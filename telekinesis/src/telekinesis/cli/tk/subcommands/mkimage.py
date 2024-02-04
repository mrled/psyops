"""The mkimage subcommand"""

from dataclasses import dataclass
import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import textwrap

from telekinesis import aports, minisign
from telekinesis.alpine_docker_builder import build_container, get_configured_docker_builder
from telekinesis.cli.tk.subcommands.buildpkg import abuild_blacksite, abuild_psyopsOS_base, build_neuralupgrade_pyz
from telekinesis.cli.tk.subcommands.requisites import get_memtest, get_ovmf
from telekinesis.config import tkconfig


def mkimage_prepare(
    skip_build_apks: bool = False,
    rebuild: bool = False,
    cleandockervol: bool = False,
    dangerous_no_clean_tmp_dir: bool = False,
):
    """Do common setup for mkimage commands"""

    aports.validate_alpine_version(tkconfig.repopaths.build, tkconfig.repopaths.aports, tkconfig.alpine_version)

    # Make sure we have an up-to-date Docker builder
    build_container(tkconfig.buildcontainer.dockertag, tkconfig.repopaths.build, rebuild)

    # Build the APKs that are also included in the ISO
    # Building them here makes sure that they are up-to-date
    # and especially that they're built on the right Python version
    # (Different Alpine versions use different Python versions,
    # and if the latest APK doesn't match what's installed on the new ISO,
    # it will fail.)
    if not skip_build_apks:
        abuild_blacksite(False, cleandockervol, dangerous_no_clean_tmp_dir)
        abuild_psyopsOS_base(False, cleandockervol, dangerous_no_clean_tmp_dir)

    return (tkconfig.alpine_version, tkconfig.buildcontainer.apkreponame, tkconfig.buildcontainer.dockertag)


def mkimage_iso(
    skip_build_apks: bool = False,
    rebuild: bool = False,
    interactive: bool = False,
    cleandockervol: bool = False,
    dangerous_no_clean_tmp_dir: bool = False,
):
    """Make a psyopsOS ISO image"""
    alpine_version, apkreponame, builder_tag = mkimage_prepare(
        skip_build_apks,
        rebuild,
        cleandockervol,
        dangerous_no_clean_tmp_dir,
    )

    with get_configured_docker_builder(interactive, cleandockervol, dangerous_no_clean_tmp_dir) as builder:
        apkindexpath = builder.in_container_apks_repo_root + f"/v{tkconfig.alpine_version}"
        apkrepopath = apkindexpath + "/" + apkreponame
        in_container_mkimage_cmd_list = [
            " ".join(
                [
                    "sh",
                    "-x",
                    "./mkimage.sh",
                    "--tag",
                    tkconfig.buildcontainer.isotag,
                    "--outdir",
                    builder.in_container_artifacts_dir,
                    "--arch",
                    tkconfig.buildcontainer.architecture,
                    "--repository",
                    f"http://dl-cdn.alpinelinux.org/alpine/v{tkconfig.alpine_version}/main",
                    "--repository",
                    f"http://dl-cdn.alpinelinux.org/alpine/v{tkconfig.alpine_version}/community",
                    "--repository",
                    apkrepopath,
                    # This would also allow using the remote APK repo, but I don't think that's necessary because of our local replica
                    # "--repository",
                    # apkpaths.uri,
                    "--workdir",
                    builder.in_container_workdir,
                    "--profile",
                    tkconfig.buildcontainer.mkimage_iso_profile,
                ]
            ),
        ]
        in_container_mkimage_cmd = " && ".join(in_container_mkimage_cmd_list)
        builder.run_docker([in_container_mkimage_cmd])
        for isofile in tkconfig.repopaths.artifacts.glob("*.iso"):
            print(f"{isofile}")


def mkimage_grubusb_repositories(alpine_version: str) -> tuple[Path, Path]:
    psyopsOS_repo = f"https://psyops.micahrl.com/apk/v{alpine_version}/psyopsOS"
    psyopsOS_apk_repositories = textwrap.dedent(
        f"""\
        https://dl-cdn.alpinelinux.org/alpine/v{alpine_version}/main
        https://dl-cdn.alpinelinux.org/alpine/v{alpine_version}/community
        @edgemain       https://dl-cdn.alpinelinux.org/alpine/edge/main
        @edgecommunity  https://dl-cdn.alpinelinux.org/alpine/edge/community
        @edgetesting    https://dl-cdn.alpinelinux.org/alpine/edge/testing
        {psyopsOS_repo}
        """
    ).strip()
    all_repos = tkconfig.artifacts.root / "psyopsOS.repositories.all"
    psyopsOS_only_repo = tkconfig.artifacts.root / "psyopsOS.repositories.psyopsOSonly"
    with all_repos.open("w") as f:
        f.write(psyopsOS_apk_repositories)
    with psyopsOS_only_repo.open("w") as f:
        f.write(f"{psyopsOS_repo}\n")
    return (all_repos, psyopsOS_only_repo)


