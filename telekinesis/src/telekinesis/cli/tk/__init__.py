"""The `tk` command"""

import argparse
import logging
import os
from pathlib import Path
import pprint
import subprocess
import sys
import textwrap

from telekinesis import aports, deaddrop, minisign, tklogger, tksecrets
from telekinesis.alpine_docker_builder import (
    AlpineDockerBuilder,
    build_container,
    get_configured_docker_builder,
)
from telekinesis.cli import idb_excepthook
from telekinesis.cli.tk.subcommands.buildpkg import (
    abuild_blacksite,
    abuild_psyopsOS_base,
    build_neuralupgrade_apk,
    build_neuralupgrade_pyz,
)
from telekinesis.cli.tk.subcommands.mkimage import (
    copy_esptar_to_deaddrop,
    copy_ostar_to_deaddrop,
    make_boot_tar,
    make_boot_image,
    make_kernel,
    make_ostar,
    make_squashfs,
    mkimage_iso,
)
from telekinesis.cli.tk.subcommands.requisites import get_x64_ovmf
from telekinesis.cli.tk.subcommands.vm import vm_diskimg, vm_osdir
from telekinesis.config import tkconfig
from telekinesis.platforms import Architecture, PLATFORMS


class ListKeyValuePairsAndExit(argparse.Action):
    """An argparse action that lists key-value pairs and exits.

    Nicely format each key and its value, wrap the text to terminal width, and indent any value that is longer than one line.
    """

    def __init__(
        self, option_strings, dest, kvpairs: dict[str, str], kvpair_help_prefix="", kvpair_help_suffix="", **kwargs
    ):
        self.kvpairs = kvpairs
        self.kvpair_help_prefix = kvpair_help_prefix
        self.kvpair_help_suffix = kvpair_help_suffix
        super(ListKeyValuePairsAndExit, self).__init__(option_strings, dest, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        print(self._help_text)
        parser.exit()

    @property
    def _help_text(self) -> str:
        terminal_width = os.get_terminal_size().columns
        max_key_len = max(len(key) for key in self.kvpairs)
        wrapped_text = self.kvpair_help_prefix + "\n\n"
        for key, value in self.kvpairs.items():
            # Format the line with a fixed tab stop
            line = f"{key.ljust(max_key_len + 4)}{value}"
            wrapped_line = textwrap.fill(line, width=terminal_width, subsequent_indent=" " * (max_key_len + 4))
            wrapped_text += wrapped_line + "\n"
        wrapped_text += self.kvpair_help_suffix
        return wrapped_text


def CommaSeparatedStrList(cssl: str) -> list[str]:
    """Convert a string with commas into a list of strings

    Useful as a type= argument to argparse.add_argument()
    """
    return cssl.split(",")


def deploy_ostar(host: str, tarball: Path, remote_path: str = "/tmp"):
    """Deploy the ostar to a remote host

    This uses multiple SSH commands, so enabling SSH master mode is recommended.

    neuralupgrade is copied into /usr/local/sbin/ on the remote host for later use.

    TODO: should I also copy the minisign public key?
    TODO: is copying neuralupgrade a good idea, now that it's an APK package?
    TODO: this doesn't work with architectures yet
    """
    build_neuralupgrade_pyz()
    nupyz = tkconfig.noarch_artifacts.neuralupgrade
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
            "--os-tar",
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

    # archlist = ",".join(all_architectures.keys())
    # parser.add_argument(
    #     "--architecture",
    #     default=list(all_architectures.keys()),
    #     type=CommaSeparatedStrList,
    #     help=f"The architecture(s) to build for. Default: {archlist}.",
    # )

    # bootsyslist = ",".join(BOOTSYSTEMS.keys())
    # parser.add_argument(
    #     "--bootsystem",
    #     default=list(BOOTSYSTEMS.keys()),
    #     type=CommaSeparatedStrList,
    #     help=f"The bootsystem(s) to build for. Default: {bootsyslist}.",
    # )

    platlist = ",".join(PLATFORMS.keys())
    parser.add_argument(
        "--platform",
        default=list(PLATFORMS.keys()),
        type=CommaSeparatedStrList,
        help=f"The platform(s) to build for. Default: {platlist}.",
    )

    subparsers = parser.add_subparsers(dest="action", required=True)

    # The showconfig subcommand
    subparsers.add_parser(
        "showconfig",
        help="Show the current configuration",
    )

    # The cog subcommand
    subparsers.add_parser(
        "cog",
        help="Run cog on all relevant files",
    )

    # The deaddrop subcommand
    sub_deaddrop = subparsers.add_parser(
        "deaddrop",
        help="Manage the S3 bucket used for psyopsOS, called deaddrop, or its local replica",
    )
    sub_deaddrop_subparsers = sub_deaddrop.add_subparsers(dest="deaddrop_action", required=True)
    sub_deaddrop_subparsers.add_parser(
        "ls",
        help="List the files in the bucket",
    )
    sub_deaddrop_subparsers.add_parser(
        "forcepull",
        help="Pull files from the bucket into the local replica and delete any local files that are not in the bucket... we don't do a nicer sync operation because APKINDEX files can't be managed that way.",
    )
    sub_deaddrop_subparsers.add_parser(
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
    sub_builder_subparsers.add_parser(
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
    sub_mkimage_subparsers.add_parser(
        "iso",
        help="Build an ISO image using mkimage.sh and the psyopsOScd profile",
    )
    sub_mkimage_sub_diskimg = sub_mkimage_subparsers.add_parser(
        "diskimg",
        help="Build a disk image that contains GRUB, can do A/B updates, and boots to initramfs root images without squashfs.",
    )

    diskimg_stages = {
        "mkinitpatch": "Generate a patch by comparing a locally created/modified initramfs-init.patched file (NOT in version control) to the upstream Alpine initramfs-init.orig file (in version control), and saving the resulting patch to initramfs-init.patch (in version control). This is only necessary when making changes to our patch, and is not part of a normal image build. Basically do this: diff -u initramfs-init.orig initramfs-init.patched > initramfs-init.patch",
        "applyinitpatch": "Generate initramfs-init.patched by appling our patch to the upstream file. This happens during every normal build. Basically do this: patch -o initramfs-init.patched initramfs-init.orig initramfs-init.patch",
        "kernel": "Build the kernel/initramfs/etc.",
        "squashfs": "Build the squashfs root filesystem.",
        "efisystar": "Create a tarball that contains extra EFI system partition files - not GRUB which is installed by neuralupgrade, but optional files like memtest.",
        "efisystar-dd": "Copy the efisystar tarball to the local deaddrop directory. (Use 'tk deaddrop forcepush' to push it to the bucket.)",
        "ostar": "Create a tarball of the kernel/squashfs/etc that can be used to apply an A/B update.",
        "ostar-dd": "Copy the ostar tarball to the local deaddrop directory. (Use 'tk deaddrop forcepush' to push it to the bucket.)",
        "sectar": "Create a tarball of secrets for a node-specific disk image. Requires that --node-secrets NODENAME is passed, and that the node already exists in progfiguration_blacksite (see 'progfiguration-blacksite-node save --help').",
        "diskimg": "Build the disk image from the kernel/squashfs. If --node-secrets is passed, the secrets tarball is included in the image. Otherwise, the image is node-agnostic and contains an empty secrets volume.",
    }

    sub_mkimage_sub_diskimg.add_argument(
        "--stages",
        nargs="+",
        default=["kernel", "squashfs", "diskimg"],
        choices=diskimg_stages.keys(),
        help="The stages to build. Default: %(default)s. See --list-stages for all possible stages and their descriptions.",
    )
    sub_mkimage_sub_diskimg.add_argument(
        "--list-stages",
        action=ListKeyValuePairsAndExit,
        kvpairs=diskimg_stages,
        kvpair_help_prefix="diskimg stages:",
        kvpair_help_suffix="",
        nargs=0,
        help="Show all possible stages and their descriptions.",
    )
    sub_mkimage_sub_diskimg.add_argument(
        "--node-secrets",
        metavar="NODENAME",
        help="If passed, generate a node-specific image with a populated secrets volume containing secrets from 'progfiguration-blacksite-node save NODENAME ...' (which is run automatically by this).",
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
        "--deploy-type", default="diskimg", choices=["iso", "diskimg"], help="The type of image to deploy"
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
        help="Run the disk image in qemu",
    )
    sub_vm_sub_diskimg.add_argument(
        "--disk-image",
        type=Path,
        help="Path to the disk image",
    )
    sub_vm_sub_diskimg.add_argument(
        "--macaddr",
        default="00:00:00:00:00:00",
        help="The MAC address to use for the VM, defaults to %(default)s",
    )
    sub_vm_subparsers.add_parser(
        "osdir",
        help="Run the kernel/initramfs from the osdir in qemu without building a disk image with EFI and A/B partitions",
    )
    sub_vm_sub_profile = sub_vm_subparsers.add_parser(
        "profile",
        help="Run a predefined VM profile (a shortcut for running specific VMs like qreamsqueen which we use for testing psyopsOS)",
    )

    vm_profiles = {
        "qreamsqueen": "Run the qreamsqueen VM. Requires that artifacts/psyopsOS.qreamsqueen.img has been created by running 'tk mkimage diskimg --stages diskimg --node-secrets qreamsqueen'.",
    }

    sub_vm_sub_profile.add_argument(
        "profile",
        choices=["qreamsqueen"],
        help="The profile to run. See --list-profiles for all possible profiles and their descriptions.",
    )
    sub_vm_sub_profile.add_argument(
        "--list-profiles",
        action=ListKeyValuePairsAndExit,
        kvpairs=vm_profiles,
        kvpair_help_prefix="VM profiles:",
        kvpair_help_suffix="",
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


def main_impl() -> None:
    """Top level program logic for the `tk` command"""
    parser = makeparser()
    parsed = parser.parse_args()

    #### Early setup
    conhandler = logging.StreamHandler()
    conhandler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    tklogger.addHandler(conhandler)
    if parsed.debug:
        print(f"Arguments: {parsed}")
        sys.excepthook = idb_excepthook
    if parsed.verbose:
        tklogger.setLevel(logging.DEBUG)

    #### Handle stuff that needs to be done for multiple subcommands

    _build_container_cms: dict[str, AlpineDockerBuilder] = {}
    """Keep a cache of build container context managers"""

    def getbldcm(arch: Architecture):
        """Get a build container context manager"""
        if arch.name not in _build_container_cms:
            _build_container_cms[arch.name] = get_configured_docker_builder(
                arch, parsed.interactive, parsed.clean, parsed.dangerous_no_clean_tmp_dir
            )
        return _build_container_cms[arch.name]

    def mkimage_prepare(architecture: Architecture):
        """Do common setup for mkimage commands"""
        builder = getbldcm(architecture)
        aports.validate_alpine_version(
            tkconfig.repopaths.buildcontainer, tkconfig.repopaths.aports, tkconfig.alpine_version
        )

        # Make sure we have an up-to-date Docker builder
        build_container(
            tkconfig.buildcontainer.build_container_tag(architecture),
            tkconfig.repopaths.buildcontainer.as_posix(),
            f"linux/{builder.architecture.docker}",
            rebuild=parsed.rebuild,
        )

        # Build the APKs that are also included in the ISO
        # Building them here makes sure that they are up-to-date
        # and especially that they're built on the right Python version
        # (Different Alpine versions use different Python versions,
        # and if the latest APK doesn't match what's installed on the new ISO,
        # it will fail.)
        if not parsed.skip_build_apks:
            abuild_blacksite(builder)
            abuild_psyopsOS_base(builder)
            build_neuralupgrade_apk(builder)

    #### Early argument validation
    try:
        interactive = parsed.interactive
    except AttributeError:
        interactive = False
    if interactive and len(parsed.platform) > 1:
        parser.error("Can't run an interactive build container for multiple architectures at once")
    # architectures = [all_architectures[arch] for arch in parsed.architecture]
    # bootsystem = [BOOTSYSTEMS[bs] for bs in parsed.bootsystem]
    platforms = [PLATFORMS[plat] for plat in parsed.platform]
    architectures = set(plat.architecture for plat in platforms)

    #### Main logic

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
            for arch in architectures:
                platform = f"linux/{arch.docker}"
                build_container(
                    tkconfig.buildcontainer.build_container_tag(arch),
                    tkconfig.repopaths.buildcontainer.as_posix(),
                    platform,
                    rebuild=parsed.rebuild,
                )
        elif parsed.builder_action == "runcmd":
            for arch in architectures:
                with getbldcm(arch) as builder:
                    builder.run_docker_raw(parsed.command)
        else:
            parser.error(f"Unknown builder action: {parsed.builder_action}")
    elif parsed.action == "mkimage":
        if parsed.mkimage_action == "iso":
            for plat in platforms:
                mkimage_prepare(plat.architecture)
                with getbldcm(plat.architecture) as builder:
                    mkimage_iso(plat.architecture, builder)
        elif parsed.mkimage_action == "diskimg":
            initdir = tkconfig.repopaths.root / "psyopsOS" / "osbuild" / "initramfs-init"
            init_patch = initdir / "initramfs-init.patch"
            if "mkinitpatch" in parsed.stages:
                with init_patch.open("w") as f:
                    diffresult = subprocess.run(
                        ["diff", "-u", "initramfs-init.orig", "initramfs-init.patched"],
                        cwd=initdir,
                        check=False,
                        stdout=f,
                    )
                    # Diff returns 0 if the files are the same, 1 if they are different, and >1 if there was an error
                    if diffresult.returncode == 0:
                        tklogger.debug("initramfs-init.patched was the same as initramfs-init.orig")
                    elif diffresult.returncode == 1:
                        tklogger.debug("initramfs-init.patched was different from initramfs-init.orig")
                    else:
                        tklogger.error(f"diff returned {diffresult.returncode}")
                        sys.exit(1)
            if "applyinitpatch" in parsed.stages:
                subprocess.run(
                    ["patch", "-o", "initramfs-init.patched", "initramfs-init.orig", init_patch.as_posix()],
                    cwd=initdir,
                    check=True,
                )
            if "kernel" in parsed.stages:
                for arch in architectures:
                    mkimage_prepare(arch)
                    with getbldcm(arch) as builder:
                        make_kernel(builder)
            if "squashfs" in parsed.stages:
                for arch in architectures:
                    mkimage_prepare(arch)
                    with getbldcm(arch) as builder:
                        make_squashfs(builder)
            if "ostar" in parsed.stages:
                for arch in architectures:
                    make_ostar(arch)
            if "ostar-dd" in parsed.stages:
                for arch in architectures:
                    copy_ostar_to_deaddrop(arch)
            if "efisystar" in parsed.stages:
                for plat in platforms:
                    with getbldcm(plat.architecture) as builder:
                        make_boot_tar(plat, builder)
            if "efisystar-dd" in parsed.stages:
                for plat in platforms:
                    copy_esptar_to_deaddrop(plat)
            if "sectar" in parsed.stages and parsed.node_secrets:
                subprocess.run(
                    [
                        "progfiguration-blacksite-node",
                        "save",
                        parsed.node_secrets,
                        "--outtar",
                        tkconfig.noarch_artifacts.node_secrets(parsed.node_secrets),
                        "--force",
                    ],
                )
            if "diskimg" in parsed.stages:
                for plat in platforms:
                    arch = plat.architecture
                    mkimage_prepare(plat.architecture)
                    out_filename = tkconfig.arch_artifacts[arch.name].node_image(plat).name
                    secrets_tarball = ""
                    if parsed.node_secrets:
                        out_filename = tkconfig.arch_artifacts[arch.name].node_image(plat, parsed.node_secrets).name
                        secrets_tarball = tkconfig.noarch_artifacts.node_secrets(parsed.node_secrets).as_posix()
                    with getbldcm(arch) as builder:
                        make_boot_image(plat, out_filename, builder, secrets_tarball=secrets_tarball)
        else:
            parser.error(f"Unknown mkimage action: {parsed.mkimage_action}")
    elif parsed.action == "vm":
        # TODO: handle architecture
        if len(architectures) > 1:
            parser.error("Can't run multiple VMs at once")
        arch = list(architectures)[0]
        if parsed.vm_action == "diskimg":
            get_x64_ovmf()
            diskimg = parsed.disk_image
            if not diskimg:
                diskimg = tkconfig.arch_artifacts[arch.name].node_image(PLATFORMS["x86_64-uefi"])
            vm_diskimg(arch, diskimg, parsed.macaddr)
        elif parsed.vm_action == "osdir":
            vm_osdir(arch)
        elif parsed.vm_action == "profile":
            if parsed.profile == "qreamsqueen":
                get_x64_ovmf()
                img_path = tkconfig.arch_artifacts[arch.name].node_image(PLATFORMS["x86_64-uefi"], "qreamsqueen")
                vm_diskimg(arch, img_path, "ac:ed:de:ad:be:ef")
            else:
                parser.error(f"Unknown profile: {parsed.profile}")
        else:
            parser.error(f"Unknown vm action: {parsed.vm_action}")
    elif parsed.action == "buildpkg":
        # arch-specific packages
        for arch in architectures:
            builder = getbldcm(arch)
            if "base" in parsed.package:
                abuild_psyopsOS_base(builder)
            if "blacksite" in parsed.package:
                abuild_blacksite(builder)
            if "neuralupgrade-apk" in parsed.package:
                build_neuralupgrade_apk(builder)
        # no-arch packages
        if "neuralupgrade-pyz" in parsed.package:
            build_neuralupgrade_pyz()
    elif parsed.action == "deployos":
        if len(architectures) > 1:
            parser.error("Can't deploy to multiple architectures at once")
        arch = list(architectures)[0]
        if parsed.deploy_type == "iso":
            raise NotImplementedError("Deploying ISO images is not implemented")
        elif parsed.deploy_type == "diskimg":
            deploy_ostar(parsed.host, tkconfig.arch_artifacts[arch.name].ostar_path)
        else:
            parser.error(f"Unknown deployment type: {parsed.deploy_type}")
    elif parsed.action == "psynet":
        if parsed.psynet_action == "run":
            if parsed.cadir:
                os.makedirs(parsed.cadir, exist_ok=True)
            with tksecrets.psynetca(parsed.cadir) as cadir:
                subprocess.run(parsed.command, cwd=cadir, check=True)
        elif parsed.psynet_action == "get":
            crt = tksecrets.gopass_get(f"psynet/{parsed.node}.crt")
            key = tksecrets.gopass_get(f"psynet/{parsed.node}.key")
            print(f"Certificate for {parsed.node}:")
            print(crt)
            print(f"Key for {parsed.node}:")
            print(key)
        elif parsed.psynet_action == "set":
            tksecrets.gopass_set(parsed.crt, f"psynet/{parsed.node}.crt")
            tksecrets.gopass_set(parsed.key, f"psynet/{parsed.node}.key")
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
