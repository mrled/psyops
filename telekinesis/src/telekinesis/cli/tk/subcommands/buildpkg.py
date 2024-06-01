"""The buildpkg subcommand"""

import subprocess
from typing import Optional

from telekinesis.alpine_docker_builder import AlpineDockerBuilder, get_configured_docker_builder
from telekinesis.config import tkconfig


def abuild_psyopsOS_package(
    package: str,
    builder: AlpineDockerBuilder,
    setupcmds: Optional[list[str]] = None,
):
    """Build a psyopsOS APK package in the mkimage docker container.

    The package should be in the psyopsOS/abuild/psyopsOS directory.
    Sign with the psyopsOS key.

    Arguments:
    package: The name of the package to build.
    setupcmds: A list of commands to run before building the package.
    """
    setupcmds = setupcmds or []
    with builder:
        apkindexpath = builder.in_container_apks_repo_root + f"/v{tkconfig.alpine_version}"
        # Place the apk repo inside the public dir, this means that 'invoke deploy' will copy it
        in_container_package_path = f"{builder.in_container_psyops_checkout}/psyopsOS/abuild/psyopsOS/{package}"
        in_container_build_cmd = [
            *builder.docker_shell_commands,
            *setupcmds,
            f"cd '{in_container_package_path}'",
            f"abuild checksum",
            f"abuild -r -P {apkindexpath} -D {tkconfig.buildcontainer.apkreponame}",
        ]
        builder.run_docker(in_container_build_cmd)


# TODO: can the blacksite apk package be built with build_psyopsOS_apk()?
def abuild_blacksite(builder: AlpineDockerBuilder):
    """Build the progfiguration psyops blacksite Python package as an Alpine package. Use the mkimage docker container."""

    with builder:
        apkindexpath = builder.in_container_apks_repo_root + f"/v{tkconfig.alpine_version}"
        apkrepopath = apkindexpath + "/" + tkconfig.buildcontainer.apkreponame

        in_container_build_cmd = [
            # We can't use venv because Alpine packages won't build that way since they switched to gpep517.
            # (We don't use gpep517, but before they switched, we could do this in a venv.)
            f"cd {builder.in_container_psyops_checkout}/progfiguration_blacksite",
            # This installs progfiguration as editable from our local checkout.
            # It means we don't have to install it over the network,
            # and it also lets us test local changes to progfiguration.
            f"pip install --break-system-packages -e {builder.in_container_psyops_checkout}/submod/progfiguration",
            # This will skip the progfiguration dependency as it is already installed.
            "pip install --break-system-packages -e .",
            f"progfiguration-blacksite-buildapk --abuild-repo-name {tkconfig.buildcontainer.apkreponame} --apks-index-path {apkindexpath}",
            f"echo 'Build packages are found in {apkrepopath}/x86_64/:'",
            f"ls -larth {apkrepopath}/{builder.architecture.mkimage}/",
        ]

        builder.run_docker(in_container_build_cmd)


def abuild_psyopsOS_base(builder: AlpineDockerBuilder):
    """Build the psyopsOS-base Alpine package"""
    setupcmds = [
        # grub-efi package is broken in Docker.
        # If we don't remove it we get a failure like this trying to run abuild:
        #     >>> psyopsOS-base: Analyzing dependencies...
        #     >>> ERROR: psyopsOS-base: builddeps failed
        #     >>> psyopsOS-base: Uninstalling dependencies...
        #     ERROR: No such package: .makedepends-psyopsOS-base
        "sudo apk update",
        "sudo apk del grub-efi",
        "sudo apk fix",
    ]
    abuild_psyopsOS_package("psyopsOS-base", builder, setupcmds=setupcmds)


def build_neuralupgrade_pyz():
    """Build the neuralupgrade package zipapp package"""
    srcroot = tkconfig.repopaths.neuralupgrade / "src"
    subprocess.run(
        [
            "python",
            "-m",
            "zipapp",
            "--main",
            "neuralupgrade.cmd:main",
            "--output",
            tkconfig.noarch_artifacts.neuralupgrade,
            "--python",
            "/usr/bin/env python3",
            srcroot.as_posix(),
        ],
        check=True,
    )


def build_neuralupgrade_apk(builder):
    """Build the neuralupgrade APK package"""
    abuild_psyopsOS_package("neuralupgrade", builder)