def mkimage_grubusb_kernel(
    skip_build_apks: bool = False,
    rebuild: bool = False,
    interactive: bool = False,
    cleandockervol: bool = False,
    dangerous_no_clean_tmp_dir: bool = False,
):
    """Make a psyopsOS kernel, initramfs, etc for grubusb images"""
    alpine_version, apkreponame, builder_tag = mkimage_prepare(
        skip_build_apks,
        rebuild,
        cleandockervol,
        dangerous_no_clean_tmp_dir,
    )

    all_repos, psyopsOS_only_repo = mkimage_grubusb_repositories(alpine_version)

    with get_configured_docker_builder(interactive, cleandockervol, dangerous_no_clean_tmp_dir) as builder:
        # Add the local copy of the psyopsOS repository to the list of repositories in the container.
        # This means that when we do "apk cache download" below,
        # it will be able to find copies of psyopsOS-base and progfiguration_blacksite on local disk.
        initdir = os.path.join(builder.in_container_psyops_checkout, "psyopsOS/grubusb/initramfs-init")
        make_grubusb_kernel_script = os.path.join(
            builder.in_container_psyops_checkout, "psyopsOS/grubusb/make-grubusb-kernel.sh"
        )
        repositories_file = os.path.join(builder.in_container_artifacts_dir, all_repos.name)
        in_container_local_repo_path = os.path.join(
            builder.in_container_artifacts_dir, f"deaddrop/apk/v{alpine_version}/psyopsOS"
        )
        in_container_build_cmd = [
            "set -x",
            # Now cache the packages we need to build the image.
            # This copies them to /var/cache/apk in the container.
            # It's a little inefficient to copy them,
            # but it's worrth it so we can mount /var/cache/apk inside the initramfs chroot later.
            # We rely on the host's artifacts/deaddrop/apk being added to /etc/apk/repositories by the Dockerfile
            # so that this cache step can see apks built locally.
            f"sudo apk cache download alpine-base linux-lts linux-firmware",
            # We don't have to pass the architecture to this script,
            # because we should be running in a container with the right architecture.
            f"sudo -E {make_grubusb_kernel_script} --apk-repositories {repositories_file} --apk-local-repo {in_container_local_repo_path} --psyopsOS-init-dir {initdir} --outdir {builder.in_container_artifacts_dir}/{tkconfig.artifacts.grubusb_os_dir.name}",
        ]
        builder.run_docker(in_container_build_cmd)
        subprocess.run(["ls", "-larth", tkconfig.artifacts.grubusb_os_dir], check=True)


