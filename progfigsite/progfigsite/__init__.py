"""Site configuration goes here

This includes everything that is not generic to how progfiguration works,
but is specific to my hosts/roles/groups/functions/etc.
"""

import importlib.resources


package_inventory_file = importlib.resources.files("progfigsite").joinpath("inventory.conf")
