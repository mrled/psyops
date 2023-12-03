"""The mkimage subcommand"""

import os
import subprocess

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


def mkimage_grubusbsq_squashfs(
    skip_build_apks: bool = False,
    rebuild: bool = False,
    interactive: bool = False,
    cleandockervol: bool = False,
    dangerous_no_clean_tmp_dir: bool = False,
):
    """Make a psyopsOS squashfs image for use with grubusbsq images"""
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
                    tkconfig.buildcontainer.sqtag,
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
                    tkconfig.buildcontainer.mkimage_squashfs_profile,
                ]
            ),
        ]
        in_container_mkimage_cmd = " && ".join(in_container_mkimage_cmd_list)
        builder.run_docker([in_container_mkimage_cmd])


def mkimage_grubusbsq_initramfs(
    skip_build_apks: bool = False,
    rebuild: bool = False,
    interactive: bool = False,
    cleandockervol: bool = False,
    dangerous_no_clean_tmp_dir: bool = False,
):
    """Make a psyopsOS initramfs image for grubusbsq images"""
    alpine_version, apkreponame, builder_tag = mkimage_prepare(
        skip_build_apks,
        rebuild,
        cleandockervol,
        dangerous_no_clean_tmp_dir,
    )
    with get_configured_docker_builder(interactive, cleandockervol, dangerous_no_clean_tmp_dir) as builder:
        make_initramfs_script = os.path.join(
            builder.in_container_psyops_checkout, "psyopsOS/grubusb/make-grubusbsq-initramfs.sh"
        )
        psyopsOS_init_dir = os.path.join(builder.in_container_psyops_checkout, "psyopsOS/grubusb/initramfs-init")
        initramfs = os.path.join(builder.in_container_artifacts_dir, tkconfig.artifacts.grubusbsq_initramfs.name)
        # by default mkinitfs doesn't include squashfs
        mkinitfsfeats = "ata,base,ide,scsi,usb,virtio,ext4,squashfs"
        in_container_build_cmd = [
            # Get the kernel version of the lts kernel from /lib/modules
            # it should only have one match in it because we're in an ephemeral container
            "modvers=$(cd /lib/modules && echo *-lts)",
            f"sudo sh {make_initramfs_script} -o {initramfs} -I {psyopsOS_init_dir} -F {mkinitfsfeats} -K $modvers",
        ]
        builder.run_docker(in_container_build_cmd)
        subprocess.run(["ls", "-larth", tkconfig.artifacts.grubusbsq_initramfs], check=True)


def mkimage_grubusbsq_diskimg(
    interactive: bool = False,
    cleandockervol: bool = False,
    dangerous_no_clean_tmp_dir: bool = False,
):
    """Make a disk image containing GRUB and a partition for squashfs images that Grub can boot"""
    with get_configured_docker_builder(interactive, cleandockervol, dangerous_no_clean_tmp_dir) as builder:
        make_grubusb_script = os.path.join(builder.in_container_psyops_checkout, "psyopsOS/grubusb/make-grubusbsq.sh")
        initramfs = os.path.join(builder.in_container_artifacts_dir, tkconfig.artifacts.grubusbsq_initramfs.name)
        squashfs = os.path.join(builder.in_container_artifacts_dir, tkconfig.artifacts.grubusbsq_squashfs.name)
        outimg = os.path.join(builder.in_container_artifacts_dir, tkconfig.artifacts.grubusbsq_img.name)
        in_container_build_cmd = [
            # Get the kernel version of the lts kernel from /lib/modules
            # it should only have one match in it because we're in an ephemeral container
            "modvers=$(cd /lib/modules && echo *-lts)",
            f"sudo sh {make_grubusb_script} -k /boot/vmlinuz-lts -i {initramfs} -q {squashfs} -o {outimg} -m {tkconfig.artifacts.memtest64efi}",
        ]
        builder.run_docker(in_container_build_cmd)


def mkimage_grubusb_initramfs(
    skip_build_apks: bool = False,
    rebuild: bool = False,
    interactive: bool = False,
    cleandockervol: bool = False,
    dangerous_no_clean_tmp_dir: bool = False,
):
    """Make a psyopsOS initramfs image for grubusb images"""
    alpine_version, apkreponame, builder_tag = mkimage_prepare(
        skip_build_apks,
        rebuild,
        cleandockervol,
        dangerous_no_clean_tmp_dir,
    )
    with get_configured_docker_builder(interactive, cleandockervol, dangerous_no_clean_tmp_dir) as builder:
        initdir = os.path.join(builder.in_container_psyops_checkout, "psyopsOS/grubusb/initramfs-init")
        make_grubusb_os_script = os.path.join(
            builder.in_container_psyops_checkout, "psyopsOS/grubusb/make-grubusb-os.sh"
        )
        in_container_build_cmd = [
            # We don't have to pass the architecture to this script,
            # because we should be running in a container with the right architecture.
            f"{make_grubusb_os_script} --psyopsOS-init-dir {initdir} --outdir {builder.in_container_artifacts_dir}/{tkconfig.artifacts.grubusb_os_dir.name}",
        ]
        builder.run_docker(in_container_build_cmd)
        subprocess.run(["ls", "-larth", tkconfig.artifacts.grubusb_os_dir], check=True)


def mkimage_grubusb_diskimg(
    interactive: bool = False,
    cleandockervol: bool = False,
    dangerous_no_clean_tmp_dir: bool = False,
):
    """Make a disk image containing GRUB and a partition for initramfs-only images that Grub can boot"""
    mkimage_grubusbsq_initramfs(
        skip_build_apks=False,
        rebuild=False,
        interactive=interactive,
        cleandockervol=cleandockervol,
        dangerous_no_clean_tmp_dir=dangerous_no_clean_tmp_dir,
    )
    with get_configured_docker_builder(interactive, cleandockervol, dangerous_no_clean_tmp_dir) as builder:
        make_grubusb_script = os.path.join(builder.in_container_psyops_checkout, "psyopsOS/grubusb/make-grubusb-img.sh")
        psyopsosdir = os.path.join(builder.in_container_artifacts_dir, tkconfig.artifacts.grubusb_os_dir.name)
        memtest64efi = os.path.join(builder.in_container_artifacts_dir, tkconfig.artifacts.memtest64efi.name)
        outimg = os.path.join(builder.in_container_artifacts_dir, tkconfig.artifacts.grubusb_img.name)
        in_container_build_cmd = [
            f"sudo sh {make_grubusb_script} -m {memtest64efi} -p {psyopsosdir} -o {outimg}",
        ]
        builder.run_docker(in_container_build_cmd)