def mkimage_grubusb_squashfs(
    skip_build_apks: bool = False,
    rebuild: bool = False,
    interactive: bool = False,
    cleandockervol: bool = False,
    dangerous_no_clean_tmp_dir: bool = False,
):
    """Make a psyopsOS squashfs root filesystem for grubusb images"""
    builddate = datetime.datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    alpine_version, apkreponame, builder_tag = mkimage_prepare(
        skip_build_apks,
        rebuild,
        cleandockervol,
        dangerous_no_clean_tmp_dir,
    )

    all_repos, psyopsOS_only_repo = mkimage_grubusb_repositories(alpine_version)

    extra_required_packages = [
        # If this isn't present, setup-keyboard in 000-psyopsOS-postboot.start will hang waiting for user input forever.
        "kbd-bkeymaps",
    ]

    apk_cache_list = []
    apk_cache_list += extra_required_packages
    with (tkconfig.repopaths.root / "psyopsOS" / "os-overlay" / "etc" / "apk" / "world").open("r") as f:
        apk_cache_list += f.read().splitlines()
    with (tkconfig.repopaths.root / "psyopsOS" / "os-overlay" / "etc" / "apk" / "available").open("r") as f:
        apk_cache_list += f.read().splitlines()

    with get_configured_docker_builder(interactive, cleandockervol, dangerous_no_clean_tmp_dir) as builder:
        # Add the local copy of the psyopsOS repository to the list of repositories in the container.
        # This means that when we do "apk cache download" below,
        # it will be able to find copies of psyopsOS-base and progfiguration_blacksite on local disk.
        make_grubusb_squashfs_script = os.path.join(
            builder.in_container_psyops_checkout, "psyopsOS/grubusb/make-grubusb-squashfs.sh"
        )
        psyopsOS_world = os.path.join(builder.in_container_psyops_checkout, "psyopsOS/os-overlay/etc/apk/world")
        # We previously used this file to get the list of packages to cache,
        # but it's not necessary because we can just cache everything in the world file.
        # We cannot install nebula here, bc blacksite needs to create its user before it installs it itself.
        # psyopsOS_available = os.path.join(builder.in_container_psyops_checkout, "psyopsOS/os-overlay/etc/apk/available")
        in_container_all_repos = os.path.join(builder.in_container_artifacts_dir, all_repos.name)
        in_container_psyopsOS_only_repo = os.path.join(builder.in_container_artifacts_dir, psyopsOS_only_repo.name)
        in_container_outdir = os.path.join(builder.in_container_artifacts_dir, tkconfig.artifacts.grubusb_os_dir.name)
        in_container_local_repo_path = os.path.join(
            builder.in_container_artifacts_dir, f"deaddrop/apk/v{alpine_version}/psyopsOS"
        )
        in_container_build_cmd = [
            "set -x",
            # Now cache the packages we need to build the image.
            # This copies them to /var/cache/apk in the container.
            # It's a little inefficient to copy them,
            # but it's worrth it so we can mount /var/cache/apk inside the initramfs chroot later.
            # We rely on the host's artifacts/deaddrop/apk being added to /etc/apk/repositories by the Dockerfile
            # so that this cache step can see apks built locally.
            f"sudo apk cache download --latest {' '.join(apk_cache_list)}",
            # We don't have to pass the architecture to this script,
            # because we should be running in a container with the right architecture.
            f"sudo -E /bin/sh {make_grubusb_squashfs_script} --apk-packages {' '.join(extra_required_packages)} --apk-packages-file {psyopsOS_world} --apk-repositories {in_container_all_repos} --apk-repositories-psyopsOSonly {in_container_psyopsOS_only_repo} --apk-local-repo {in_container_local_repo_path} --outdir {in_container_outdir} --psyops-root {builder.in_container_psyops_checkout}",
        ]
        builder.run_docker(in_container_build_cmd)
        alpine_version_file = tkconfig.artifacts.grubusb_os_dir / "squashfs.alpine_version"
        with alpine_version_file.open("w") as f:
            f.write(alpine_version)
        subprocess.run(["ls", "-larth", tkconfig.artifacts.grubusb_os_dir], check=True)


def mkimage_grubusb_diskimg(
    out_filename: str,
    interactive: bool = False,
    cleandockervol: bool = False,
    dangerous_no_clean_tmp_dir: bool = False,
    secrets_tarball: str | None = None,
):
    """Make a disk image containing GRUB and a partition for initramfs-only images that Grub can boot

    If secrets_tarball is not None, it should be a path to a tarball containing node secrets to be included in the image.
    In that case, out_filename should probably reflect the nodename.
    """

    # We can't have the neuralupgrade package in the Docker image as an APK package,
    # because the Docker image is required to build the neuralupgrade APK package.
    # Instead, make the zipapp (outside of the Docker image) and use that.
    build_neuralupgrade_pyz()

    extra_volumes = []
    extra_scriptargs = ""
    if secrets_tarball is not None:
        extra_volumes += [f"{secrets_tarball}:/tmp/secret.tar"]
        extra_scriptargs = "-x /tmp/secret.tar"

    with get_configured_docker_builder(
        interactive, cleandockervol, dangerous_no_clean_tmp_dir, extra_volumes=extra_volumes
    ) as builder:
        make_grubusb_script = os.path.join(builder.in_container_psyops_checkout, "psyopsOS/grubusb/make-grubusb-img.sh")
        psyopsostar = os.path.join(builder.in_container_artifacts_dir, tkconfig.artifacts.grubusb_os_tarfile.name)
        psyopsesptar = os.path.join(builder.in_container_artifacts_dir, tkconfig.artifacts.grubusb_efisystar.name)
        neuralupgrade = os.path.join(builder.in_container_artifacts_dir, tkconfig.artifacts.neuralupgrade.name)
        minisign_pubkey = os.path.join(builder.in_container_psyops_checkout, "psyopsOS/minisign.pubkey")
        outimg = os.path.join(builder.in_container_artifacts_dir, out_filename)
        in_container_build_cmd = [
            f"sudo sh {make_grubusb_script} -n {neuralupgrade} -p {psyopsostar} -E {psyopsesptar} -o {outimg} -V {minisign_pubkey} {extra_scriptargs}",
        ]
        builder.run_docker(in_container_build_cmd)


