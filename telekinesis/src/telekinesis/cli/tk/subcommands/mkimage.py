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

from telekinesis import minisign
from telekinesis.alpine_docker_builder import AlpineDockerBuilder
from telekinesis.architectures import Architecture
from telekinesis.cli.tk.subcommands.buildpkg import build_neuralupgrade_pyz
from telekinesis.cli.tk.subcommands.requisites import get_rpi_firmware, get_x64_memtest, get_x64_ovmf
from telekinesis.config import tkconfig


def mkimage_iso(architecture: Architecture, builder: AlpineDockerBuilder):
    """Make a psyopsOS ISO image"""
    with builder:
        apkindexpath = builder.in_container_apks_repo_root + f"/v{tkconfig.alpine_version}"
        apkrepopath = apkindexpath + "/" + tkconfig.buildcontainer.apkreponame
        in_container_mkimage_cmd_list = [
            " ".join(
                [
                    "sh",
                    "-x",
                    "./mkimage.sh",
                    "--tag",
                    tkconfig.buildcontainer.isotag,
                    "--outdir",
                    builder.in_container_arch_artifacts_dir,
                    "--arch",
                    architecture.mkimage,
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
        for isofile in tkconfig.repopaths.artifacts.glob("*/*.iso"):
            print(f"{isofile}")


def generate_apk_repositories_files(alpine_version: str) -> tuple[Path, Path]:
    """Generate APK repositories files

    The first file contains Alpine main/community,
    tagged edge main/community/testing,
    and the psyopsOS repository on deaddrop.
    The second file contains only the psyopsOS repository on deaddrop.

    Returns a tuple of paths to the two files.
    """
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
    os.makedirs(tkconfig.noarch_artifacts.noarchroot, exist_ok=True)
    all_repos = tkconfig.noarch_artifacts.noarchroot / "psyopsOS.repositories.all"
    psyopsOS_only_repo = tkconfig.noarch_artifacts.noarchroot / "psyopsOS.repositories.psyopsOSonly"
    with all_repos.open("w") as f:
        f.write(psyopsOS_apk_repositories)
    with psyopsOS_only_repo.open("w") as f:
        f.write(f"{psyopsOS_repo}\n")
    return (all_repos, psyopsOS_only_repo)


def make_kernel(builder: AlpineDockerBuilder):
    """Make a psyopsOS kernel, initramfs, etc for disk images (not ISOs)"""
    all_repos, psyopsOS_only_repo = generate_apk_repositories_files(tkconfig.alpine_version)

    extra_args = ""

    if builder.architecture.name == "aarch64":
        extra_args = " --kernel-flavor rpi --dtbs-dir /boot"

    with builder:
        # Add the local copy of the psyopsOS repository to the list of repositories in the container.
        # This means that when we do "apk cache download" below,
        # it will be able to find copies of psyopsOS-base and progfiguration_blacksite on local disk.
        initdir = os.path.join(builder.in_container_psyops_checkout, "psyopsOS/osbuild/initramfs-init")
        make_kernel_script = os.path.join(
            builder.in_container_psyops_checkout, "psyopsOS/osbuild/make-psyopsOS-kernel.sh"
        )
        repositories_file = os.path.join(builder.in_container_noarch_artifacts_dir, all_repos.name)
        in_container_local_repo_path = os.path.join(
            builder.in_container_artifacts_root, f"deaddrop/apk/v{tkconfig.alpine_version}/psyopsOS"
        )
        arch_artifacts = tkconfig.arch_artifacts[builder.architecture.name]
        in_container_osdir = os.path.join(builder.in_container_arch_artifacts_dir, arch_artifacts.osdir_path.name)
        in_container_build_cmd = [
            "set -x",
            "sudo apk update",
            # Now cache the packages we need to build the image.
            # This copies them to /var/cache/apk in the container.
            # It's a little inefficient to copy them,
            # but it's worrth it so we can mount /var/cache/apk inside the initramfs chroot later.
            # We rely on the host's artifacts/deaddrop/apk being added to /etc/apk/repositories by the Dockerfile
            # so that this cache step can see apks built locally.
            "sudo apk cache download alpine-base linux-lts linux-firmware",
            # We don't have to pass the architecture to this script,
            # because we should be running in a container with the right architecture.
            f"sudo -E {make_kernel_script} --apk-repositories {repositories_file} --apk-local-repo {in_container_local_repo_path} --psyopsOS-init-dir {initdir} --outdir {in_container_osdir} {extra_args}",
        ]
        builder.run_docker(in_container_build_cmd)
        if arch_artifacts.osdir_path.exists():
            subprocess.run(["ls", "-larth", arch_artifacts.osdir_path], check=True)


def make_squashfs(builder: AlpineDockerBuilder):
    """Make a psyopsOS squashfs root filesystem for disk images (not ISOs)"""

    all_repos, psyopsOS_only_repo = generate_apk_repositories_files(tkconfig.alpine_version)

    extra_required_packages = [
        # If this isn't present, setup-keyboard in 100-psyopsOS-postboot.start will hang waiting for user input forever.
        "kbd-bkeymaps",
    ]

    apk_cache_list = []
    apk_cache_list += extra_required_packages
    with (tkconfig.repopaths.root / "psyopsOS" / "os-overlay" / "etc" / "apk" / "world").open("r") as f:
        apk_cache_list += f.read().splitlines()
    with (tkconfig.repopaths.root / "psyopsOS" / "os-overlay" / "etc" / "apk" / "available").open("r") as f:
        apk_cache_list += f.read().splitlines()

    with builder:
        # Add the local copy of the psyopsOS repository to the list of repositories in the container.
        # This means that when we do "apk cache download" below,
        # it will be able to find copies of psyopsOS-base and progfiguration_blacksite on local disk.
        make_squashfs_script = os.path.join(
            builder.in_container_psyops_checkout, "psyopsOS/osbuild/make-psyopsOS-squashfs.sh"
        )
        psyopsOS_world = os.path.join(builder.in_container_psyops_checkout, "psyopsOS/os-overlay/etc/apk/world")
        # We previously used this file to get the list of packages to cache,
        # but it's not necessary because we can just cache everything in the world file.
        # We cannot install nebula here, bc blacksite needs to create its user before it installs it itself.
        # psyopsOS_available = os.path.join(builder.in_container_psyops_checkout, "psyopsOS/os-overlay/etc/apk/available")
        in_container_all_repos = os.path.join(builder.in_container_noarch_artifacts_dir, all_repos.name)
        in_container_psyopsOS_only_repo = os.path.join(
            builder.in_container_noarch_artifacts_dir, psyopsOS_only_repo.name
        )
        arch_artifacts = tkconfig.arch_artifacts[builder.architecture.name]
        osdir_path = arch_artifacts.osdir_path
        in_container_outdir = os.path.join(builder.in_container_arch_artifacts_dir, osdir_path.name)
        in_container_local_repo_path = os.path.join(
            builder.in_container_artifacts_root, f"deaddrop/apk/v{tkconfig.alpine_version}/psyopsOS"
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
            f"sudo -E /bin/sh {make_squashfs_script} --apk-packages {' '.join(extra_required_packages)} --apk-packages-file {psyopsOS_world} --apk-repositories {in_container_all_repos} --apk-repositories-psyopsOSonly {in_container_psyopsOS_only_repo} --apk-local-repo {in_container_local_repo_path} --outdir {in_container_outdir} --psyops-root {builder.in_container_psyops_checkout}",
        ]
        builder.run_docker(in_container_build_cmd)
        alpine_version_file = osdir_path / "squashfs.alpine_version"
        with alpine_version_file.open("w") as f:
            f.write(tkconfig.alpine_version)
        subprocess.run(["ls", "-larth", osdir_path], check=True)


def make_boot_image(
    architecture: Architecture,
    out_filename: str,
    builder: AlpineDockerBuilder,
    secrets_tarball: str = "",
):
    """Make a disk image containing our bootloader"""

    # We can't have the neuralupgrade package in the Docker image as an APK package,
    # because the Docker image is required to build the neuralupgrade APK package.
    # Instead, make the zipapp (outside of the Docker image) and use that.
    build_neuralupgrade_pyz()

    extra_scriptargs = ""

    if secrets_tarball:
        builder.extra_volumes = [f"{secrets_tarball}:/tmp/secret.tar"]
        extra_scriptargs = " -x /tmp/secret.tar"

    with builder:
        arch_artifacts = tkconfig.arch_artifacts[builder.architecture.name]

        fwtype = None
        psyopsesptar = None
        if architecture.name == "x86_64":
            fwtype = "x86_64_uefi"
        elif architecture.name == "aarch64":
            fwtype = "raspberrypi"
        if fwtype is None:
            raise RuntimeError(f"Unsupported architecture {architecture.name} for boot image")

        psyopsesptar = os.path.join(builder.in_container_arch_artifacts_dir, arch_artifacts.esptar_path.name)
        extra_scriptargs += f" -E {psyopsesptar}"

        make_img_script = os.path.join(builder.in_container_psyops_checkout, "psyopsOS/osbuild/make-psyopsOS-img.sh")
        psyopsostar = os.path.join(builder.in_container_arch_artifacts_dir, arch_artifacts.ostar_path.name)
        neuralupgrade = os.path.join(
            builder.in_container_noarch_artifacts_dir, tkconfig.noarch_artifacts.neuralupgrade.name
        )
        minisign_pubkey = os.path.join(builder.in_container_psyops_checkout, "psyopsOS/minisign.pubkey")
        outimg = os.path.join(builder.in_container_arch_artifacts_dir, out_filename)
        # TODO: Fix NeuralUpgrade so we don't have to mock a booted side
        in_container_build_cmd = [
            f"sudo sh {make_img_script} -n {neuralupgrade} -N '--booted-mock=psyopsOS-A' -f {fwtype} -p {psyopsostar} -o {outimg} -V {minisign_pubkey} {extra_scriptargs}",
        ]
        builder.run_docker(in_container_build_cmd)


def make_ostar(architecture: Architecture):
    """Create the OS tarball"""
    build_date = datetime.datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    arch_artifacts = tkconfig.arch_artifacts[architecture.name]
    tarball_file = arch_artifacts.ostar_versioned_fmt.format(arch=architecture.name, version=build_date)

    items = [
        "kernel",
        "kernel.version",
        "modloop",
        "squashfs",
        "squashfs.alpine_version",
        "initramfs",
        "System.map",
        "config",
    ]
    optional_items = [
        # Contains DTB files for some platforms if the platform requires
        "dtbs",
    ]
    # We don't compress because the big files - kernel/squashfs/initramfs - are already compressed
    # Compressing with "w:gz" saved about 4MB out of 630MB as of 20231215
    with tarfile.open(arch_artifacts.ostar_path.as_posix(), "w") as tar:
        for item in items:
            tar.add(arch_artifacts.osdir_path / item, arcname=item)
    with tarfile.open(arch_artifacts.ostar_path.as_posix(), "a") as tar:
        for item in optional_items:
            item_path = arch_artifacts.osdir_path / item
            if not item_path.exists():
                continue
            tar.add(item_path, arcname=item)

    with open(arch_artifacts.osdir_path / "squashfs.alpine_version", "r") as f:
        alpine_version = f.read().strip()
    with open(arch_artifacts.osdir_path / "kernel.version", "r") as f:
        kernel_version = f.read().strip()

    trusted_comment = f"type=psyopsOS filename={tarball_file} version={build_date} kernel={kernel_version} alpine={alpine_version} architecture={architecture.kernel}"

    # Note that we're signing the tarball using the unversioned name from arch_artifacts,
    # but the trusted_comment contains the versioned name.
    # This doesn't matter, even though the default trusted_comment contains the signed filename.
    minisign.sign(arch_artifacts.ostar_path.as_posix(), trusted_comment=trusted_comment)


def copy_ostar_to_deaddrop(architecture: Architecture):
    """Copy the OS tarball and signature to the deaddrop, making sure they have correct names"""
    arch_artifacts = tkconfig.arch_artifacts[architecture.name]
    trusted_comment = minisign.verify(arch_artifacts.ostar_path)
    metadata = {kv[0]: kv[1] for kv in [x.split("=") for x in trusted_comment.split()]}
    os.makedirs(tkconfig.deaddrop.osdir, exist_ok=True)
    shutil.copy(arch_artifacts.ostar_path, tkconfig.deaddrop.osdir / metadata["filename"])
    sig = f"{arch_artifacts.ostar_path}.minisig"
    shutil.copy(sig, tkconfig.deaddrop.osdir / f"{metadata['filename']}.minisig")

    # symlink the minisig to latest.minisig
    ostar_name = arch_artifacts.ostar_versioned_fmt.format(arch=architecture.name, version="latest")
    latest_sig = tkconfig.deaddrop.osdir / (ostar_name + ".minisig")
    if latest_sig.exists():
        latest_sig.unlink()
    latest_sig.symlink_to(f"{metadata['filename']}.minisig")


def make_boot_tar(builder: AlpineDockerBuilder):
    """Make the boot tarball for the platform"""

    if builder.architecture.name == "x86_64":
        return make_x64_efi_boot_tar(builder)
    elif builder.architecture.name == "aarch64":
        return make_rpi4_boot_tar(builder)


def make_x64_efi_boot_tar(builder: AlpineDockerBuilder):
    """Make an EFI system partition tarball

    The EFI system partition is installed by neuralupgrade,
    which handles installing GRUB and creating its config file.

    This tarball contains some extra files like memtest and the EFI shell.
    """
    architecture = builder.architecture
    build_date = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S")
    arch_artifacts = tkconfig.arch_artifacts[architecture.name]
    tarball_file = arch_artifacts.esptar_versioned_fmt.format(arch=architecture.name, version=build_date)
    get_x64_ovmf()
    get_x64_memtest()

    @dataclass
    class EfiProgram:
        localpath: str
        arcname: str
        bootentry: str

    programs = [
        EfiProgram(arch_artifacts.memtest64efi.as_posix(), arch_artifacts.memtest64efi.name, "MemTest86 EFI (64-bit)"),
        EfiProgram(
            arch_artifacts.uefishell_extracted_bin.as_posix(), "tcshell.efi", "TianoCore OVMF UEFI Shell (64-bit)"
        ),
    ]
    programs_list = ",".join([program.arcname for program in programs])
    trusted_comment = f"type=psyopsESP filename={tarball_file} version={build_date} efi_programs={programs_list}"
    manifest_contents = {
        "version": 1,
        "extra_programs": {f"/{program.arcname}": program.bootentry for program in programs},
    }
    with arch_artifacts.esptar_manifest.open("w") as f:
        json.dump(manifest_contents, f, indent=2)
    with tarfile.open(arch_artifacts.esptar_path, "w") as tf:
        for program in programs:
            tf.add(program.localpath, arcname=program.arcname)
        tf.add(arch_artifacts.esptar_manifest, arcname="manifest.json")
    minisign.sign(arch_artifacts.esptar_path.as_posix(), trusted_comment=trusted_comment)


def get_rpi4_uboot(builder: AlpineDockerBuilder):
    """Get the Raspberry Pi 4 U-Boot binary"""
    artifacts = tkconfig.arch_artifacts[builder.architecture.name]
    with builder:
        outdir = os.path.join(builder.in_container_arch_artifacts_dir, "u-boot")
        in_container_cmd = [
            f"mkdir -p {outdir}",
            # The Alpine u-boot binary for the Raspberry Pi 4 in package u-boot-raspberrypi
            f"cp /usr/share/u-boot/rpi_arm64/u-boot.bin {outdir}",
            f"apk info u-boot-raspberrypi | head -n1 | sed 's/ .*//' > {outdir}/u-boot.version",
            # The Linux kernel dtb and dtbo files required for U-Boot and VideoCore
            # (the Pi GPU firmware that runs before U-Boot).
            # From package linux-rpi.
            # These are not necessarily the ones used by the psyopsOS kernel.
            # U-Boot needs the dtb it was built with,
            # which in this case is the one built for the Alpine linux-rpi kernel,
            # and VideoCore needs the disable-bt overlay so we can set it in our config.txt,
            # which is necessary to use the serial port after boot.
            # The Linux kernel booted from A/B will use the dtb and any overlays
            # found on the A/B partition, NOT THESE.
            f"cp /boot/bcm2711-rpi-4-b.dtb {outdir}/u-boot.dtb",
            f"mkdir -p {outdir}/overlays",
            f"cp /boot/overlays/disable-bt.dtbo {outdir}/overlays/disable-bt.dtbo",
            f"apk info linux-rpi | head -n1 | sed 's/ .*//' > {outdir}/dtbs-linux-rpi.version",
        ]
        builder.run_docker(in_container_cmd)


def make_rpi4_boot_tar(builder: AlpineDockerBuilder):
    """Make a Raspberry Pi 4 boot tarball

    The Raspberry Pi boot partition is installed by neuralupgrade,
    which handles installing GRUB and creating its config file.
    """
    arch = builder.architecture.name
    build_date = datetime.datetime.now(tz=datetime.timezone.utc).strftime("%Y%m%d-%H%M%S")
    arch_artifacts = tkconfig.arch_artifacts[arch]
    tarball_file = arch_artifacts.esptar_versioned_fmt.format(arch=arch, version=build_date)

    get_rpi4_uboot(builder)

    get_rpi_firmware()
    rpifwboot = arch_artifacts.rpi_firmware_extracted / "boot"

    uboot_version_file = arch_artifacts.uboot_path / "u-boot.version"
    uboot_version = uboot_version_file.read_text().strip()
    trusted_comment = f"type=psyopsOSBoot filename={tarball_file} uboot_version={uboot_version} rpi_firmware_version={arch_artifacts.rpi_firmware_version} version={build_date}"

    with tarfile.open(arch_artifacts.esptar_path, "w") as tf:
        tf.add(arch_artifacts.uboot_path / "u-boot.bin", arcname="u-boot.bin")
        tf.add(arch_artifacts.uboot_path / "u-boot.dtb", arcname="u-boot.dtb")
        tf.add(arch_artifacts.uboot_path / "overlays" / "disable-bt.dtbo", arcname="overlays/disable-bt.dtbo")
        tf.add(arch_artifacts.uboot_path / "u-boot.version", arcname="u-boot.version")
        tf.add(arch_artifacts.uboot_path / "dtbs-linux-rpi.version", arcname="u-boot.version")

        tf.add(rpifwboot / "fixup4.dat", arcname="fixup4.dat")
        tf.add(rpifwboot / "start4.elf", arcname="start4.elf")

    minisign.sign(arch_artifacts.esptar_path.as_posix(), trusted_comment=trusted_comment)


def copy_esptar_to_deaddrop(architecture: Architecture):
    """Copy the EFI tarball and signature to the deaddrop, making sure they have correct names"""
    arch_artifacts = tkconfig.arch_artifacts[architecture.name]
    trusted_comment = minisign.verify(arch_artifacts.esptar_path)
    metadata = {kv[0]: kv[1] for kv in [x.split("=") for x in trusted_comment.split()]}
    os.makedirs(tkconfig.deaddrop.osdir, exist_ok=True)
    shutil.copy(arch_artifacts.esptar_path, tkconfig.deaddrop.osdir / metadata["filename"])
    sig = f"{arch_artifacts.esptar_path}.minisig"
    shutil.copy(sig, tkconfig.deaddrop.osdir / f"{metadata['filename']}.minisig")

    # symlink the minisig to latest.minisig
    esptar_name = arch_artifacts.esptar_versioned_fmt.format(arch=architecture.name, version="latest")
    latest_sig = tkconfig.deaddrop.osdir / (esptar_name + ".minisig")
    if latest_sig.exists():
        latest_sig.unlink()
    latest_sig.symlink_to(f"{metadata['filename']}.minisig")
