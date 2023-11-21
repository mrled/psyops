"""The `tk` command"""


import argparse
import logging
import os
from pathlib import Path
import pdb
import pprint
import shlex
import string
import subprocess
import sys
import time
import traceback

from telekinesis.alpine_docker_builder import build_container, get_configured_docker_builder
from telekinesis import aports
from telekinesis import config
from telekinesis import deaddrop


def idb_excepthook(type, value, tb):
    """Call an interactive debugger in post-mortem mode"""
    if hasattr(sys, "ps1") or not sys.stderr.isatty():
        sys.__excepthook__(type, value, tb)
    else:
        traceback.print_exception(type, value, tb)
        print
        pdb.pm()


def mkimage(
    skip_build_apks: bool = False,
    rebuild: bool = False,
    interactive: bool = False,
    cleandockervol: bool = False,
    dangerous_no_clean_tmp_dir: bool = False,
):
    """Make a psyopsOS image"""

    alpine_version = config.tkconfig["alpine_version"]

    aports.validate_alpine_version(
        config.tkconfig["buildcontainer"]["builddir"],
        config.tkconfig["buildcontainer"]["aportsrepo"],
        alpine_version,
    )

    apkreponame = config.tkconfig["buildcontainer"]["apkreponame"]

    # Make sure we have an up-to-date Docker builder
    builder_tag = config.tkconfig["buildcontainer"]["tag_prefix"] + alpine_version
    build_container(builder_tag, config.tkconfig["buildcontainer"]["builddir"], rebuild)

    # Build the APKs that are also included in the ISO
    # Building them here makes sure that they are up-to-date
    # and especially that they're built on the right Python version
    # (Different Alpine versions use different Python versions,
    # and if the latest APK doesn't match what's installed on the new ISO,
    # it will fail.)
    if not skip_build_apks:
        abuild_blacksite(False, cleandockervol, dangerous_no_clean_tmp_dir)
        abuild_psyopsOS_base(False, cleandockervol, dangerous_no_clean_tmp_dir)

    with get_configured_docker_builder(interactive, cleandockervol, dangerous_no_clean_tmp_dir) as builder:
        apkindexpath = builder.in_container_apks_repo_root + f"/v{config.tkconfig['alpine_version']}"
        apkrepopath = apkindexpath + "/" + apkreponame
        in_container_mkimage_cmd_list = [
            " ".join(
                [
                    "sh",
                    "-x",
                    "./mkimage.sh",
                    "--tag",
                    config.tkconfig["buildcontainer"]["isotag"],
                    "--outdir",
                    builder.in_container_isodir,
                    "--arch",
                    config.tkconfig["buildcontainer"]["architecture"],
                    "--repository",
                    f"http://dl-cdn.alpinelinux.org/alpine/v{alpine_version}/main",
                    "--repository",
                    f"http://dl-cdn.alpinelinux.org/alpine/v{alpine_version}/community",
                    "--repository",
                    apkrepopath,
                    # This would also allow using the remote APK repo, but I don't think that's necessary any more?
                    # "--repository",
                    # apkpaths.uri,
                    "--workdir",
                    builder.in_container_workdir,
                    "--profile",
                    config.tkconfig["buildcontainer"]["mkimage_profile"],
                ]
            ),
        ]
        in_container_mkimage_cmd = " && ".join(in_container_mkimage_cmd_list)
        builder.run_docker([in_container_mkimage_cmd])
        for isofile in builder.isodir.glob("*.iso"):
            print(f"{isofile}")


def abuild_blacksite(interactive: bool, cleandockervol: bool, dangerous_no_clean_tmp_dir: bool):
    """Build the progfiguration psyops blacksite Python package as an Alpine package. Use the mkimage docker container."""

    with get_configured_docker_builder(interactive, cleandockervol, dangerous_no_clean_tmp_dir) as builder:
        apkreponame = config.tkconfig["buildcontainer"]["apkreponame"]
        apkindexpath = builder.in_container_apks_repo_root + f"/v{config.tkconfig['alpine_version']}"
        apkrepopath = apkindexpath + "/" + apkreponame

        in_container_build_cmd = [
            f"cd {builder.in_container_psyops_checkout}/progfiguration_blacksite",
            # This installs progfiguration as editable from our local checkout.
            # It means we don't have to install it over the network,
            # and it also lets us test local changes to progfiguration.
            f"pip install -e {builder.in_container_psyops_checkout}/submod/progfiguration",
            # This will skip progfiguration as it is already installed.
            "pip install -e '.[development]'",
            # TODO: remove this once we have a new enough setuptools in the container
            # Ran into this problem: <https://stackoverflow.com/questions/74941714/importerror-cannot-import-name-legacyversion-from-packaging-version>
            # I'm using an older Alpine container, 3.16 at the time of this writing, because psyopsOS is still that old.
            # When we can upgrade, we'll just use the setuptools in apk.
            "pip install -U setuptools",
            f"progfiguration-blacksite-buildapk --abuild-repo-name {apkreponame} --apks-index-path {apkindexpath}",
            f"echo 'Build packages are found in {apkrepopath}/x86_64/:'",
            f"ls -larth {apkrepopath}/x86_64/",
        ]

        builder.run_docker(in_container_build_cmd)


