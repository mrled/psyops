"""Site configuration goes here"""

from progfiguration import sitewrapper
from progfiguration.sitehelpers import siteversion
from progfiguration.sitehelpers.invconf import hosts_conf, secrets_conf

sitewrapper.set_progfigsite_by_module_name("progfiguration_blacksite")

hoststore = hosts_conf("inventory.conf")

secretstore = secrets_conf("inventory.conf")

mint_version = siteversion.mint_version_factory_from_epoch(major=1, minor=0)
