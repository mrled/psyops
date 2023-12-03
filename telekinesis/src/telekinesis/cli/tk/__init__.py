"""The `tk` command"""


import argparse
import logging
import pdb
import pprint
import subprocess
import sys
import traceback
import zipfile

from telekinesis import deaddrop
from telekinesis.alpine_docker_builder import build_container, get_configured_docker_builder
from telekinesis.cli.tk.subcommands.buildpkg import abuild_blacksite, abuild_psyopsOS_base
from telekinesis.cli.tk.subcommands.mkimage import (
    mkimage_grubusb_diskimg,
    mkimage_grubusb_initramfs,
    mkimage_iso,
    mkimage_grubusbsq_diskimg,
    mkimage_grubusbsq_initramfs,
    mkimage_grubusbsq_squashfs,
)
from telekinesis.cli.tk.subcommands.vm import get_ovmf, vm_grubusb_img, vm_grubusb_os
from telekinesis.config import getsecret, tkconfig
from telekinesis.rget import rget


def idb_excepthook(type, value, tb):
    """Call an interactive debugger in post-mortem mode"""
    if hasattr(sys, "ps1") or not sys.stderr.isatty():
        sys.__excepthook__(type, value, tb)
    else:
        traceback.print_exception(type, value, tb)
        print
        pdb.pm()


def get_memtest():
    """Download and extract memtest binaries"""
    # code to download memtest from memtest.org with requestslibrary:
    rget(
        "https://memtest.org/download/v6.20/mt86plus_6.20.binaries.zip",
        tkconfig.artifacts.memtest_zipfile,
    )
    if not tkconfig.artifacts.memtest64efi.exists():
        with zipfile.ZipFile(tkconfig.artifacts.memtest_zipfile, "r") as zip_ref:
            zip_ref.extract("memtest64.efi", tkconfig.repopaths.artifacts)


def deployiso(host):
    """Deploy the ISO image to a remote host"""
    subprocess.run(
        ["scp", tkconfig.deaddrop.isodir.as_posix(), f"root@{host}:/tmp/{tkconfig.deaddrop.isofilename}"], check=True
    )
    subprocess.run(
        ["ssh", f"root@{host}", "/usr/sbin/psyopsOS-write-bootmedia", f"/tmp/{tkconfig.deaddrop.isofilename}"],
        check=True,
    )


