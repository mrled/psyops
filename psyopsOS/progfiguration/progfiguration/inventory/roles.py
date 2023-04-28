"""Applying and working with roles"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from importlib.abc import Traversable
from importlib.resources import files as importlib_resources_files
from types import ModuleType
from typing import Any, Dict, List, Optional, Type

from progfiguration import age

from progfiguration.inventory.nodes import InventoryNode
from progfiguration.localhost import LocalhostLinuxPsyopsOs


@dataclass
class RoleResultReference:
    """A reference to a result from a role

    This is used to allow roles to reference results from other roles
    """

    role: str
    result: str


@dataclass(kw_only=True)
class ProgfigurationRole(ABC):
    """A role that can be applied to a node

    Required attributes:

    * name: The name of the role
    * localhost: A localhost object
    * inventory: An inventory object
    * rolepkg: The package that the role is defined in,
        used to determine the path to the role's templates.

    Required methods:

    * apply(): Apply the role to the node

    Optional methods:

    * results(): Return a dict of results that may be used by other roles

    Note that you cannot override properties in a subclass of a dataclass.
    Take care when adding new attributes here.
    """

    name: str
    localhost: LocalhostLinuxPsyopsOs
    inventory: "Inventory"
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

        This works whether we're installed from pip, checked out from git, or running from a pyz file.
        """
        if not self._rolefiles:
            self._rolefiles = importlib_resources_files(self.rolepkg)
        return self._rolefiles.joinpath(filename)


def dereference_rolearg(nodename: str, argument: Any, inventory: "Inventory", secrets: Dict[str, Any]) -> Any:
    """Get the final value of a role argument for a node.

    Arguments to this method:

    * nodename:     The name of the node that the argument is being applied to
    * argument:     The role argument to get the final value of
    * inventory:    The inventory object
    * secrets:      A dict containing secrets we can decrypt
                    This might be from inventory.get_group_secrets(groupname) or inventory.get_node_secrets(nodename)

    Role arguments are often used as-is, but some kinds of arguments are special:

    * age.AgeSecretReference: Decrypt the secret using the age key
    * RoleResultReference: Get the result from the referenced role

    This function retrieves the final value from these special argument types.
    Arguments that do not match one of these types are just returned as-is.
    """

    value = argument
    if isinstance(argument, age.AgeSecretReference):
        secret = secrets[argument.name]
        value = secret.decrypt(inventory.age_path)
    elif isinstance(argument, RoleResultReference):
        value = inventory.node_role(nodename, argument.role).results()[argument.result]
    return value


def collect_role_arguments(
    inventory: "Inventory",
    nodename: str,
    node: InventoryNode,
    nodegroups: dict[str, ModuleType],
    rolename: str,
    role_cls: Type[ProgfigurationRole],
):
    """Collect all the arguments for a role

    Find the arguments in the following order:

    * Default role arguments from the ProgfigurationRole subclass
    * Arguments from the universal group
    * Arguments from other groups (in an undefined order)
    * Arguments from the node itself
    """
    groupmods = {}
    for groupname in inventory.node_groups[nodename]:
        groupmods[groupname] = inventory.group(groupname)

    roleargs = {}

    for groupname, gmod in nodegroups.items():
        group_rolevars = getattr(gmod.group.roles, rolename, {})
        for key, value in group_rolevars.items():
            roleargs[key] = dereference_rolearg(nodename, value, inventory, inventory.get_group_secrets(groupname))

    # Apply any role arguments from the node itself
    node_rolevars = getattr(node.roles, rolename, {})
    for key, value in node_rolevars.items():
        roleargs[key] = dereference_rolearg(nodename, value, inventory, inventory.get_node_secrets(nodename))

    return roleargs