def mkimage_grubusb_ostar():
    """Create the OS tarball for grubusb images"""
    build_date = datetime.datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    tarball_file = tkconfig.artifacts.grubusb_os_tarfile_versioned_format.format(version=build_date)

    items = [
        "kernel",
        "kernel.version",
        "modloop",
        "squashfs",
        "squashfs.alpine_version",
        "initramfs",
        "System.map",
        "config",
        "boot",  # Contains DTB files if the platform requires, otherwise empty
    ]
    # We don't compress because the big files - kernel/squashfs/initramfs - are already compressed
    # Compressing with "w:gz" saved about 4MB out of 630MB as of 20231215
    with tarfile.open(tkconfig.artifacts.grubusb_os_tarfile.as_posix(), "w") as tar:
        for item in items:
            tar.add(tkconfig.artifacts.grubusb_os_dir / item, arcname=item)

    with open(tkconfig.artifacts.grubusb_os_dir / "squashfs.alpine_version", "r") as f:
        alpine_version = f.read().strip()
    with open(tkconfig.artifacts.grubusb_os_dir / "kernel.version", "r") as f:
        kernel_version = f.read().strip()

    trusted_comment = (
        f"psyopsOS filename={tarball_file} version={build_date} kernel={kernel_version} alpine={alpine_version}"
    )
    # Note that we're signing the tarball using the unversioned name from tkconfig.artifacts,
    # but the trusted_comment contains the versioned name.
    # This doesn't matter, even though the default trusted_comment contains the signed filename.
    minisign.sign(tkconfig.artifacts.grubusb_os_tarfile.as_posix(), trusted_comment=trusted_comment)


def mkimage_grubusb_ostar_copy_to_deaddrop():
    """Copy the grubusb OS tarball and signature to the deaddrop, making sure they have correct names"""
    trusted_comment = minisign.verify(tkconfig.artifacts.grubusb_os_tarfile)
    prefix = "psyopsOS "
    metadata_string = trusted_comment[len(prefix) :]
    metadata = {kv[0]: kv[1] for kv in [x.split("=") for x in metadata_string.split()]}
    shutil.copy(tkconfig.artifacts.grubusb_os_tarfile, tkconfig.deaddrop.osdir / metadata["filename"])
    sig = f"{tkconfig.artifacts.grubusb_os_tarfile}.minisig"
    shutil.copy(sig, tkconfig.deaddrop.osdir / f"{metadata['filename']}.minisig")


def mkimage_grubusb_efisystar():
    """Make an EFI system partition tarball for grubusb images

    The EFI system partition is installed by neuralupgrade,
    which handles installing GRUB and creating its config file.

    This tarball contains some extra files like memtest and the EFI shell.
    """
    build_date = datetime.datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    tarball_file = tkconfig.artifacts.grubusb_efisystar_versioned_format.format(version=build_date)
    trusted_comment = f"psyopsESP filename={tarball_file} version={build_date}"
    get_ovmf()
    get_memtest()

    @dataclass
    class EfiProgram:
        localpath: str
        arcname: str
        bootentry: str

    programs = [
        EfiProgram(tkconfig.artifacts.memtest64efi, tkconfig.artifacts.memtest64efi.name, "MemTest86 EFI (64-bit)"),
        EfiProgram(tkconfig.artifacts.uefishell_extracted_bin, "tcshell.efi", "TianoCore OVMF UEFI Shell (64-bit)"),
    ]
    manifest_contents = {
        "version": 1,
        "extra_programs": {f"/{program.arcname}": program.bootentry for program in programs},
    }
    with tkconfig.artifacts.grubusb_efisystar_manifest.open("w") as f:
        json.dump(manifest_contents, f, indent=2)
    with tarfile.open(tkconfig.artifacts.grubusb_efisystar, "w") as tf:
        for program in programs:
            tf.add(program.localpath, arcname=program.arcname)
        tf.add(tkconfig.artifacts.grubusb_efisystar_manifest, arcname="manifest.json")
    minisign.sign(tkconfig.artifacts.grubusb_efisystar.as_posix(), trusted_comment=trusted_comment)


def mkimage_grubusb_efisystar_copy_to_deaddrop():
    """Copy the grubusb EFI tarball and signature to the deaddrop, making sure they have correct names"""
    trusted_comment = minisign.verify(tkconfig.artifacts.grubusb_os_tarfile)
    prefix = "psyopsESP "
    metadata_string = trusted_comment[len(prefix) :]
    metadata = {kv[0]: kv[1] for kv in [x.split("=") for x in metadata_string.split()]}
    shutil.copy(tkconfig.artifacts.grubusb_os_tarfile, tkconfig.deaddrop.osdir / metadata["filename"])
    sig = f"{tkconfig.artifacts.grubusb_os_tarfile}.minisig"
    shutil.copy(sig, tkconfig.deaddrop.osdir / f"{metadata['filename']}.minisig")
