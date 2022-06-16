"""KuberNASTY: the NASTIEST k3s cluster in the 'verse.

(k3s at home.)
"""

from datetime import datetime
import textwrap
from typing import Any, Dict

from progfiguration.facts import PsyopsOsNode


def apply(node: PsyopsOsNode, variables: Dict[str, Any]):

    subprocess.run("rc-update add cgroups default", shell=True, check=True)
    subprocess.run("rc-service cgroups start", shell=True, check=True)
    subprocess.run("apk add k3s", shell=True, check=True)
