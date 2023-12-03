"""The mkimage subcommand"""

import os
import string
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

    apk_cache_list = []
    with (tkconfig.repopaths.root / "psyopsOS" / "os-overlay" / "etc" / "apk" / "world").open("r") as f:
        apk_cache_list += f.read().splitlines()
    with (tkconfig.repopaths.root / "psyopsOS" / "os-overlay" / "etc" / "apk" / "available").open("r") as f:
        apk_cache_list += f.read().splitlines()

    with get_configured_docker_builder(interactive, cleandockervol, dangerous_no_clean_tmp_dir) as builder:
        # Add the local copy of the psyopsOS repository to the list of repositories in the container.
        # This means that when we do "apk cache download" below,
        # it will be able to find copies of psyopsOS-base and progfiguration_blacksite on local disk.
        initdir = os.path.join(builder.in_container_psyops_checkout, "psyopsOS/grubusb/initramfs-init")
        make_grubusb_os_script = os.path.join(
            builder.in_container_psyops_checkout, "psyopsOS/grubusb/make-grubusb-os.sh"
        )
        psyopsOS_world = os.path.join(builder.in_container_psyops_checkout, "psyopsOS/os-overlay/etc/apk/world")
        psyopsOS_available = os.path.join(builder.in_container_psyops_checkout, "psyopsOS/os-overlay/etc/apk/available")
        repositories_file = os.path.join(builder.in_container_artifacts_dir, "psyopsOS.repositories")
        in_container_build_cmd = [
            "set -x",
            # Now cache the packages we need to build the image.
            # This copies them to /var/cache/apk in the container.
            # It's a little inefficient to copy them,
            # but it's worrth it so we can mount /var/cache/apk inside the initramfs chroot later.
            # We rely on the host's artifacts/deaddrop/apk being added to /etc/apk/repositories by the Dockerfile
            # so that this cache step can see apks built locally.
            f"sudo apk cache download alpine-base linux-lts linux-firmware {' '.join(apk_cache_list)}",
            "sudo apk cache download progfiguration_blacksite",
            "uname -a",
            "apk --print-arch",
            "cat /etc/apk/repositories",
            "ls -alF /home/build/artifacts/deaddrop/apk",
            "ls -alF /home/build/artifacts/deaddrop/apk/v3.18/psyopsOS/x86_64",
            "exit",
            # We don't have to pass the architecture to this script,
            # because we should be running in a container with the right architecture.
            f"sudo -E {make_grubusb_os_script} --apk-packages-file {psyopsOS_world} --apk-packages-file {psyopsOS_available} --apk-repositories {repositories_file} --psyopsOS-init-dir {initdir} --outdir {builder.in_container_artifacts_dir}/{tkconfig.artifacts.grubusb_os_dir.name}",
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
