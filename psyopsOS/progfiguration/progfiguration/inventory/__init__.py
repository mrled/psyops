"""The progfiguration inventory"""

from dataclasses import dataclass
import os
import importlib
from importlib.abc import Traversable
from importlib.resources import files as importlib_resources_files
from pathlib import Path
from types import ModuleType
from typing import Any, Dict, List, Optional

import yaml

from progfiguration import age
from progfiguration.inventory.roles import ProgfigurationRole, collect_role_arguments
from progfiguration.localhost import LocalhostLinuxPsyopsOs
from progfiguration.progfigtypes import AnyPathOrStr


@dataclass
class Controller:
    age: Optional[age.AgeKey]
    agepub: str
    agepath: str


class Inventory:

    # The controller age key that can be used to decrypt anything.
    # When running progfiguration from a node, this is not available.
    age: Optional[age.AgeKey]

    def __init__(self, invfile: Traversable | Path, age_privkey: Optional[str]):
        """Initializer

        invfile:        A YAML inventory file.
        age_privkey:    Use this path to an age private key.
                        If not passed, try to find the appropriate node/controller age key.
        """
        self.invfile = invfile
        with self.invfile.open() as ifp:
            self.inventory_parsed = yaml.load(ifp, Loader=yaml.Loader)

        self.localhost = LocalhostLinuxPsyopsOs()

        self.node_function = self.inventory_parsed["nodeFunctionMap"]
        self.function_roles = self.inventory_parsed["functionRoleMap"]

        # Prepend the universal group to the list of groups
        self.group_members = {"universal": self.node_function.keys(), **self.inventory_parsed["groupNodeMap"]}

        self._node_groups = None
        self._function_nodes = None
        self._role_functions = None

        self._node_modules = {}
        self._group_modules = {}
        self._role_modules = {}
        self._node_roles = {}

        self._node_secrets = {}
        self._group_secrets = {}

        self._controller: Optional[Controller] = None

        self._age_path = age_privkey

    @property
    def groups(self) -> List[str]:
        """All groups, in undetermined order"""
        return self.group_members.keys()

    @property
    def nodes(self) -> List[str]:
        """All nodes, in undetermined order"""
        return self.node_function.keys()

    @property
    def functions(self) -> List[str]:
        """All functions, in undetermined order"""
        return self.function_roles.keys()

    @property
    def node_groups(self) -> Dict[str, List[str]]:
        """A dict, containing node:grouplist mappings"""
        if not self._node_groups:
            self._node_groups = {}

            # All nodes should be listed in the nodeFunctionMap, so we first give them all an empty group list.
            # This gets us all nodes, even if they are not members of any explicit group.
            for node in self.node_function.keys():
                self._node_groups[node] = []

            # Now we traverse the groupNodeMap and fill in the group list
            for group, members in self.group_members.items():
                for member in members:
                    self._node_groups[member].append(group)

        return self._node_groups

    @property
    def function_nodes(self) -> Dict[str, List[str]]:
        """A dict, containing function:nodelist mappings"""
        if not self._function_nodes:
            self._function_nodes = {}
            for node, function in self.node_function.items():
                if function not in self._function_nodes:
                    self._function_nodes[function] = []
                self._function_nodes[function].append(node)
        return self._function_nodes

    @property
    def role_functions(self) -> Dict[str, str]:
        """A dict, containing role:function mappings"""
        if not self._role_functions:
            self._role_functions = {}
            for function, nodes in self.function_nodes.items():
                for node in nodes:
                    if node not in self._role_functions:
                        self._role_functions[node] = []
                    self._role_functions[node].append(function)
        return self._role_functions

    @property
    def controller(self) -> Controller:
        """A Controller object

        If this program is running on the controller, it includes the private key;
        otherwise, it just includes the public key.
        """
        if not self._controller:
            ctrlrdata = self.inventory_parsed["controller"]
            if os.path.exists(ctrlrdata["age"]):
                ctrlrage = age.AgeKey.from_file(ctrlrdata["age"])
            else:
                ctrlrage = None
            self._controller = Controller(ctrlrage, ctrlrdata["agepub"], ctrlrdata["age"])
        return self._controller

    @property
    def age_path(self) -> str:
        """The path to an age private key

        Return the path to an age private key.
        May return None if no private key is available
        (some progfiguration functions can be performed without one).
        Lookup order, highest priority first:

        * A key passed to the class initializer directly, if present
        * The controller key, if available
        * The key for the current node, if running from a node with an available key
        * None
        """
        if not self._age_path:
            if os.path.exists(self.controller.agepath):
                self._age_path = self.controller.agepath
            else:
                for agekey in self.inventory_parsed["nodeSettings"]["age"]:
                    if os.path.exists(agekey):
                        self._age_path = agekey
                        break
        return self._age_path

    def node_rolename_list(self, nodename: str) -> List[str]:
        """A list of all rolenames for a given node"""
        return self.function_roles[self.node_function[nodename]]

    def node(self, name: str) -> ModuleType:
        """The Python module for a given node"""
        if name not in self._node_modules:
            module = importlib.import_module(f"progfiguration.site.nodes.{name}")
            self._node_modules[name] = module
        return self._node_modules[name]

    def group(self, name: str) -> ModuleType:
        """The Python module for a given group"""
        if name not in self._group_modules:
            module = importlib.import_module(f"progfiguration.site.groups.{name}")
            self._group_modules[name] = module
        return self._group_modules[name]

    def role_module(self, name: str) -> ModuleType:
        """The Python module for a given role"""
        if name not in self._role_modules:
            module = importlib.import_module(f"progfiguration.site.roles.{name}")
            self._role_modules[name] = module
        return self._role_modules[name]

    def node_role(self, nodename: str, rolename: str) -> ProgfigurationRole:
        """A dict of {nodename: {rolename: ProgfigurationRole}}

        Get an instantiated ProgfigurationRole object for a given node and role.

        We collect all arguments required to instantiate the role,
        including the superclass arguments like rolepkg and localhost,
        as well as role-specific arguments accepted by the given ProgfigurationRole subclass
        and defined as a default argument or in the group or node argument dicts.
        The result is ready to .apply() or .results().

        Results are cached for subsequent calls.
        """
        if nodename not in self._node_roles:
            self._node_roles[nodename] = {}
        if rolename not in self._node_roles[nodename]:

            # rolepkg is a string containing the package name of the role, like progfiguration.site.roles.role_name
            rolepkg = self.role_module(rolename).__package__

            # The class it the subclass of ProgfigurationRole that implements the role
            role_cls = self.role_module(rolename).Role

            # Get a list of all the groups this node is a member of so that we can get any role arg definitions they may have
            groupmods = {}
            for groupname in self.node_groups[nodename]:
                groupmods[groupname] = self.group(groupname)

            # Get the node module so we can get any role arg definitions it may have
            node = self.node(nodename).node

            # Collect all the arguments we need to instantiate the role class
            # This function finds the most specific definition of each argument
            roleargs = collect_role_arguments(self, nodename, node, groupmods, rolename, role_cls)

            # Instantiate the role class, now that we have all the arguments we need
            try:
                role = role_cls(name=rolename, localhost=self.localhost, inventory=self, rolepkg=rolepkg, **roleargs)
            except Exception as exc:
                msg = f"Error instantiating role {rolename} for node {nodename}: {exc}"
                if isinstance(exc, AttributeError) and exc.args[0].startswith("can't set attribute"):
                    msg += " This might happen if you have two properties with the same name (perhaps one as a function with a @property decorator)."
                raise Exception(msg) from exc

            # And set the role in the cache
            self._node_roles[nodename][rolename] = role

        return self._node_roles[nodename][rolename]

    def node_role_list(self, nodename: str) -> list[ProgfigurationRole]:
        """A list of all instantiated roles for a given node"""
        return [self.node_role(nodename, rolename) for rolename in self.node_rolename_list(nodename)]

    def get_secrets(self, filename: AnyPathOrStr) -> Dict[str, age.AgeSecret]:
        """Retrieve secrets from a file.

        If the file is not found, just return an empty dict.
        """
        if isinstance(filename, str):
            filename = Path(filename)
        try:
            with filename.open() as fp:
                contents = yaml.load(fp, Loader=yaml.Loader)
                encrypted_secrets = {k: age.AgeSecret(v) for k, v in contents.items()}
                return encrypted_secrets
        except FileNotFoundError:
            return {}

    def get_node_secrets(self, nodename: str) -> Dict[str, Any]:
        """A Dict of secrets for a given node"""
        if nodename not in self._node_secrets:
            sfile = importlib_resources_files("progfiguration.site.nodes").joinpath(f"{nodename}.secrets.yml")
            self._node_secrets[nodename] = self.get_secrets(sfile)
        return self._node_secrets[nodename]

    def get_group_secrets(self, groupname: str) -> Dict[str, Any]:
        """A Dict of secrets for a given group"""
        if groupname not in self._group_secrets:
            sfile = importlib_resources_files("progfiguration.site.groups").joinpath(f"{groupname}.secrets.yml")
            self._group_secrets[groupname] = self.get_secrets(sfile)
        return self._group_secrets[groupname]

    def get_controller_secrets(self) -> Dict[str, Any]:
        """A Dict of secrets for the controller"""
        if not self._controller_secrets:
            sfile = importlib_resources_files("progfiguration.site").joinpath(f"controller.secrets.yml")
            self._controller_secrets = self.get_secrets(sfile)
        return self._controller_secrets

    def _set_secrets(self, filename: str, secrets: Dict[str, age.AgeSecret]):
        """Set the contents of a secrets file"""
        file_contents = {k: v.secret for k, v in secrets.items()}
        with open(filename, "w") as fp:
            yaml.dump(file_contents, fp, default_style="|")

    def group_secrets_file(self, group: str) -> Path:
        """The path to the secrets file for a given group"""
        return importlib_resources_files("progfiguration.site.groups").joinpath(f"{group}.secrets.yml")

    def node_secrets_file(self, node: str) -> Path:
        """The path to the secrets file for a given node"""
        return importlib_resources_files("progfiguration.site.nodes").joinpath(f"{node}.secrets.yml")

    def set_node_secret(self, nodename: str, secretname: str, encrypted_value: str):
        """Set a secret for a node"""
        self.get_node_secrets(nodename)  # Ensure it's cached
        self._node_secrets[nodename][secretname] = age.AgeSecret(encrypted_value)
        self._set_secrets(self.node_secrets_file(nodename), self._node_secrets[nodename])

    def set_group_secret(self, groupname: str, secretname: str, encrypted_value: str):
        """Set a secret for a group"""
        self.get_group_secrets(groupname)  # Ensure it's cached
        self._group_secrets[groupname][secretname] = age.AgeSecret(encrypted_value)
        self._set_secrets(self.group_secrets_file(groupname), self._group_secrets[groupname])

    def set_controller_secret(self, secretname: str, encrypted_value: str):
        """Set a secret for the controller"""
        self.get_controller_secrets()  # Ensure it's cached
        self._controller_secrets[secretname] = age.AgeSecret(encrypted_value)
        self._set_secrets(self.controller_secrets_file(), self._controller_secrets)

    def encrypt_secret(
        self, name: str, value: str, nodes: List[str], groups: List[str], controller_key: bool, store: bool = False
    ):
        """Encrypt a secret for some list of nodes and groups.

        Always encrypt for the controller so that it can decrypt too.
        """

        recipients = nodes.copy()

        for group in groups:
            recipients += self.group_members[group]
        recipients = set(recipients)

        nmods = [self.node(n) for n in recipients]
        pubkeys = [nm.node.age_pubkey for nm in nmods]

        # We always encrypt for the controller when storing, so that the controller can decrypt too
        if controller_key or store:
            pubkeys += [self.controller.agepub]

        encrypted_value = age.encrypt(value, pubkeys)

        if store:
            for node in nodes:
                self.set_node_secret(node, name, encrypted_value)
            for group in groups:
                self.set_group_secret(group, name, encrypted_value)
            if controller_key:
                self.set_controller_secret(name, encrypted_value)

        return (encrypted_value, pubkeys)
