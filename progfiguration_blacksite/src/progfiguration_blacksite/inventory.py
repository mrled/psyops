"""Site configuration goes here"""

from datetime import datetime, UTC
import os

from progfiguration import sitewrapper
from progfiguration.sitehelpers import siteversion
from progfiguration.sitehelpers.invconf import hosts_conf, secrets_conf

sitewrapper.set_progfigsite_by_module_name("progfiguration_blacksite")

hoststore = hosts_conf("inventory.conf")

secretstore = secrets_conf("inventory.conf")


def mint_version() -> str:
    """Mint a new version number

    Similar to progfiguration.sitehelpers.siteversion.mint_version_factory_from_epoch,
    but allow overriding the epoch via an environment variable PROGFIGURATION_BLACKSITE_OVERRIDE_EPOCH.
    We use this to set a known version in the CI/CD pipeline.

    Get a good value like `date +%s` in bash,
    or in a quick Python one-liner like
    `import datetime as d; print(int(d.datetime.now(d.UTC).timestamp()))`.

    The results of this function should match the pkgver set in the APKBUILD file.
    """

    major = 1
    minor = 0
    if "PROGFIGURATION_BLACKSITE_OVERRIDE_EPOCH" in os.environ:
        epoch = os.environ["PROGFIGURATION_BLACKSITE_OVERRIDE_EPOCH"]
    else:
        dt = datetime.now(UTC)
        epoch = int(dt.timestamp())
    version = f"{major}.{minor}.{epoch}"
    return version
