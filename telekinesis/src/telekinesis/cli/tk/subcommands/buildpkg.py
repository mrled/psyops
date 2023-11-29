"""The buildpkg subcommand"""

import os
import string
import time

from telekinesis.alpine_docker_builder import get_configured_docker_builder
from telekinesis.config import tkconfig


def abuild_blacksite(interactive: bool, cleandockervol: bool, dangerous_no_clean_tmp_dir: bool):
    """Build the progfiguration psyops blacksite Python package as an Alpine package. Use the mkimage docker container."""

    with get_configured_docker_builder(interactive, cleandockervol, dangerous_no_clean_tmp_dir) as builder:
        apkindexpath = builder.in_container_apks_repo_root + f"/v{tkconfig.alpine_version}"
        apkrepopath = apkindexpath + "/" + tkconfig.buildcontainer.apkreponame

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
            f"progfiguration-blacksite-buildapk --abuild-repo-name {tkconfig.buildcontainer.apkreponame} --apks-index-path {apkindexpath}",
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

    with (tkconfig.repopaths.psyopsOS_base / "APKBUILD.template").open() as fp:
        apkbuild_template = string.Template(fp.read())
    apkbuild_contents = apkbuild_template.substitute(version=version)
    apkbuild_path = os.path.join(tkconfig.repopaths.psyopsOS_base, "APKBUILD")

    try:
        with open(apkbuild_path, "w") as afd:
            afd.write(apkbuild_contents)
        print("Running build in progfiguration directory...")
        with get_configured_docker_builder(interactive, cleandockervol, dangerous_no_clean_tmp_dir) as builder:
            apkindexpath = builder.in_container_apks_repo_root + f"/v{tkconfig.alpine_version}"
            apkrepopath = apkindexpath + "/" + tkconfig.buildcontainer.apkreponame

            # Place the apk repo inside the public dir
            # This means that 'invoke deploy' will copy it
            abuild_cmd = f"abuild -r -P {apkindexpath} -D {tkconfig.buildcontainer.apkreponame}"

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
