"""Applying and working with roles"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from importlib.abc import Traversable
from importlib.resources import files as importlib_resources_files
from pathlib import Path
from typing import Any, Dict, List, Optional

from progfiguration import age
from progfiguration.inventory import Inventory
from progfiguration.localhost import LocalhostLinuxPsyopsOs


@dataclass
class RoleResultReference:
    """A reference to a result from a role

    This is used to allow roles to reference results from other roles
    """

    role: str
    result: str


@dataclass
class ProgfigurationRole(ABC):
    """A role that can be applied to a node

    Required attributes:

    * name: The name of the role
    * localhost: A localhost object
    * inventory: An inventory object
    * rolepkg: The package that the role is defined in,
        used to determine the path to the role's templates.

    Optional attributes:

    * defaults: A dict of default arguments for the role
    * appends: A list of arguments that should be appended to, rather than replaced
    * constants: A dict of constants that should be available to the role

    Required methods:

    * apply(): Apply the role to the node

    Optional methods:

    * results(): Return a dict of results that may be used by other roles

    Note that you cannot override properties in a subclass of a dataclass
    This means we can't have a default value for attributes like `defaults` and `appends`,
    and that we have to use .default_arguments and .argument_appends when we want to access them instead.
    """

    name: str
    localhost: LocalhostLinuxPsyopsOs
    inventory: Inventory
    rolepkg: str

    # This is just a cache
    _rolefiles: Optional[Any] = None

    @abstractmethod
    def apply(self, **kwargs):
        pass

    def results(self, **kwargs):
        return {}

    def role_file(self, filename: str) -> Traversable:
        """Get the path to a file in the role's package

        TODO: convert to using importlib.resources.as_file, which I think works inside a zip file or anywhere
        """
        if not self._rolefiles:
            self._rolefiles = importlib_resources_files(self.rolepkg)
        return self._rolefiles.joinpath(filename)

    @property
    def default_arguments(self):
        """Return the default arguments for the role's apply() method"""
        if hasattr(self, "defaults"):
            return self.defaults
        return {}

    @property
    def argument_appends(self):
        """Return the arguments that should be appended to, rather than replaced, by arguments defined on the group/node"""
        if hasattr(self, "appends"):
            return self.appends
        return []


_coalescence_cache = {}


def dereference_rolearg(
    argument: Any, inventory: Inventory, secrets: Dict[str, Any], append_to: Optional[List] = None
) -> Any:
    """Get the final value of a role argument

    Arguments to this method:

    * argument:     The role argument to get the final value of
    * inventory:    The inventory object
    * nodename:     The name of the node that the argument is being applied to
    * secrets:      A dict containing secrets we can decrypt
                    This might be from inventory.get_group_secrets(groupname) or inventory.get_node_secrets(nodename)
    * append_to:    If not None, append to this list and return the new list
                    This allows us to handle arguments that are "appends",
                    which means that they cannot be overridden by groups/nodes, only appended to.

    Role arguments are often used as-is, but some kinds of arguments are special:

    * age.AgeSecretReference: Decrypt the secret using the age key
    * RoleResultReference: Get the result from the referenced role

    This function retrieves the final value from these special argument types.
    Arguments that do not match one of these types are just returned as-is.
    """

    value = argument
    if isinstance(argument, age.AgeSecretReference):
        secret = secrets[argument.name]
        # TODO: don't use a hardcoded path for the key here
        value = secret.decrypt("/mnt/psyops-secret/mount/age.key")
    elif isinstance(argument, RoleResultReference):
        value = inventory.role(argument.role).results()[argument.result]
    if append_to is None:
        return value
    else:
        return append_to + [value]


def _coalesce_node_roles_arguments(inventory: Inventory, nodename: str) -> Dict[str, tuple[ProgfigurationRole, dict]]:
    """Coalesce a node's role arguments from groups and nodes into a single dict

    This is the implementation for the memoized coalesce_node_roles_arguments() function.

    Returns a dict of {rolename: (roleobject, roleargs)}
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
        rolevars.update(role.default_arguments)

        # The role module may define some values as "appends",
        # which means that they cannot be overridden by groups/nodes, only appended to.
        appendvars = role.argument_appends
        for append in appendvars:
            if append not in rolevars:
                rolevars[append] = []

        # Prepend the universal group to the group list,
        # and find the role arguments from each group
        all_groups = {"universal": inventory.group("universal"), **groupmods}
        for groupname, gmod in all_groups.items():
            group_rolevars = getattr(gmod.group.roles, rolename, {})
            for key, value in group_rolevars.items():
                append_to = None
                if key in appendvars:
                    append_to = rolevars[key]
                rolevars[key] = dereference_rolearg(
                    value, inventory, inventory.get_group_secrets(groupname), append_to=append_to
                )

        # Apply any role arguments from the node itself
        node_rolevars = getattr(node.roles, rolename, {})
        for key, value in node_rolevars.items():
            append_to = None
            if key in appendvars:
                append_to = rolevars[key]
            rolevars[key] = dereference_rolearg(
                value, inventory, inventory.get_node_secrets(nodename), append_to=append_to
            )

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
    role, roleargs = coalesce_node_roles_arguments(inventory, nodename)[rolename]
    if "results" not in dir(role):
        return {}
    return role.results(localhost, **roleargs)