def makeparser(prog=None):
    """Return the argument parser for this program

    prog: The name of the program, used in the help text.
    """

    parser = argparse.ArgumentParser(
        prog=prog,
        description="Telekinesis: the PSYOPS build and administration tool",
    )
    parser.add_argument(
        "--debug",
        "-d",
        action="store_true",
        help="Open the debugger if an unhandled exception is encountered.",
    )

    subparsers = parser.add_subparsers(dest="action", required=True)

    # The showconfig subcommand
    sub_showconfig = subparsers.add_parser(
        "showconfig",
        help="Show the current configuration",
    )

    # The cog subcommand
    sub_cog = subparsers.add_parser(
        "cog",
        help="Run cog on all relevant files",
    )

    # The deaddrop subcommand
    sub_deaddrop = subparsers.add_parser(
        "deaddrop",
        help=f"Manage the S3 bucket used for psyopOS, called deaddrop, or its local replica",
    )
    sub_deaddrop_subparsers = sub_deaddrop.add_subparsers(dest="deaddrop_action", required=True)
    sub_deaddrop_sub_ls = sub_deaddrop_subparsers.add_parser(
        "ls",
        help="List the files in the bucket",
    )
    sub_deaddrop_sub_forcepull = sub_deaddrop_subparsers.add_parser(
        "forcepull",
        help="Pull files from the bucket into the local replica and delete any local files that are not in the bucket... we don't do a nicer sync operation because APKINDEX files can't be managed that way.",
    )
    sub_deaddrop_sub_forcepush = sub_deaddrop_subparsers.add_parser(
        "forcepush",
        help="Push files from the local replica to the bucket and delete any bucket files that are not in the local replica.",
    )

    # Options related to the build container
    buildcontainer_opts = argparse.ArgumentParser(add_help=False)
    buildcontainer_opts.add_argument(
        "--rebuild", action="store_true", help="Rebuild the build container even if it already exists"
    )
    buildcontainer_opts.add_argument(
        "--interactive", action="store_true", help="Run a shell in the container instead of running the build command"
    )
    buildcontainer_opts.add_argument("--clean", action="store_true", help="Clean the docker volume before running")
    buildcontainer_opts.add_argument(
        "--dangerous-no-clean-tmp-dir",
        action="store_true",
        help="Don't clean the temporary directory containing the APK key",
    )

    # The builder subcommand
    sub_builder = subparsers.add_parser(
        "builder",
        help="Actions related to the psyopsOS Docker container that is used for making Alpine packages and ISO images",
    )
    sub_builder_subparsers = sub_builder.add_subparsers(dest="builder_action", required=True)
    sub_builder_sub_build = sub_builder_subparsers.add_parser(
        "build",
        parents=[buildcontainer_opts],
        help="Build the psyopsOS Docker container",
    )
    sub_builder_sub_runcmd = sub_builder_subparsers.add_parser(
        "runcmd",
        parents=[buildcontainer_opts],
        help="Run a single command in the container, for testing purposes",
    )
    sub_builder_sub_runcmd.add_argument(
        "command",
        nargs="+",
        help="The command to run in the container, like 'whoami' or 'ls -larth'. Note that if any of the arguments start with a dash, you'll need to use '--' to separate the command from the arguments, like '... build runcmd -- ls -larth'.",
    )

    # The mkimage subcommand
    sub_mkimage = subparsers.add_parser(
        "mkimage",
        parents=[buildcontainer_opts],
        help="Make a psyopsOS image",
    )
    sub_mkimage.add_argument("--skip-build-apks", action="store_true", help="Don't build APKs before building ISO")
    sub_mkimage_subparsers = sub_mkimage.add_subparsers(dest="mkimage_action", required=True)
    sub_mkimage_sub_iso = sub_mkimage_subparsers.add_parser(
        "iso",
        help="Build an ISO image using mkimage.sh and the psyopsOScd profile",
    )
    sub_mkimage_sub_grubusbsq = sub_mkimage_subparsers.add_parser(
        "grubusbsq",
        help="Build a disk image that contains GRUB, can do A/B updates, and boots to squashfs root images.",
    )
    sub_mkimage_sub_grubusbsq.add_argument(
        "--stages",
        default="squashfs,initramfs,grubusb",
        help="The stages to build, comma-separated. Default: %(default)s",
    )
    sub_mkimage_sub_grubusb = sub_mkimage_subparsers.add_parser(
        "grubusb",
        help="Build a disk image that contains GRUB, can do A/B updates, and boots to initramfs root images without squashfs.",
    )
    sub_mkimage_sub_grubusb.add_argument(
        "--stages",
        nargs="*",
        default=["osdir", "diskimg"],
        choices=["geninitpatch", "osdir", "diskimg"],
        help="The stages to build, comma-separated. Default: %(default)s. geninitpatch: Generate the initramfs-init patch. osdir: Build the OS directory. diskimg: Build the disk image from the osdir.",
    )

    # The buildpkg subcommand
    sub_buildpkg = subparsers.add_parser(
        "buildpkg",
        parents=[buildcontainer_opts],
        help="Build a package",
    )
    sub_buildpkg.add_argument("package", nargs="+", choices=["base", "blacksite"], help="The package(s) to build")

    # The deployiso subcommand
    sub_deployiso = subparsers.add_parser(
        "deployiso",
        help="Deploy the ISO image to the S3 bucket",
    )
    sub_deployiso.add_argument("host", help="The remote host to deploy to, assumes root@ accepts the psyops SSH key")

    # The vm subcommand
    sub_vm = subparsers.add_parser(
        "vm",
        help="Run VM(s)",
    )
    sub_vm_subparsers = sub_vm.add_subparsers(dest="vm_action", required=True)
    sub_vm_sub_grubusb = sub_vm_subparsers.add_parser(
        "grubusb",
        help="Run the grubusb image in qemu",
    )
    sub_vm_sub_grubusb = sub_vm_subparsers.add_parser(
        "osdir",
        help="Run the kernel/initramfs from the osdir in qemu without building a grubusb image with EFI and A/B partitions",
    )
    sub_vm_sub_grubusb.add_argument(
        "--grubusb-image",
        default=tkconfig.artifacts.grubusb_img,
        help="Path to the grubusb image",
    )

    return parser


