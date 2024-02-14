"""The `tk` command"""

import argparse
import logging
import os
from pathlib import Path
import pprint
import subprocess
import sys
import tarfile
import textwrap
import zipfile

from telekinesis import deaddrop, minisign, tklogger, tksecrets
from telekinesis.alpine_docker_builder import build_container, get_configured_docker_builder
from telekinesis.cli import idb_excepthook
from telekinesis.cli.tk.subcommands.buildpkg import (
    abuild_blacksite,
    abuild_psyopsOS_base,
    build_neuralupgrade_apk,
    build_neuralupgrade_pyz,
)
from telekinesis.cli.tk.subcommands.mkimage import (
    mkimage_grubusb_diskimg,
    mkimage_grubusb_efisystar,
    mkimage_grubusb_efisystar_copy_to_deaddrop,
    mkimage_grubusb_kernel,
    mkimage_grubusb_squashfs,
    mkimage_iso,
    mkimage_grubusb_ostar,
    mkimage_grubusb_ostar_copy_to_deaddrop,
)
from telekinesis.cli.tk.subcommands.requisites import get_ovmf, get_memtest
from telekinesis.cli.tk.subcommands.vm import vm_grubusb_img, vm_grubusb_os
from telekinesis.config import tkconfig


def deployiso(host):
    """Deploy the ISO image to a remote host"""
    isofile = tkconfig.deaddrop.isopath
    subprocess.run(["scp", isofile.as_posix(), f"root@{host}:/tmp/{isofile.name}"], check=True)
    subprocess.run(
        ["ssh", f"root@{host}", "/usr/sbin/psyopsOS-write-bootmedia", "iso", f"/tmp/{isofile.name}"], check=True
    )


