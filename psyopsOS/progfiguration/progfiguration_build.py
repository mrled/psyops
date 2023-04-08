"""The progfiguration build script

We support building for the following circumstances:
- Building this package as standalone for Alpine Linux.
  psyopsOS is based on Alpine, and the Alpine package manager is extremely fast.
- Having the package build itself, for the remoteapply subcommand.
  This way the package can be installed locally, and told to build itself and install itself remotely on managed nodes.
"""

import datetime
import os
import string
import subprocess
import textwrap
import zipapp


PKG_ROOT = os.path.dirname(__file__)
PROGFIGURATION_ROOT = os.path.join(PKG_ROOT, "progfiguration")
PKG_VERSION_FILE = os.path.join(PROGFIGURATION_ROOT, "build_version.py")
APKBUILD_TEMPLATE = os.path.join(PKG_ROOT, "APKBUILD.template")
APKBUILD_FILE = os.path.join(PKG_ROOT, "APKBUILD")


def get_epoch_build_version(dt: datetime.datetime):
    """Return a version string based on the given datetime"""
    epochsecs = int(dt.timestamp())
    # version = dt.strftime("%Y%m%d.%H%M%S.0")
    version = f"1.0.{epochsecs}"
    return version


def set_build_version(dt: datetime.datetime):
    """Set the build version in the APKBUILD template and in the package itself.

    These files should not be added to git, take care.
    """
    version = get_epoch_build_version(dt)

    with open(APKBUILD_TEMPLATE) as fp:
        apkbuild_template = string.Template(fp.read())
    apkbuild_contents = apkbuild_template.substitute(version=version)
    with open(APKBUILD_FILE, "w") as fp:
        fp.write(apkbuild_contents)

    package_version_template = string.Template(
        textwrap.dedent(
            """\
            VERSION = '$version'
            DATE = '$date'
            """
        )
    )
    package_version_contents = package_version_template.substitute(version=version, date=dt)
    with open(PKG_VERSION_FILE, "w") as fp:
        fp.write(package_version_contents)


def build_alpine(apk_index_path: str, abuild_repodest: str = "psyopsOS", clean: bool = False):
    """Build progfiguration as an Alpine package

    apk_index_path:     A local APK index where the package will be created
    abuild_repodest:    Set REPODEST as the repository location for created packages
    """

    buildtime = datetime.datetime.now()

    try:
        set_build_version(buildtime)

        if clean:
            print(f"Cleaning build in progfiguration directory...")
            subprocess.run(["abuild", "clean"], cwd=PKG_ROOT)

        abuild = ["abuild", "-P", apk_index_path, "-D", abuild_repodest]
        print(f"Running build in progfiguration directory with command: {abuild}")
        subprocess.run(abuild, cwd=PKG_ROOT)
    finally:
        failed = False
        if os.path.exists(PKG_VERSION_FILE):
            try:
                os.unlink(PKG_VERSION_FILE)
            except:
                failed = True
        if os.path.exists(APKBUILD_FILE):
            try:
                os.unlink(APKBUILD_FILE)
            except:
                failed = True
        if failed:
            raise Exception(
                f"When trying to remove version file and/or ABKBUILD, got an exception. Manually remove these two files, if they exist: {PKG_VERSION_FILE}, {APKBUILD_FILE}"
            )
    return get_epoch_build_version(buildtime)


def build_zipapp(outfile: str):
    """Build a .pyz file with the zipapp module"""
    zipapp.create_archive(source=PROGFIGURATION_ROOT, target=outfile, main="cli.progfiguration:main")
