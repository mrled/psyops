"""A get_version() function.

get_version() used to get the current package version,
at both runtime and build time.
"""


import os
from pathlib import Path
import sys


def get_version() -> str:
    """Dynamically get the package version

    In pyproject.toml, this function is used to set the package version.
    That means it must return the correct value in multiple contexts.

    building a package (e.g. with `python -m build`)
        First look for ``progfigsite.builddata.version``,
        which will have been injected at build time by
        `progfiguration.progfigbuild.ProgfigsitePythonPackagePreparer`.
        If that fails, fall back to the default value returned by this function,

    installing from a built package (e.g. a .tar.gz or .whl)
        Use ``progfigsite.builddata.version`` as above.
        This should always be present for a built package.

    installing from source (e.g. with `pip install -e .`)
        Use the default value returned by this function,
        which a very low version number.
        ``progfigsite.builddata.version`` should never be present in this case.
    """

    def dbgprint(msg: str) -> None:
        """A stupid debug print function

        If the version is returning the wrong information,
        for instance if you're running it inside a
        `progfiguration.progfigbuild.ProgfigsitePythonPackagePreparer`
        but it's still returning the default function,
        you can set the environment variable ``PROGFIGSITE_VERSION_DEBUG`` to any value
        and see the module paths and any error messages.
        """
        red = "\033[91m"
        endc = "\033[00m"
        if os.environ.get("PROGFIGSITE_VERSION_DEBUG", ""):
            print(f"{red}{__file__}:get_version(): {msg}{endc}", file=sys.stderr)

    try:
        from progfiguration import sitewrapper

        # With ``sitewrapper``, we can set the progfigsite module one of two ways:
        #
        # 1.    By module name, e.g. "progfiguration_blacksite"
        #       with sitewrapper.set_progfigsite_by_module_name().
        #       This looks for a module already in ``sys.path``.
        # 2.    By filesystem path to the root module, e.g. Path(__file__).parent
        #       with sitewrapper.set_progfigsite_by_filepath().
        #       This looks for a module in a specific location, whether its in ``sys.path`` or not.
        #
        # We need the second behavior, because
        # when we build this package in Docker, we do the following:
        #
        # 1.    Mount the source directory as a volume in the container.
        # 2.    Install the package as editable from the source directory, placing it in ``sys.path``
        # 3.    Copy the source directory to a temporary directory.
        #       We do this because APK packages use the parent's parent directory as the repository name,
        #       and we don't want to have to know the name of the parent directory.
        # 4.    Inject the version data into the copy in the temporary directory --
        #       but not the copy that we installed with Pip.
        # 5.    Run ``abuild`` from the temporary directory.
        #       We need it to find the version data in the temporary directory.
        sitewrapper.set_progfigsite_by_filepath(
            Path(__file__).parent, "progfiguration_blacksite"
        )

        builddata_version = sitewrapper.site_submodule("builddata.version")
        dbgprint(
            f"Found injected version data: {builddata_version.version}, {builddata_version.builddate}"
        )
        return builddata_version.version
    except Exception as exc:
        dbgprint(f"Could not import injected version data: {exc}")
        default_version = "0.0.1a0"
        dbgprint(
            f"Could not import directly imported version data: {exc}; returning default version of {default_version}"
        )
        return default_version
