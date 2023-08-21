"""Site configuration goes here

This includes everything that is not generic to how progfiguration works,
but is specific to my hosts/roles/groups/functions/etc.
"""

import datetime
import os

from progfiguration import sitewrapper
from progfiguration.inventory.storeimpl.invconf import inventory_conf


site_name = "progfiguration_blacksite"

# A slogan from a USACAPOC psychological operations challenge coin I found online,
# whose provenance I did not investigate
site_description = "BECAUSE PHYSICAL WOUNDS HEAL"

sitewrapper.set_progfigsite_by_module_name(site_name)

hoststore, secretstore = inventory_conf(
    sitewrapper.site_submodule_resource("", "inventory.conf")
)


def mint_version() -> str:
    """Mint a new version number

    This function is called by progfiguration core to generate a version number.
    It should return a string that is a valid pip version number.
    """

    dt = datetime.datetime.utcnow()
    epoch = int(dt.timestamp())
    version = f"1.0.{epoch}"
    return version


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
        if os.environ.get("PROGFIGSITE_VERSION_DEBUG", "") != "":
            print(f"{__file__}.get_version(): {msg}")

    try:
        from progfiguration_blacksite.builddata import version  # type: ignore

        dbgprint(f"Returning {version.version} from {version.__file__}")
        return version.version
    except Exception as exc:
        default_version = "0.0.1a0"
        dbgprint(
            f"Could not import directly imported version data: {exc}; returning default version of {default_version}"
        )
        return default_version
