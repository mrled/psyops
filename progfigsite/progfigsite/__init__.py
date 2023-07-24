"""Site configuration goes here

This includes everything that is not generic to how progfiguration works,
but is specific to my hosts/roles/groups/functions/etc.
"""

import datetime


site_name = "psyops progfigsite"

# A slogan from a USACAPOC psychological operations challenge coin I found online,
# whose provenance I did not investigate
site_description = "BECAUSE PHYSICAL WOUNDS HEAL"


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

    If we have version data injected at build time, retrieve that.
    Otherwise return a default version.
    """

    try:
        from progfigsite.builddata import version  # type: ignore

        return version.version
    except ImportError:
        return "0.0.1a0"
