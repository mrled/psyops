"""The progfiguration inventory"""

from dataclasses import dataclass
import os
import importlib
from importlib.resources import files as importlib_resources_files
from typing import Dict, List, Optional

import yaml

from progfiguration import age


@dataclass
class Controller:
    age: Optional[age.AgeKey]
    agepub: str


class Inventory:

    age: Optional[age.AgeKey]

    def __init__(self, invfile: str, age_privkey: Optional[str]):
        self.invfile = invfile
        with open(invfile) as ifp:
            self.inventory_parsed = yaml.load(ifp, Loader=yaml.Loader)

        self.group_members = self.inventory_parsed["groupNodeMap"]
        self.node_function = self.inventory_parsed["nodeFunctionMap"]
        self.function_roles = self.inventory_parsed["functionRoleMap"]

        # All nodes are members of the 'universal' group
        self.group_members["universal"] = self.node_function.keys()

        self._node_groups = None
        self._function_nodes = None
        self._role_functions = None

        self._node_modules = {}
        self._group_modules = {}
        self._role_modules = {}

        self._node_secrets = {}
        self._group_secrets = {}

        ctrlrdata = self.inventory_parsed["controller"]
        if os.path.exists(ctrlrdata["age"]):
            ctrlrage = age.AgeKey.from_file(ctrlrdata["age"])
        else:
            ctrlrage = None
        self.controller = Controller(ctrlrage, ctrlrdata["agepub"])

        node_settings = self.inventory_parsed["nodeSettings"]
        nodeage = None
        nodeage_path = None
        for agekey in node_settings["age"]:
            if os.path.exists(agekey):
                nodeage = age.AgeKey.from_file(agekey)
                nodeage_path = agekey
                break

        # TODO: clean this up, I think I can just keep track of the path and that's it
        self.age = None
        self.age_path = None
        if age_privkey:
            self.age = age.AgeKey.from_file(age_privkey)
            self.age_path = age_privkey
        elif ctrlrage:
            self.age = ctrlrage
            self.age_path = ctrlrdata["age"]
        elif nodeage:
            self.age = nodeage
            self.age_Path = nodeage_path
        else:
            # No age key found
            pass

    @property
    def groups(self):
        return self.group_members.keys()

    @property
    def nodes(self):
        return self.node_function.keys()

    @property
    def functions(self):
        return self.function_roles.keys()

    @property
    def node_groups(self):
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
    def function_nodes(self):
        if not self._function_nodes:
            self._function_nodes = {}
            for node, function in self.node_function.items():
                if function not in self._function_nodes:
                    self._function_nodes[function] = []
                self._function_nodes[function].append(node)
        return self._function_nodes

    @property
    def role_functions(self):
        if not self._role_functions:
            self._role_functions = {}
            for function, nodes in self.function_nodes.items():
                for node in nodes:
                    if node not in self._role_functions:
                        self._role_functions[node] = []
                    self._role_functions[node].append(function)
        return self._role_functions

    def node_roles(self, nodename: str):
        return self.function_roles[self.node_function[nodename]]

    def node(self, name: str):
        if name not in self._node_modules:
            module = importlib.import_module(f"progfiguration.inventory.nodes.{name}")
            self._node_modules[name] = module
        return self._node_modules[name]

    def group(self, name: str):
        if name not in self._group_modules:
            module = importlib.import_module(f"progfiguration.inventory.groups.{name}")
            self._group_modules[name] = module
        return self._group_modules[name]

    def role(self, name: str):
        if name not in self._role_modules:
            module = importlib.import_module(f"progfiguration.roles.{name}")
            self._role_modules[name] = module
        return self._role_modules[name]

    def node_secrets_file(self, nodename: str) -> str:
        """Get the secrets file for a node"""
        sfile = importlib_resources_files("progfiguration.inventory.nodes").joinpath(f"{nodename}.secrets.yml")
        return sfile

    def group_secrets_file(self, groupname: str) -> str:
        """Get the secrets file for a group"""
        sfile = importlib_resources_files("progfiguration.inventory.groups").joinpath(f"{groupname}.secrets.yml")
        return sfile

    def controller_secrets_file(self) -> str:
        """Get the secrets file for the controller"""
        sfile = importlib_resources_files("progfiguration.inventory").joinpath(f"controller.secrets.yml")

    def get_secrets(self, filename: str) -> Dict[str, age.AgeSecret]:
        """Retrieve secrets from a file.

        If the file is not found, just return an empty dict.
        """
        try:
            with open(filename) as fp:
                contents = yaml.load(fp, Loader=yaml.Loader)
                encrypted_secrets = {k: age.AgeSecret(v) for k, v in contents.items()}
                return encrypted_secrets
        except FileNotFoundError:
            return {}

    def get_node_secrets(self, nodename: str) -> Dict:
        if nodename not in self._node_secrets:
            self._node_secrets[nodename] = self.get_secrets(self.node_secrets_file(nodename))
        return self._node_secrets[nodename]

    def get_group_secrets(self, groupname: str) -> Dict:
        if groupname not in self._group_secrets:
            self._group_secrets[groupname] = self.get_secrets(self.group_secrets_file(groupname))
        return self._group_secrets[groupname]

    def get_controller_secrets(self) -> Dict:
        if not self._controller_secrets:
            self._controller_secrets = self.get_secrets(self.controller_secrets_file())
        return self._controller_secrets

    def set_secrets(self, filename: str, secrets: Dict[str, age.AgeSecret]):
        """Set the contents of a secrets file"""
        file_contents = {k: v.secret for k, v in secrets.items()}
        with open(filename, "w") as fp:
            yaml.dump(file_contents, fp, default_style="|")

    def set_node_secret(self, nodename: str, secretname: str, encrypted_value: str):
        self.get_node_secrets(nodename)  # Ensure it's cached
        self._node_secrets[nodename][secretname] = age.AgeSecret(encrypted_value)
        self.set_secrets(self.node_secrets_file(nodename), self._node_secrets[nodename])

    def set_group_secret(self, groupname: str, secretname: str, encrypted_value: str):
        self.get_group_secrets(groupname)  # Ensure it's cached
        self._group_secrets[groupname][secretname] = age.AgeSecret(encrypted_value)
        self.set_secrets(self.group_secrets_file(groupname), self._group_secrets[groupname])

    def set_controller_secret(self, secretname: str, encrypted_value: str):
        self.get_controller_secrets()  # Ensure it's cached
        self._controller_secrets[secretname] = age.AgeSecret(encrypted_value)
        self.set_secrets(self.controller_secrets_file(), self._controller_secrets)

    def encrypt_secret(
        self, name: str, value: str, nodes: List[str], groups: List[str], controller_key: bool, store: bool = False
    ):

        recipients = nodes.copy()

        for group in groups:
            recipients += self.group_members[group]
        recipients = set(recipients)

        nmods = [self.node(n) for n in recipients]
        pubkeys = [nm.node.pubkey for nm in nmods]

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


package_inventory_file = importlib_resources_files("progfiguration.inventory").joinpath("inventory.yml")
