"""KuberNASTY: the NASTIEST k3s cluster in the 'verse.

(k3s at home.)
"""

import os
import subprocess
import textwrap
from typing import Any, Dict

from progfiguration.facts import PsyopsOsNode


defaults = Bunch(
    data_mountpoint = "/psyopsos-data",
    data_k3s_subpath = "overlays/var-lib-rancher-k3s",
    data_containerd_subpath = "overlays/var-lib-containerd"
)


def mount_k3s_binds(
    data_mountpoint: str,
    data_k3s_subpath: str,
    data_containerd_subpath: str
):
    k3s_dir = "/var/lib/rancher/k3s"
    data_k3s_dir_path = f"{data_mountpoint}/{data_k3s_subpath}"

    containerd_dir = "/var/lib/containerd"
    data_containerd_dir_path = f"{data_mountpoint}/{data_containerd_subpath}"

    # TODO: do I need to manage /var/lib/docker also?

    os.makedirs(data_k3s_dir_path, mode=0o0700, exist_ok=True)
    os.makedirs(data_containerd_dir_path, mode=0o0700, exist_ok=True)

    if not subprocess.run(f"mountpoint {k3s_dir}", shell=True, check=False).exitcode != 0:
        subprocess.run(f"mount --bind '{data_k3s_dir_path}' '{k3s_dir}'", shell=True, check=True)

    if not subprocess.run(f"mountpoint {containerd_dir}", shell=True, check=False).exitcode != 0:
        subprocess.run(f"mount --bind '{data_containerd_dir_path}' '{containerd_dir}'", shell=True, check=True)


def apply(
    node: PsyopsOsNode,
    # server_token: str,
    data_mountpoint: str,
    data_k3s_subpath: str,
    data_containerd_subpath: str,
    start_k3s: bool
):

    mount_k3s_binds(data_mountpoint, data_k3s_subpath, data_containerd_subpath)

    # k3s_dir = "/var/lib/rancher/k3s"
    # data_k3s_dir_path = f"{data_mountpoint}/{data_k3s_subpath}"

    # containerd_dir = "/var/lib/containerd"
    # data_containerd_dir_path = f"{data_mountpoint}/{data_containerd_subpath}"

    # # TODO: do I need to manage /var/lib/docker also?

    # os.makedirs(data_k3s_dir_path, mode=0o0700, exist_ok=True)
    # os.makedirs(data_containerd_dir_path, mode=0o0700, exist_ok=True)

    # if not subprocess.run(f"mountpoint {k3s_dir}", shell=True, check=False).exitcode != 0:
    #     subprocess.run(f"mount --bind '{data_k3s_dir_path}' '{k3s_dir}'", shell=True, check=True)

    # if not subprocess.run(f"mountpoint {containerd_dir}", shell=True, check=False).exitcode != 0:
    #     subprocess.run(f"mount --bind '{data_containerd_dir_path}' '{containerd_dir}'", shell=True, check=True)

    # server_token_file = os.path.join(k3s_dir, "server", "token")
    # with open(server_token_file, 'w') as tfp:
    #     tfp.write(server_token)

    if start_k3s:
        subprocess.run("rc-service cgroups start", shell=True, check=True)
        subprocess.run("apk add k3s", shell=True, check=True)
        subprocess.run("rc-service k3s start", shell=True, check=True)