def abuild_psyopsOS_base(interactive: bool, cleandockervol: bool, dangerous_no_clean_tmp_dir: bool):
    """Build the psyopsOS-base Python package as an Alpine package. Use the mkimage docker container.

    Sign with the psyopsOS key.
    """
    epochsecs = int(time.time())
    version = f"1.0.{epochsecs}"

    apkreponame = config.tkconfig["buildcontainer"]["apkreponame"]
    psyopsOS_base_dir = config.tkconfig["buildcontainer"]["psyopsosbasedir"]

    with open(f"{psyopsOS_base_dir}/APKBUILD.template") as fp:
        apkbuild_template = string.Template(fp.read())
    apkbuild_contents = apkbuild_template.substitute(version=version)
    apkbuild_path = os.path.join(psyopsOS_base_dir, "APKBUILD")

    try:
        with open(apkbuild_path, "w") as afd:
            afd.write(apkbuild_contents)
        print("Running build in progfiguration directory...")
        with get_configured_docker_builder(interactive, cleandockervol, dangerous_no_clean_tmp_dir) as builder:
            apkindexpath = builder.in_container_apks_repo_root + f"/v{config.tkconfig['alpine_version']}"
            apkrepopath = apkindexpath + "/" + apkreponame

            # Place the apk repo inside the public dir
            # This means that 'invoke deploy' will copy it
            abuild_cmd = f"abuild -r -P {apkindexpath} -D {apkreponame}"

            in_container_build_cmd = builder.docker_shell_commands + [
                f"cd {builder.in_container_psyops_checkout}/psyopsOS/psyopsOS-base",
                # grub-efi package is broken in Docker.
                # If we don't remove it we get a failure like this trying to run abuild:
                #     >>> psyopsOS-base: Analyzing dependencies...
                #     >>> ERROR: psyopsOS-base: builddeps failed
                #     >>> psyopsOS-base: Uninstalling dependencies...
                #     ERROR: No such package: .makedepends-psyopsOS-base
                "sudo apk update",
                "sudo apk del grub-efi",
                "sudo apk fix",
                #
                f"abuild checksum",
                abuild_cmd,
                f"ls -larth {apkrepopath}/x86_64/",
            ]
            builder.run_docker(in_container_build_cmd)

    finally:
        try:
            os.unlink(apkbuild_path)
        except:
            raise Exception(f"When trying to remove ABKBUILD, got an exception. Manually remove: {apkbuild_path}")


def deployiso(host):
    """Deploy the ISO image to a remote host"""
    iso_filename = config.tkconfig["deaddrop"]["isofilename"]
    iso_path = config.tkconfig["deaddrop"]["isodir"] / iso_filename
    subprocess.run(["scp", iso_path.as_posix(), f"root@{host}:/tmp/{iso_filename}"], check=True)
    subprocess.run(["ssh", f"root@{host}", "/usr/sbin/psyopsOS-write-bootmedia", "/tmp/{iso_filename}"], check=True)


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

    return parser


def main():
    parser = makeparser()
    parsed = parser.parse_args()

    if parsed.debug:
        print(f"Arguments: {parsed}")
        logging.setLevel("DEBUG")
        sys.excepthook = idb_excepthook

    builder_tag = config.tkconfig["buildcontainer"]["tag_prefix"] + config.tkconfig["alpine_version"]

    if parsed.action == "showconfig":
        pprint.pprint(config.tkconfig, indent=2, sort_dicts=False)
    elif parsed.action == "deaddrop":
        aws_keyid = config.getsecret(config.tkconfig["deaddrop"]["onepassword_item"], "username")
        aws_secret = config.getsecret(config.tkconfig["deaddrop"]["onepassword_item"], "password")
        aws_sess = deaddrop.makesession(aws_keyid, aws_secret, config.tkconfig["deaddrop"]["region"])
        if parsed.deaddrop_action == "ls":
            deaddrop.list_files(aws_sess, config.tkconfig["deaddrop"]["bucketname"])
        elif parsed.deaddrop_action == "forcepull":
            deaddrop.s3_forcepull_directory(
                aws_sess, config.tkconfig["deaddrop"]["bucketname"], config.tkconfig["deaddrop"]["localpath"]
            )
        elif parsed.deaddrop_action == "forcepush":
            deaddrop.s3_forcepush_directory(
                aws_sess, config.tkconfig["deaddrop"]["bucketname"], config.tkconfig["deaddrop"]["localpath"]
            )
        else:
            parser.error(f"Unknown deaddrop action: {parsed.deaddrop_action}")
    elif parsed.action == "builder":
        if parsed.builder_action == "build":
            build_container(builder_tag, config.tkconfig["buildcontainer"]["builddir"], parsed.rebuild)
        elif parsed.builder_action == "runcmd":
            with get_configured_docker_builder(
                parsed.interactive, parsed.clean, parsed.dangerous_no_clean_tmp_dir
            ) as builder:
                builder.run_docker_raw(parsed.command)
        else:
            parser.error(f"Unknown builder action: {parsed.builder_action}")
    elif parsed.action == "mkimage":
        mkimage(
            skip_build_apks=parsed.skip_build_apks,
            rebuild=parsed.rebuild,
            interactive=parsed.interactive,
            cleandockervol=parsed.clean,
            dangerous_no_clean_tmp_dir=parsed.dangerous_no_clean_tmp_dir,
        )
    elif parsed.action == "buildpkg":
        if "base" in parsed.package:
            abuild_psyopsOS_base(parsed.interactive, parsed.clean, parsed.dangerous_no_clean_tmp_dir)
        if "blacksite" in parsed.package:
            abuild_blacksite(parsed.interactive, parsed.clean, parsed.dangerous_no_clean_tmp_dir)
    elif parsed.action == "deployiso":
        deployiso(parsed.host)
    else:
        parser.error(f"Unknown action: {parsed.action}")