def deploygrubusb(host, remote_path="/tmp"):
    """Deploy the ISO image to a remote host

    This uses multiple SSH commands, so enabling SSH master mode is recommended.

    neuralupgrade is copied into /usr/local/sbin/ on the remote host for later use.

    TODO: should I also copy the minisign public key?
    """
    build_neuralupgrade()
    nupyz = tkconfig.artifacts.neuralupgrade
    tarball = tkconfig.artifacts.grubusb_os_tarfile
    minisig = tarball.with_name(tarball.name + ".minisig")
    subprocess.run(["scp", nupyz.as_posix(), f"root@{host}:/usr/local/sbin/neuralupgrade"], check=True)
    subprocess.run(["scp", tarball.as_posix(), minisig.as_posix(), f"root@{host}:{remote_path}/"], check=True)
    subprocess.run(
        [
            "ssh",
            f"root@{host}",
            "/usr/local/sbin/neuralupgrade",
            "--verbose",
            "apply",
            "nonbooted",
            "--ostar",
            f"{remote_path}/{tarball.name}",
        ],
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
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Print more information about what is happening.",
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
        help=f"Manage the S3 bucket used for psyopsOS, called deaddrop, or its local replica",
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
    sub_mkimage_sub_grubusb = sub_mkimage_subparsers.add_parser(
        "grubusb",
        help="Build a disk image that contains GRUB, can do A/B updates, and boots to initramfs root images without squashfs.",
    )

    grubusb_stages = {
        "mkinitpatch": "Generate a patch by comparing a locally created/modified initramfs-init.patched.grubusb file (NOT in version control) to the upstream Alpine initramfs-init.orig file (in version control), and saving the resulting patch to initramfs-init.psyopsOS.grubusb.patch (in version control). This is only necessary when making changes to our patch, and is not part of a normal image build. Basically do this: diff -u initramfs-init.orig initramfs-init.patched.grubusb > initramfs-init.psyopsOS.grubusb.patch",
        "applyinitpatch": "Generate initramfs-init.patched.grubusb by appling our patch to the upstream file. This happens during every normal build. Basically do this: patch -o initramfs-init.patched.grubusb initramfs-init.orig initramfs-init.psyopsOS.grubusb.patch",
        "kernel": "Build the kernel/initramfs/etc.",
        "squashfs": "Build the squashfs root filesystem.",
        "efisystar": "Create a tarball that contains extra EFI system partition files - not GRUB which is installed by neuralupgrade, but optional files like memtest.",
        "efisystar-dd": "Copy the efisystar tarball to the local deaddrop directory. (Use 'tk deaddrop forcepush' to push it to the bucket.)",
        "ostar": "Create a tarball of the kernel/squashfs/etc that can be used to apply an A/B update.",
        "ostar-dd": "Copy the ostar tarball to the local deaddrop directory. (Use 'tk deaddrop forcepush' to push it to the bucket.)",
        "sectar": "Create a tarball of secrets for a node-specific grubusb image. Requires that --node-secrets NODENAME is passed, and that the node already exists in progfiguration_blacksite (see 'progfiguration-blacksite-node save --help').",
        "diskimg": "Build the disk image from the kernel/squashfs. If --node-secrets is passed, the secrets tarball is included in the image. Otherwise, the image is node-agnostic and contains an empty secrets volume.",
    }

    class StagesHelpAction(argparse.Action):
        """An argparse action that prints the stages help text and exits

        Nicely format each stage and its description, wrap the text to terminal width, and indent any description that is longer than one line.
        """

        def __call__(self, parser, namespace, values, option_string=None):
            terminal_width = os.get_terminal_size().columns
            max_stage_length = max(len(stage) for stage in grubusb_stages)
            wrapped_text = "grubusb stages:\n\n"
            for stage, desc in grubusb_stages.items():
                # Format the line with a fixed tab stop
                line = f"{stage.ljust(max_stage_length + 4)}{desc}"
                wrapped_line = textwrap.fill(line, width=terminal_width, subsequent_indent=" " * (max_stage_length + 4))
                wrapped_text += wrapped_line + "\n"
            print(wrapped_text)
            parser.exit()

    sub_mkimage_sub_grubusb.add_argument(
        "--stages",
        nargs="+",
        default=["kernel", "squashfs", "diskimg"],
        choices=grubusb_stages.keys(),
        help="The stages to build, comma-separated. Default: %(default)s. See --list-stages for all possible stages and their descriptions.",
    )
    sub_mkimage_sub_grubusb.add_argument(
        "--list-stages",
        action=StagesHelpAction,
        nargs=0,
        help="Show all possible stages and their descriptions.",
    )
    sub_mkimage_sub_grubusb.add_argument(
        "--node-secrets",
        help="If passed, generate a node-specific grubusb image with a populated secrets volume containing secrets from 'progfiguration-blacksite-node save NODENAME ...'.",
    )

    # The buildpkg subcommand
    sub_buildpkg = subparsers.add_parser(
        "buildpkg",
        parents=[buildcontainer_opts],
        help="Build a package",
    )
    sub_buildpkg.add_argument(
        "package",
        nargs="+",
        choices=["base", "blacksite", "neuralupgrade-apk", "neuralupgrade-pyz"],
        help="The package(s) to build",
    )

    # The deployos subcommand
    sub_deployos = subparsers.add_parser(
        "deployos",
        help="Deploy the ISO image to a psyopsOS remote host",
    )
    sub_deployos.add_argument(
        "--type", default="grubusb", choices=["iso", "grubusb"], help="The type of image to deploy"
    )
    sub_deployos.add_argument("host", help="The remote host to deploy to, assumes root@ accepts the psyops SSH key")

    # The vm subcommand
    sub_vm = subparsers.add_parser(
        "vm",
        help="Run VM(s)",
    )
    sub_vm_subparsers = sub_vm.add_subparsers(dest="vm_action", required=True)
    sub_vm_sub_diskimg = sub_vm_subparsers.add_parser(
        "diskimg",
        help="Run the grubusb image in qemu",
    )
    sub_vm_sub_diskimg.add_argument(
        "--grubusb-image",
        type=Path,
        default=tkconfig.artifacts.node_image(),
        help="Path to the grubusb image",
    )
    sub_vm_sub_diskimg.add_argument(
        "--macaddr",
        default="00:00:00:00:00:00",
        help="The MAC address to use for the VM, defaults to %(default)s",
    )
    sub_vm_sub_osdir = sub_vm_subparsers.add_parser(
        "osdir",
        help="Run the kernel/initramfs from the osdir in qemu without building a grubusb image with EFI and A/B partitions",
    )
    sub_vm_sub_profile = sub_vm_subparsers.add_parser(
        "profile",
        help="Run a predefined VM profile (a shortcut for running specific VMs like qreamsqueen which we use for testing psyopsOS)",
    )

    vm_profiles = {
        "qreamsqueen": "Run the qreamsqueen VM. Requires that artifacts/psyopsOS.qreamsqueen.img has been created by running 'tk mkimage grubusb --stages diskimg --node-secrets qreamsqueen'.",
    }

    class ProfilesHelpAction(argparse.Action):
        """An argparse action that prints the profiles help text and exits

        Nicely format each profile and its description, wrap the text to terminal width, and indent any description that is longer than one line.
        """

        def __call__(self, parser, namespace, values, option_string=None):
            terminal_width = os.get_terminal_size().columns
            max_profile_length = max(len(profile) for profile in vm_profiles)
            wrapped_text = "VM profiles:\n\n"
            for profile, desc in vm_profiles.items():
                # Format the line with a fixed tab stop
                line = f"{profile.ljust(max_profile_length + 4)}{desc}"
                wrapped_line = textwrap.fill(
                    line, width=terminal_width, subsequent_indent=" " * (max_profile_length + 4)
                )
                wrapped_text += wrapped_line + "\n"
            print(wrapped_text)
            parser.exit()

    sub_vm_sub_profile.add_argument(
        "profile",
        choices=["qreamsqueen"],
        help="The profile to run. See --list-profiles for all possible profiles and their descriptions.",
    )
    sub_vm_sub_profile.add_argument(
        "--list-profiles",
        action=ProfilesHelpAction,
        nargs=0,
        help="Show all possible profiles and their descriptions.",
    )

    # The psynet subcommand
    sub_psynet = subparsers.add_parser(
        "psynet",
        help="Manage psynet",
    )
    sub_psynet_subparsers = sub_psynet.add_subparsers(dest="psynet_action", required=True)
    sub_psynet_sub_run = sub_psynet_subparsers.add_parser(
        "run",
        help="Run a command in the context of the psynet certificate authority",
    )
    sub_psynet_sub_run.add_argument(
        "--cadir",
        type=Path,
        help="The directory containing the psynet certificate authority. If not passed, a temporary directory is created, and deleted along with its contents when the command exits.",
    )
    sub_psynet_sub_run.add_argument(
        "command",
        nargs="+",
        help="The command to run in the context of the psynet certificate authority. If any of the arguments start with a dash, you'll need to use '--' to separate the command from the arguments, like '... psynet run -- ls -larth'.",
    )
    sub_psynet_sub_get = sub_psynet_subparsers.add_parser(
        "get",
        help="Get a node from the psynet",
    )
    sub_psynet_sub_get.add_argument(
        "node",
        help="The node to get",
    )
    sub_psynet_sub_set = sub_psynet_subparsers.add_parser(
        "set",
        help="Set a node in the psynet",
    )
    sub_psynet_sub_set.add_argument(
        "node",
        help="The node to set",
    )
    sub_psynet_sub_set.add_argument(
        "crt",
        type=Path,
        help="The filename of the node's certificate",
    )
    sub_psynet_sub_set.add_argument(
        "key",
        type=Path,
        help="The filename of the node's key",
    )

    # The signify subcommand
    sub_signify = subparsers.add_parser(
        "signify",
        help="Sign and verify with the psyopsOS signature tooling",
    )
    sub_signify_subparsers = sub_signify.add_subparsers(dest="signify_action", required=True)
    sub_signify_sub_sign = sub_signify_subparsers.add_parser(
        "sign",
        help="Sign a file",
    )
    sub_signify_sub_sign.add_argument(
        "file",
        type=Path,
        help="The file to sign",
    )
    sub_signify_sub_verify = sub_signify_subparsers.add_parser(
        "verify",
        help="Verify a file",
    )
    sub_signify_sub_verify.add_argument(
        "file",
        type=Path,
        help="The file to verify",
    )

    return parser


def main_impl():
    """Top level program logic for the `tk` command"""
    parser = makeparser()
    parsed = parser.parse_args()

    conhandler = logging.StreamHandler()
    conhandler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    tklogger.addHandler(conhandler)
    if parsed.debug:
        print(f"Arguments: {parsed}")
        sys.excepthook = idb_excepthook
    if parsed.verbose:
        tklogger.setLevel(logging.DEBUG)

    if parsed.action == "showconfig":
        print(tkconfig.pformat(indent=2, sort_dicts=False))
    elif parsed.action == "cog":
        for path in [
            tkconfig.psyopsroot / "telekinesis" / "readme.md",
            tkconfig.psyopsroot / "psyopsOS" / "neuralupgrade" / "readme.md",
        ]:
            subprocess.run(["cog", "-r", path.as_posix()], check=True)
    elif parsed.action == "deaddrop":
        aws_keyid, aws_secret = tkconfig.deaddrop.get_credential()
        aws_sess = deaddrop.makesession(aws_keyid, aws_secret, tkconfig.deaddrop.region)
        if parsed.deaddrop_action == "ls":
            files, symlinks = deaddrop.s3_list_remote_files(aws_sess, tkconfig.deaddrop.bucketname)
            print("Files:")
            pprint.pprint(files)
            print("Symlinks:")
            pprint.pprint(symlinks)
        elif parsed.deaddrop_action == "forcepull":
            deaddrop.s3_forcepull_directory(aws_sess, tkconfig.deaddrop.bucketname, tkconfig.deaddrop.localpath)
        elif parsed.deaddrop_action == "forcepush":
            deaddrop.s3_forcepush_deaddrop(aws_sess, tkconfig.deaddrop.bucketname, tkconfig.deaddrop.localpath)
        else:
            parser.error(f"Unknown deaddrop action: {parsed.deaddrop_action}")
    elif parsed.action == "builder":
        if parsed.builder_action == "build":
            build_container(tkconfig.buildcontainer.dockertag, tkconfig.repopaths.buildcontainer, parsed.rebuild)
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
        elif parsed.mkimage_action == "grubusb":
            initdir = tkconfig.repopaths.root / "psyopsOS" / "grubusb" / "initramfs-init"
            init_patch = initdir / "initramfs-init.psyopsOS.grubusb.patch"
            if "mkinitpatch" in parsed.stages:
                with init_patch.open("w") as f:
                    subprocess.run(["ls", "-larth"], cwd=initdir, check=True)
                    diffresult = subprocess.run(
                        ["diff", "-u", "initramfs-init.orig", "initramfs-init.patched.grubusb"],
                        cwd=initdir,
                        check=False,
                        stdout=f,
                    )
                    # Diff returns 0 if the files are the same, 1 if they are different, and >1 if there was an error
                    if diffresult.returncode == 0:
                        tklogger.debug(f"initramfs-init.patched.grubusb was the same as initramfs-init.orig")
                    elif diffresult.returncode == 1:
                        tklogger.debug(f"initramfs-init.patched.grubusb was different from initramfs-init.orig")
                    else:
                        tklogger.error(f"diff returned {diffresult.returncode}")
                        sys.exit(1)
            if "applyinitpatch" in parsed.stages:
                subprocess.run(
                    ["patch", "-o", "initramfs-init.patched.grubusb", "initramfs-init.orig", init_patch.as_posix()],
                    cwd=initdir,
                    check=True,
                )
            if "kernel" in parsed.stages:
                mkimage_grubusb_kernel(
                    skip_build_apks=parsed.skip_build_apks,
                    rebuild=parsed.rebuild,
                    interactive=parsed.interactive,
                    cleandockervol=parsed.clean,
                    dangerous_no_clean_tmp_dir=parsed.dangerous_no_clean_tmp_dir,
                )
            if "squashfs" in parsed.stages:
                mkimage_grubusb_squashfs(
                    skip_build_apks=parsed.skip_build_apks,
                    rebuild=parsed.rebuild,
                    interactive=parsed.interactive,
                    cleandockervol=parsed.clean,
                    dangerous_no_clean_tmp_dir=parsed.dangerous_no_clean_tmp_dir,
                )
            if "ostar" in parsed.stages:
                mkimage_grubusb_ostar()
            if "ostar-dd" in parsed.stages:
                mkimage_grubusb_ostar_copy_to_deaddrop()
            if "efisystar" in parsed.stages:
                mkimage_grubusb_efisystar()
            if "efisystar-dd" in parsed.stages:
                mkimage_grubusb_efisystar_copy_to_deaddrop()
            if "sectar" in parsed.stages and parsed.node_secrets:
                subprocess.run(
                    [
                        "progfiguration-blacksite-node",
                        "save",
                        parsed.node_secrets,
                        "--outtar",
                        tkconfig.artifacts.node_secrets(parsed.node_secrets),
                        "--force",
                    ],
                )
            if "diskimg" in parsed.stages:
                get_memtest()
                mgd_kwargs = dict(
                    out_filename=tkconfig.artifacts.node_image().name,
                    interactive=parsed.interactive,
                    cleandockervol=parsed.clean,
                    dangerous_no_clean_tmp_dir=parsed.dangerous_no_clean_tmp_dir,
                )
                if parsed.node_secrets:
                    mgd_kwargs["out_filename"] = tkconfig.artifacts.node_image(parsed.node_secrets).name
                    mgd_kwargs["secrets_tarball"] = tkconfig.artifacts.node_secrets(parsed.node_secrets)
                mkimage_grubusb_diskimg(**mgd_kwargs)
        else:
            parser.error(f"Unknown mkimage action: {parsed.mkimage_action}")
    elif parsed.action == "vm":
        if parsed.vm_action == "diskimg":
            get_ovmf()
            vm_grubusb_img(parsed.grubusb_image, parsed.macaddr)
        elif parsed.vm_action == "osdir":
            vm_grubusb_os()
        elif parsed.vm_action == "profile":
            if parsed.profile == "qreamsqueen":
                get_ovmf()
                vm_grubusb_img(tkconfig.artifacts.node_image("qreamsqueen"), "ac:ed:de:ad:be:ef")
            else:
                parser.error(f"Unknown profile: {parsed.profile}")
        else:
            parser.error(f"Unknown vm action: {parsed.vm_action}")
    elif parsed.action == "buildpkg":
        if "base" in parsed.package:
            abuild_psyopsOS_base(parsed.interactive, parsed.clean, parsed.dangerous_no_clean_tmp_dir)
        if "blacksite" in parsed.package:
            abuild_blacksite(parsed.interactive, parsed.clean, parsed.dangerous_no_clean_tmp_dir)
        if "neuralupgrade-pyz" in parsed.package:
            build_neuralupgrade_pyz()
        if "neuralupgrade-apk" in parsed.package:
            build_neuralupgrade_apk(parsed.interactive, parsed.clean, parsed.dangerous_no_clean_tmp_dir)
    elif parsed.action == "deployos":
        if parsed.type == "iso":
            deployiso(parsed.host)
        elif parsed.type == "grubusb":
            deploygrubusb(parsed.host)
        else:
            parser.error(f"Unknown deployment type: {parsed.type}")
    elif parsed.action == "psynet":
        if parsed.psynet_action == "run":
            if parsed.cadir:
                os.makedirs(parsed.cadir, exist_ok=True)
            with tksecrets.psynetca(parsed.cadir) as cadir:
                subprocess.run(parsed.command, cwd=cadir, check=True)
        elif parsed.psynet_action == "get":
            crt, key = tksecrets.psynet_get(parsed.node)
            print(f"Certificate for {parsed.node}:")
            print(crt)
            print(f"Key for {parsed.node}:")
            print(key)
        elif parsed.psynet_action == "set":
            tksecrets.psynet_set(parsed.node, parsed.crt, parsed.key)
        else:
            parser.error(f"Unknown psynet action: {parsed.psynet_action}")
    elif parsed.action == "signify":
        if parsed.signify_action == "sign":
            minisign.sign(parsed.file)
        elif parsed.signify_action == "verify":
            print(minisign.verify(parsed.file))
        else:
            parser.error(f"Unknown signify action: {parsed.signify_action}")
    else:
        parser.error(f"Unknown action: {parsed.action}")


def main():
    """Entry point for the `tk` command"""
    try:
        main_impl()
    except KeyboardInterrupt:
        print("Got KeyboardInterrupt, exiting...")
