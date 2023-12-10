"""The mkimage subcommand"""

import os
import subprocess
import textwrap

from telekinesis import aports
from telekinesis.alpine_docker_builder import build_container, get_configured_docker_builder
from telekinesis.cli.tk.subcommands.buildpkg import abuild_blacksite, abuild_psyopsOS_base
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

    psyopsOS_apk_repositories = textwrap.dedent(
        f"""\
        https://dl-cdn.alpinelinux.org/alpine/v{alpine_version}/main
        https://dl-cdn.alpinelinux.org/alpine/v{alpine_version}/community
        @edgemain       https://dl-cdn.alpinelinux.org/alpine/edge/main
        @edgecommunity  https://dl-cdn.alpinelinux.org/alpine/edge/community
        @edgetesting    https://dl-cdn.alpinelinux.org/alpine/edge/testing
        https://psyops.micahrl.com/apk/v{alpine_version}/psyopsOS
        """
    ).strip()
    with (tkconfig.artifacts.root / "psyopsOS.repositories").open("w") as f:
        f.write(psyopsOS_apk_repositories)

    with get_configured_docker_builder(interactive, cleandockervol, dangerous_no_clean_tmp_dir) as builder:
        # Add the local copy of the psyopsOS repository to the list of repositories in the container.
        # This means that when we do "apk cache download" below,
        # it will be able to find copies of psyopsOS-base and progfiguration_blacksite on local disk.
        initdir = os.path.join(builder.in_container_psyops_checkout, "psyopsOS/grubusb/initramfs-init")
        make_grubusb_kernel_script = os.path.join(
            builder.in_container_psyops_checkout, "psyopsOS/grubusb/make-grubusb-kernel.sh"
        )
        repositories_file = os.path.join(builder.in_container_artifacts_dir, "psyopsOS.repositories")
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
    alpine_version, apkreponame, builder_tag = mkimage_prepare(
        skip_build_apks,
        rebuild,
        cleandockervol,
        dangerous_no_clean_tmp_dir,
    )

    psyopsOS_apk_repositories = textwrap.dedent(
        f"""\
        https://dl-cdn.alpinelinux.org/alpine/v{alpine_version}/main
        https://dl-cdn.alpinelinux.org/alpine/v{alpine_version}/community
        @edgemain       https://dl-cdn.alpinelinux.org/alpine/edge/main
        @edgecommunity  https://dl-cdn.alpinelinux.org/alpine/edge/community
        @edgetesting    https://dl-cdn.alpinelinux.org/alpine/edge/testing
        https://psyops.micahrl.com/apk/v{alpine_version}/psyopsOS
        """
    ).strip()
    with (tkconfig.artifacts.root / "psyopsOS.repositories").open("w") as f:
        f.write(psyopsOS_apk_repositories)

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
        psyopsOS_available = os.path.join(builder.in_container_psyops_checkout, "psyopsOS/os-overlay/etc/apk/available")
        psyopsOS_overlay = os.path.join(builder.in_container_psyops_checkout, "psyopsOS/os-overlay")
        repositories_file = os.path.join(builder.in_container_artifacts_dir, "psyopsOS.repositories")
        outdir = os.path.join(builder.in_container_artifacts_dir, tkconfig.artifacts.grubusb_os_dir.name)
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
            f"sudo -E /bin/sh {make_grubusb_squashfs_script} --apk-packages {' '.join(extra_required_packages)} --apk-packages-file {psyopsOS_world} --apk-packages-file {psyopsOS_available} --apk-repositories {repositories_file} --apk-local-repo {in_container_local_repo_path} --outdir {outdir} --psyopsos-overlay-dir {psyopsOS_overlay}",
        ]
        builder.run_docker(in_container_build_cmd)
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
    extra_volumes = []
    extra_scriptargs = ""
    if secrets_tarball is not None:
        extra_volumes += [f"{secrets_tarball}:/tmp/secret.tar"]
        extra_scriptargs = "-x /tmp/secret.tar"

    with get_configured_docker_builder(
        interactive, cleandockervol, dangerous_no_clean_tmp_dir, extra_volumes=extra_volumes
    ) as builder:
        make_grubusb_script = os.path.join(builder.in_container_psyops_checkout, "psyopsOS/grubusb/make-grubusb-img.sh")
        psyopsosdir = os.path.join(builder.in_container_artifacts_dir, tkconfig.artifacts.grubusb_os_dir.name)
        memtest64efi = os.path.join(builder.in_container_artifacts_dir, tkconfig.artifacts.memtest64efi.name)
        outimg = os.path.join(builder.in_container_artifacts_dir, out_filename)
        in_container_build_cmd = [
            f"sudo sh {make_grubusb_script} -m {memtest64efi} -p {psyopsosdir} -o {outimg} {extra_scriptargs}",
        ]
        builder.run_docker(in_container_build_cmd)
