"""The progfiguration inventory"""

import os

import yaml


class Inventory():

    def __init__(self, invfile: str):
        self.invfile = invfile
        with open(invfile) as ifp:
            self.inventory_parsed = yaml.load(ifp, Loader=yaml.Loader)

        self.group_members = self.inventory_parsed["groupNodeMap"]
        self.node_function = self.inventory_parsed["nodeFunctionMap"]
        self.function_roles = self.inventory_parsed["functionRoleMap"]

        self._node_groups = None
        self._function_nodes = None
        self._role_functions = None

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
            for group, members in self.group_members.items():
                for member in members:
                    if member not in self._node_groups:
                        self._node_groups[member] = []
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
                        self._role_functions[member] = []
                    self._role_functions[member].append(function)
        return self._role_functions

    # def group_members(self, groupname: str):
    #     return self.inventory_parsed["groupNodeMap"][groupname]

    # def node_function(self, nodename: str):
    #     return self.inventory_parsed["nodeFunctionMap"][nodename]

    # def function_role(self, functionname: str):
    #     return self.inventory_parsed["functionRoleMap"][functionname]

    def node_role(self, nodename: str):
        return self.function_role(self.node_function(nodename))


_inventory_file = os.path.join(os.path.dirname(__file__), "inventory.yml")


# inventory = Inventory(os.path.join(os.path.dirname(__file__), "inventory.yml"))
inventory = Inventory(_inventory_file)


# def _build_inventory(path: str):
#     with open(path) as fp:
#         inventory = yaml.load(fp, Loader=yaml.Loader)

#     inventory["nodeGroupMap"] = {}
#     inventory["nodeRoleMap"]

#     for gname, nodes in inventory["groupNodeMap"].items():


#     return inventory


# inventory = _build_inventory(_inventory_file)
