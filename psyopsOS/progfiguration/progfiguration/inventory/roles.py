"""Applying and working with roles"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from importlib.resources import files as importlib_resources_files
from typing import Any, Dict, List, Optional

from progfiguration import age
from progfiguration.inventory import Inventory
from progfiguration.localhost import LocalhostLinuxPsyopsOs


@dataclass
class ProgfigurationRole(ABC):
    """A role that can be applied to a node

    Required attributes:

    * name: The name of the role
    * localhost: A localhost object
    * inventory: An inventory object

    Optional attributes:

    * rolepkg: The package that the role is defined in,
        used to determine the path to the role's templates,
        which you can set from the role's __init__.py by setting 'rolepkg = __package__'
    * defaults: A dict of default arguments for the role
    * appends: A list of arguments that should be appended to, rather than replaced
    * constants: A dict of constants that should be available to the role

    Required methods:

    * apply(): Apply the role to the node

    Optional methods:

    * results(): Return a dict of results that may be used by other roles
    """

    name: str
    localhost: LocalhostLinuxPsyopsOs
    inventory: Inventory

    defaults: Dict[str, Any] = field(default_factory=dict)
    appends: List[str] = field(default_factory=list)
    constants: Dict[str, Any] = field(default_factory=dict)
    rolepkg: Optional[str] = None
    _rolefiles: Optional[Any] = None

    @abstractmethod
    def apply(self, **kwargs):
        pass

    def results(self, **kwargs):
        return {}

    def role_file(self, filename: str) -> str:
        """Get the path to a file in the role's package

        TODO: convert to using importlib.resources.as_file, which I think works inside a zip file or anywhere
        """
        if not self.rolepkg:
            raise NotImplementedError("rolepkg must be set to use package_file()")
        if not self._rolefiles:
            self._rolefiles = importlib_resources_files(self.rolepkg)
        return self._rolefiles.joinpath(filename)


_coalescence_cache = {}


def _coalesce_node_roles_arguments(inventory: Inventory, nodename: str) -> Dict[str, tuple[ProgfigurationRole, dict]]:
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
        role = inventory.role(rolename)

        # If the role module itself has defaults, set them
        rolevars = {}
        rolevars.update(role.defaults)

        # The role module may define some values as "appends",
        # which means that they cannot be overridden by groups/nodes, only appended to.
        appendvars = role.appends
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

        applyroles[rolename] = (role, rolevars)

    return applyroles


def coalesce_node_roles_arguments(inventory: Inventory, nodename: str):
    """Coalesce a node's role arguments from groups and nodes into a single dict

    We find role arguments in the following order:

    * Defaults for the role
    * The universal group
    * The node's groups (in unspecified order - do not rely on conflicting group arguments)
    * The node itself

    Returns a dict of {rolename: (rolemodule, roleargs)}
    """

    # We cache the results of this function so that roles can call it many times
    if nodename not in _coalescence_cache:
        _coalescence_cache[nodename] = _coalesce_node_roles_arguments(inventory, nodename)

    return _coalescence_cache[nodename]


def get_role_results(localhost: LocalhostLinuxPsyopsOs, inventory: Inventory, nodename: str, rolename: str):
    """Get the results of applying roles to a node

    Results are static or simple-to-calculate values that may be used by other roles.
    """
    rolemod, roleargs = coalesce_node_roles_arguments(inventory, nodename)[rolename]
    if "results" not in dir(rolemod):
        return {}
    return rolemod.results(localhost, **roleargs)
