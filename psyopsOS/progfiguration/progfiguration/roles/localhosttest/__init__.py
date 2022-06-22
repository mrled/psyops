"""A test role for working with the localhost node"""


import json
import subprocess
from typing import Any, Dict

from progfiguration.facts import PsyopsOsNode
from progfiguration.inventory.invhelpers import Bunch


defaults = {
    "testval_from_role_defaults": "this is a test value from role defaults, lol",
}


def apply(node: PsyopsOsNode, variables: Dict[str, Any]):

    print(f"I am called for node {node.nodename}")

    print(f"The variables I have in scope are:")
    print(json.dumps(variables, indent=2, sort_keys=True))