def main():
    parser = makeparser()
    parsed = parser.parse_args()

    if parsed.debug:
        print(f"Arguments: {parsed}")
        sys.excepthook = idb_excepthook

    if parsed.action == "showconfig":
        pprint.pprint(tkconfig.__dict__, indent=2, sort_dicts=False)
    elif parsed.action == "cog":
        for path in [tkconfig.psyopsroot / "telekinesis" / "readme.md"]:
            subprocess.run(["cog", "-r", path.as_posix()], check=True)
    elif parsed.action == "deaddrop":
        aws_keyid = getsecret(tkconfig.deaddrop.onepassword_item, "username")
        aws_secret = getsecret(tkconfig.deaddrop.onepassword_item, "password")
        aws_sess = deaddrop.makesession(aws_keyid, aws_secret, tkconfig.deaddrop.region)
        if parsed.deaddrop_action == "ls":
            deaddrop.list_files(aws_sess, tkconfig.deaddrop.bucketname)
        elif parsed.deaddrop_action == "forcepull":
            deaddrop.s3_forcepull_directory(aws_sess, tkconfig.deaddrop.bucketname, tkconfig.deaddrop.localpath)
        elif parsed.deaddrop_action == "forcepush":
            deaddrop.s3_forcepush_directory(aws_sess, tkconfig.deaddrop.bucketname, tkconfig.deaddrop.localpath)
        else:
            parser.error(f"Unknown deaddrop action: {parsed.deaddrop_action}")
    elif parsed.action == "builder":
        if parsed.builder_action == "build":
            build_container(tkconfig.buildcontainer.dockertag, tkconfig.repopaths.build, parsed.rebuild)
        elif parsed.builder_action == "runcmd":
            with get_configured_docker_builder(
                parsed.interactive, parsed.clean, parsed.dangerous_no_clean_tmp_dir
            ) as builder:
                builder.run_docker_raw(parsed.command)
        else:
            parser.error(f"Unknown builder action: {parsed.builder_action}")
    elif parsed.action == "mkimage":
        if parsed.mkimage_action == "iso":
            mkimage_iso(
                skip_build_apks=parsed.skip_build_apks,
                rebuild=parsed.rebuild,
                interactive=parsed.interactive,
                cleandockervol=parsed.clean,
                dangerous_no_clean_tmp_dir=parsed.dangerous_no_clean_tmp_dir,
            )
        elif parsed.mkimage_action == "grubusbsq":
            if "squashfs" in parsed.stages:
                mkimage_grubusbsq_squashfs(
                    skip_build_apks=parsed.skip_build_apks,
                    rebuild=parsed.rebuild,
                    interactive=parsed.interactive,
                    cleandockervol=parsed.clean,
                    dangerous_no_clean_tmp_dir=parsed.dangerous_no_clean_tmp_dir,
                )
            if "initramfs" in parsed.stages:
                mkimage_grubusbsq_initramfs(
                    skip_build_apks=parsed.skip_build_apks,
                    rebuild=parsed.rebuild,
                    interactive=parsed.interactive,
                    cleandockervol=parsed.clean,
                    dangerous_no_clean_tmp_dir=parsed.dangerous_no_clean_tmp_dir,
                )
            if "grubusb" in parsed.stages:
                mkimage_grubusbsq_diskimg(
                    interactive=parsed.interactive,
                    cleandockervol=parsed.clean,
                    dangerous_no_clean_tmp_dir=parsed.dangerous_no_clean_tmp_dir,
                )
        elif parsed.mkimage_action == "grubusb":
            if "geninitpatch" in parsed.stages:
                initdir = tkconfig.repopaths.root / "psyopsOS" / "grubusb" / "initramfs-init"
                init_patch = initdir / "initramfs-init.psyopsOS.grubusb.patch"
                with init_patch.open("w") as f:
                    subprocess.run(["ls", "-larth"], cwd=initdir, check=True)
                    subprocess.run(
                        ["diff", "-u", "initramfs-init.orig", "initramfs-init.patched.grubusb"],
                        cwd=initdir,
                        check=True,
                        stdout=f,
                    )
            if "osdir" in parsed.stages:
                mkimage_grubusb_initramfs(
                    skip_build_apks=parsed.skip_build_apks,
                    rebuild=parsed.rebuild,
                    interactive=parsed.interactive,
                    cleandockervol=parsed.clean,
                    dangerous_no_clean_tmp_dir=parsed.dangerous_no_clean_tmp_dir,
                )
            if "diskimg" in parsed.stages:
                get_memtest()
                mkimage_grubusb_diskimg(
                    interactive=parsed.interactive,
                    cleandockervol=parsed.clean,
                    dangerous_no_clean_tmp_dir=parsed.dangerous_no_clean_tmp_dir,
                )
        else:
            parser.error(f"Unknown mkimage action: {parsed.mkimage_action}")
    elif parsed.action == "vm":
        if parsed.vm_action == "diskimg":
            get_ovmf()
            vm_grubusb_img()
        elif parsed.vm_action == "osdir":
            vm_grubusb_os()
        else:
            parser.error(f"Unknown vm action: {parsed.vm_action}")
    elif parsed.action == "buildpkg":
        if "base" in parsed.package:
            abuild_psyopsOS_base(parsed.interactive, parsed.clean, parsed.dangerous_no_clean_tmp_dir)
        if "blacksite" in parsed.package:
            abuild_blacksite(parsed.interactive, parsed.clean, parsed.dangerous_no_clean_tmp_dir)
    elif parsed.action == "deployiso":
        deployiso(parsed.host)
    else:
        parser.error(f"Unknown action: {parsed.action}")
