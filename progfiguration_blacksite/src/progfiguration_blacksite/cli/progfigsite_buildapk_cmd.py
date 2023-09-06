"""Build an APK for the progfigsite.

This is not part of the progfiguration API,
just a convenient place to put a build script.

This script isn't available when running from a zipapp.
"""


import argparse
import importlib.resources
import os
from pathlib import Path
import shutil
import sys
import tempfile

import progfiguration_blacksite
import progfiguration_blacksite.sitelib.buildsite
from progfiguration_blacksite.cli.progfigsite_shim import ensure_staticinclude


def parseargs():
    """Build progfigsite"""

    parser = argparse.ArgumentParser(
        description="Build APK for progfigsite",
        epilog=" ".join(
            [
                "This script is not part of the progfiguration API,",
                "just a convenient place to put a build script.",
                "This script must be run from our build environment,",
                "which is the psyops container with decrypted secrets.",
            ]
        ),
    )
    parser.add_argument(
        "--debug",
        "-d",
        action="store_true",
        help="Open the debugger if an unhandled exception is encountered.",
    )
    parser.add_argument(
        "--abuild-verbose",
        action="store_true",
        help="Print verbose output from abuild.",
    )
    parser.add_argument(
        "--keep-apkbuild",
        "-k",
        action="store_true",
        help="Keep the APK build file after building. Make sure not to commit it!",
    )
    default_apks_index_path = Path("/psyops/psyopsOS/public/apk")
    parser.add_argument(
        "--apks-index-path",
        type=Path,
        default=default_apks_index_path,
        help=f"Path to the APK index in the build container. Defaults to '{default_apks_index_path.as_posix()}'.",
    )
    default_abuild_repo_desc = "psyopsOS"
    parser.add_argument(
        "--abuild-repo-description",
        default="psyopsOS",
        help=f"Name of the Alpine repository where the package will be created. Defaults to '{default_abuild_repo_desc}'.",
    )
    default_abuild_repo_name = "psyopsOS"
    parser.add_argument(
        "--abuild-repo-name",
        default="psyopsOS",
        help=f"Name of the Alpine repository where the package will be created. Defaults to '{default_abuild_repo_name}'.",
    )
    default_pyproject_root = Path(
        progfiguration_blacksite.__file__
    ).parent.parent.parent
    parser.add_argument(
        "--pyproject-root",
        type=Path,
        default=default_pyproject_root,
        help=f"Path to the root of the pyproject.toml file. Defaults to '{default_pyproject_root.as_posix()}'. You won't need to override this if running from an editable install of a git checkout.",
    )
    parser.add_argument("--clean", action="store_true", help="Clean before building.")
    parsed = parser.parse_args()
    return parsed, parser


def main():
    parsed, parser = parseargs()

    if not (parsed.pyproject_root / "pyproject.toml").exists():
        raise RuntimeError(
            f"pyproject.toml not found at {parsed.pyproject_root}, please specify the path to the root of the pyproject.toml file with the --pyproject-root option. Note that you should generally be running this script from an editable install of a git checkout."
        )

    ensure_staticinclude()

    from progfiguration import logger, sitewrapper
    from progfiguration.cli.util import idb_excepthook
    from progfiguration.cmd import magicrun
    from progfiguration.progfigbuild import ProgfigsitePythonPackagePreparer
    from progfiguration.temple import Temple

    logger.setLevel("DEBUG")

    if parsed.debug:
        sys.excepthook = idb_excepthook

    progfigsite_package_root = Path(progfiguration_blacksite.__file__).parent

    sitewrapper.set_progfigsite_by_module_name("progfiguration_blacksite")

    # Abuild names the repo after the parent directory of the package root.
    # Apparently I can't change this.
    # This is set in the abuild script as "repo=".
    # <https://gitlab.alpinelinux.org/alpine/abuild/-/blob/f150027100d2488b318af935979c9b32ff420c71/abuild.in#L1022>
    # It corresponds to "main", "community", "testing" in the Alpine repository.
    # Even if I didn't want to make my own, I want to set it so that it's not whatever ../../ happens to be.
    #
    # See also psyopsOS/tasks/constants.py:ApkPaths
    #
    # So we're going to inflate the APKBUILD template in a temporary directory
    # whose parent is named abuild_repo_name.
    # The APKBUILD template will find the Python project from a path stored in
    # the environment variable $PROGFIGURATION_BLACKSITE_PROJECT_DIR.

    with tempfile.TemporaryDirectory() as tmpdir_str:
        tmpdir = Path(tmpdir_str)
        tmp_pyproj_root = (
            tmpdir / str(parsed.abuild_repo_name) / str(parsed.pyproject_root.name)
        )
        tmp_pyproj_root.mkdir(parents=True)

        # Note: We don't use the injection mechanism here,
        # because we have to define injections before entering the context manager,
        # and we don't know the version until we enter the context manager.
        tmp_apkbuild_path = tmp_pyproj_root / "APKBUILD"
        apkbuild_temple_path = importlib.resources.files(
            progfiguration_blacksite.sitelib.buildsite
        ).joinpath("APKBUILD.temple")
        with apkbuild_temple_path.open() as f:
            apkbuild_temple = Temple(f.read())

        with ProgfigsitePythonPackagePreparer(
            progfigsite_package_root, progfiguration_blacksite.site_name
        ) as preparer:

            # The preparer has dropped a version file at progfigsite/builddate/version.py
            # containing a version generated from progfigsite.mint_version().
            # We can access the version string in code from preparer.minted_version.
            #
            # pyproject.toml sets the version to a dynamic value from progfigsite.get_version().
            # That function reads the version from the version file,
            # and falls back to a low default version if the version file is missing.
            #
            # This means that things like 'python -m build' will find our minted version implicitly.
            # Inflate the APKBUILD template in the temporary directory
            apkbuild_hydrated = apkbuild_temple.substitute(
                version=preparer.minted_version
            )
            with tmp_apkbuild_path.open("w") as f:
                f.write(apkbuild_hydrated)

            # Add the APK build file to the package
            apkbuild_hydrated = apkbuild_temple.substitute(
                version=preparer.minted_version
            )
            with tmp_apkbuild_path.open("w") as f:
                f.write(apkbuild_hydrated)

            if parsed.clean:
                magicrun("abuild clean", cwd=tmp_pyproj_root.as_posix())

            abuild_cmd = ["abuild"]
            if parsed.abuild_verbose:
                abuild_cmd += ["-vv"]
            abuild_cmd += [
                "-P",
                parsed.apks_index_path.as_posix(),
                "-D",
                parsed.abuild_repo_description,
            ]

            print(f"Running {' '.join(abuild_cmd)}")

            abuild_env = os.environ.copy()
            progfigsite_project_root = progfigsite_package_root.parent.parent
            abuild_env["PROGFIGURATION_BLACKSITE_PROJECT_DIR"] = str(
                progfigsite_project_root
            )

            magicrun(
                abuild_cmd,
                cwd=tmp_pyproj_root.as_posix(),
                env=abuild_env,
            )
