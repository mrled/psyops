"""Site configuration goes here"""

from progfiguration import sitewrapper
from progfiguration.sitehelpers import siteversion
from progfiguration.sitehelpers.invconf import hosts_conf, secrets_conf

site_name = "progfiguration_blacksite"

# A slogan from a USACAPOC psychological operations challenge coin I found online,
# whose provenance I did not investigate
site_description = "BECAUSE PHYSICAL WOUNDS HEAL"

sitewrapper.set_progfigsite_by_module_name(site_name)

hoststore = hosts_conf("inventory.conf")

secretstore = secrets_conf("inventory.conf")

mint_version = siteversion.mint_version_factory_from_epoch(major=1, minor=0)
