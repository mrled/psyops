"""Site configuration goes here

This includes everything that is not generic to how progfiguration works,
but is specific to my hosts/roles/groups/functions/etc.
"""

from importlib.resources import files as importlib_resources_files


package_inventory_file = importlib_resources_files("progfigsite").joinpath("inventory.yml")
