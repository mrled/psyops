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


# TODO: can the blacksite apk package be built with abuild_psyopsOS_package()?
def abuild_blacksite(builder: AlpineDockerBuilder):
    """Build the progfiguration psyops blacksite Python package as an Alpine package. Use the mkimage docker container."""

    with builder:
        apkindexpath = builder.in_container_apks_repo_root + f"/v{tkconfig.alpine_version}"
        in_container_site_dir = f"{builder.in_container_psyops_checkout}/progfiguration_blacksite"
        in_container_progfig_dir = f"{builder.in_container_psyops_checkout}/submod/progfiguration"
        in_container_abuild_pkg_dir = (
            f"{builder.in_container_psyops_checkout}/psyopsOS/abuild/psyopsOS/progfiguration_blacksite"
        )

        in_container_build_cmd = [
            # Create a venv for the build.
            # Note that installing the progfigsite into this venv
            # and then building it with setuptools will not work,
            # ever since Alpine switched to using gpep517.
            # (We don't use gpep517, but before they switched, we could do this in a venv.)
            # However, our progfigsite package will just contain the zipapp,
            # so using a venv here won't break anything.
            "python3 -m venv --system-site-packages /tmp/venv",
            "source /tmp/venv/bin/activate",
            # This installs progfiguration as editable from our local checkout.
            # It means we don't have to install it over the network,
            # and it also lets us test local changes to progfiguration.
            f"pip install -e {in_container_progfig_dir}",
            # This will skip installing the progfiguration dependency as it is already installed.
            f"pip install -e {in_container_site_dir}",
            # Build the zipapp and the APK package.
            f"cd {in_container_abuild_pkg_dir}",
            "progfiguration-blacksite zipapp ./progfiguration-blacksite",
            f"abuild -r -P {apkindexpath} -D {tkconfig.buildcontainer.apkreponame}",
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
