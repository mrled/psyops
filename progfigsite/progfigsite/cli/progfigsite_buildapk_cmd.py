"""Build an APK for the progfigsite.

This is not part of the progfiguration API,
just a convenient place to put a build script.

This script isn't available when running from a zipapp.
"""


import argparse
import importlib.resources
from pathlib import Path
import sys

from progfiguration.cli.util import idb_excepthook
from progfiguration.cmd import magicrun
from progfiguration.progfigbuild import InjectedFile, ProgfigsitePythonPackagePreparer
from progfiguration.temple import Temple

import progfigsite
import progfigsite.sitelib.buildsite


def main():
    """Build progfigsite"""

    parser = argparse.ArgumentParser(
        description="Build APK for progfigsite",
        epilog=(
            "This script is not part of the progfiguration API, just a convenient place to put a build script.",
            "This script must be run from our build environment, which is the psyops container with decrypted secrets.",
        ),
    )
    parser.add_argument(
        "--debug",
        "-d",
        action="store_true",
        help="Open the debugger if an unhandled exception is encountered",
    )
    parser.add_argument(
        "--apks-index-path",
        default="/psyops/psyopsOS/public/apk",
        help="Path to the APK index in the build container",
    )
    parser.add_argument(
        "--abuild-repo-name",
        default="psyopsOS",
        help="Name of the Alpine repository where the package will be created",
    )
    parser.add_argument("--clean", action="store_true", help="Clean before building")
    parsed = parser.parse_args()

    if parsed.debug:
        sys.excepthook = idb_excepthook

    # Note: We don't use the injection mechanism here,
    # because we have to define injections before entering the context manager,
    # and we don't know the version until we enter the context manager.
    apkbuild_path = Path("./APKBUILD")
    apkbuild_temple_path = importlib.resources.files(progfigsite.sitelib.buildsite).joinpath("APKBUILD.temple")
    with apkbuild_temple_path.open() as f:
        apkbuild_temple = Temple(f.read())

    with ProgfigsitePythonPackagePreparer(Path(progfigsite.__file__).parent) as preparer:

        try:

            # Add the APK build file to the package
            apkbuild_hydrated = apkbuild_temple.substitute(version=preparer.minted_version)
            with apkbuild_path.open("w") as f:
                f.write(apkbuild_hydrated)

            if parsed.clean:
                magicrun("abuild clean")

            magicrun(["abuild", "-P", parsed.apks_index_path, "-D", parsed.abuild_repo_name])

        finally:

            # Remove the APK build file from the package
            try:
                apkbuild_path.unlink()
            except Exception:
                raise RuntimeError(
                    f"Failed to remove {apkbuild_path}, take care to remove it manually and please don't commit it to source control."
                )
