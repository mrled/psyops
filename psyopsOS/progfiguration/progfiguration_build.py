"""The progfiguration build script

We support building for the following circumstances:
- Building this package as standalone for Alpine Linux.
  psyopsOS is based on Alpine, and the Alpine package manager is extremely fast.
- Having the package build itself, for the remoteapply subcommand.
  This way the package can be installed locally, and told to build itself and install itself remotely on managed nodes.
"""

import datetime
import os
import pathlib
import string
import stat
import subprocess
import textwrap
import zipfile


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
    """Build a .pyz file

    Zip up the contents of PROGFIGURATION_ROOT.
    Place them inside a subdirectory called 'progfigruation'.
    Add a __main__.py file to the root of the zip file.

    We have to do this because the zipapp module does not allow us to specify
    the subdirectory name.
    When our program does "from progfiguration import ...",
    it will look for a directory called 'progfiguration' in the zip file.

    Inspired by the zipapp module code
    <https://github.com/python/cpython/blob/3.11/Lib/zipapp.py>

    TODO: go into more detail in documentation as to why this is required, with examples.
    """

    outfile = pathlib.Path(outfile)
    modulebase = pathlib.Path(PROGFIGURATION_ROOT)

    # Set this to zipfile.ZIP_DEFLATED to compress the output
    compression = zipfile.ZIP_STORED

    # This is the __main__.py that will be in the root of the zip file
    # By default, zipapp will create something like this:
    #
    # r"""
    # # -*- coding: utf-8 -*-
    # import cli.progfiguration
    # cli.progfiguration.main()
    # """
    #
    # We want to be able to import progfiguration from the root of the zip file
    # so we have to do this:
    main_py = textwrap.dedent(
        r"""
        from progfiguration.cli import progfiguration_cmd
        progfiguration_cmd.main()
        """
    )

    with open(outfile, "wb") as fp:
        # Writing a shebang like this is optional in zipapp,
        # but there's no reason not to since it's a valid zip file either way.
        fp.write(b"#!/usr/bin/env python3\n")

        with zipfile.ZipFile(fp, "w", compression=compression) as z:
            for child in modulebase.rglob("*"):
                if child.name == "__pycache__":
                    continue
                arcname = child.relative_to(modulebase)
                z.write(child, "progfiguration/" + arcname.as_posix())
            z.writestr("__main__.py", main_py.encode("utf-8"))

    outfile.chmod(outfile.stat().st_mode | stat.S_IEXEC)
