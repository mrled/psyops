"""Applying and working with roles"""

from progfiguration import age
from progfiguration.inventory import Inventory


def coalesce_node_roles_arguments(inventory: Inventory, nodename: str):
    """Coalesce a node's role arguments from groups and nodes into a single dict

    We find role arguments in the following order:

    * Defaults for the role
    * The universal group
    * The node's groups (in unspecified order - do not rely on conflicting group arguments)
    * The node itself

    Returns a dict of {rolename: (rolemodule, roleargs)}
    """

    node = inventory.node(nodename).node

    groupmods = {}
    for groupname in inventory.node_groups[nodename]:
        groupmods[groupname] = inventory.group(groupname)

    applyroles = {}
    for rolename in inventory.node_roles(nodename):
        rolemodule = inventory.role(rolename)

        # If the role module itself has defaults, set them
        rolevars = {}
        if hasattr(rolemodule, "defaults"):
            rolevars.update(rolemodule.defaults)

        # The role module may define some values as "appends",
        # which means that they cannot be overridden by groups/nodes, only appended to.
        appendvars = []
        if hasattr(rolemodule, "appends"):
            appendvars = rolemodule.appends
            for append in appendvars:
                if append not in rolevars:
                    rolevars[append] = []

        # Apply role arguments from the universal group
        universal_gmod = inventory.group("universal")
        universal_rolevars = getattr(universal_gmod.group.roles, rolename, {})
        for key, value in universal_rolevars.items():
            unencrypted_value = value
            if isinstance(value, age.AgeSecretReference):
                secret = inventory.get_group_secrets("universal")[value.name]
                unencrypted_value = secret.decrypt()
            if key in appendvars:
                rolevars[key].append(unencrypted_value)
            else:
                rolevars[key] = unencrypted_value

        # Check each group that the node is in for role arguments
        for groupname, gmod in groupmods.items():
            group_rolevars = getattr(gmod.group.roles, rolename, {})
            for key, value in group_rolevars.items():
                unencrypted_value = value
                if isinstance(value, age.AgeSecretReference):
                    secret = inventory.get_group_secrets(groupname)[value.name]
                    unencrypted_value = secret.decrypt()
                if key in appendvars:
                    rolevars[key].append(unencrypted_value)
                else:
                    rolevars[key] = unencrypted_value

        # Apply any role arguments from the node itself
        node_rolevars = getattr(node.roles, rolename, {})
        for key, value in node_rolevars.items():
            unencrypted_value = value
            if isinstance(value, age.AgeSecretReference):
                secret = inventory.get_node_secrets(nodename)[value.name]
                unencrypted_value = secret.decrypt("/mnt/psyops-secret/mount/age.key")
            if key in appendvars:
                rolevars[key].append(unencrypted_value)
            else:
                rolevars[key] = unencrypted_value

        applyroles[rolename] = (rolemodule, rolevars)

    return applyroles
