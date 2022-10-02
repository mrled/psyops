"""The progfiguration build script

We support building for the following circumstances:
- Building this package as standalone for Alpine Linux.
  psyopsOS is based on Alpine, and the Alpine package manager is extremely fast.
- Having the package build itself, for the remoteapply subcommand.
  This way the package can be installed locally, and told to build itself and install itself remotely on managed nodes.
"""

# import argparse
import os
import string
import subprocess

# import sys
import time
from typing import List


PKG_ROOT = os.path.dirname(__file__)

PKG_VERSION_FILE = os.path.join(PKG_ROOT, "progfiguration", "build_version.py")
APKBUILD_TEMPLATE = os.path.join(PKG_ROOT, "APKBUILD.template")
APKBUILD_FILE = os.path.join(PKG_ROOT, "APKBUILD")


def get_epoch_build_version():
    # version = datetime.datetime.now().strftime("%Y%m%d.%H%M%S.0")
    epochsecs = int(time.time())
    version = f"1.0.{epochsecs}"
    return version


def set_build_version(version: str):
    """Set the build version in the APKBUILD template and in the package itself.

    These files should not be added to git, take care.
    """
    with open(APKBUILD_TEMPLATE) as fp:
        apkbuild_template = string.Template(fp.read())
    apkbuild_contents = apkbuild_template.substitute(version=version)

    with open(PKG_VERSION_FILE, "w") as fp:
        fp.write(f"VERSION = '{version}'\n")
    with open(APKBUILD_FILE, "w") as fp:
        fp.write(apkbuild_contents)


def build_alpine(apk_index_path: str, abuild_repodest: str = "psyopsOS"):
    """Build progfiguration as an Alpine package

    apk_index_path:     A local APK index where the package will be created
    abuild_repodest:    Set REPODEST as the repository location for created packages
    """

    version = get_epoch_build_version()

    try:
        set_build_version(version)
        abuild = ["abuild", "-P", apk_index_path, "-D", abuild_repodest]
        print(f"Running build in progfiguration directory with command: {abuild}")
        subprocess.run(abuild, cwd=PKG_ROOT)
    finally:
        failed = False
        try:
            os.unlink(PKG_VERSION_FILE)
        except:
            failed = True
        try:
            os.unlink(APKBUILD_FILE)
        except:
            failed = True
        if failed:
            raise Exception(
                f"When trying to remove version file and/or ABKBUILD, got an exception. Manually remove these two files, if they exist: {PKG_VERSION_FILE}, {APKBUILD_FILE}"
            )


# def main(arguments: List[str]) -> int:
#     parser = argparse.ArgumentParser(description="Build progfiguration")
#     subparsers = parser.add_subparsers(dest="action", required=True)
#     sub_build = subparsers.add_parser("build", description="Build the package")
#     sub_build.add_arugment("--apk-index-path", required=True, help="Path to ")
#     sub_save_version = subparsers.add_parser("save-version", description="Save the version files")
#     parsed = parser.parse_args()

#     if parsed.action == "build":
#         build_alpine(parsed.apk_index_path, parsed.abuild_repodest)


# if __name__ == "__main__":
#     sys.exit(main(*sys.argv))
