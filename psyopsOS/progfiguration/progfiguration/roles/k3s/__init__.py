"""KuberNASTY: the NASTIEST k3s cluster in the 'verse.

(k3s at home.)
"""

import os
import subprocess

from progfiguration import logger
from progfiguration.facts import PsyopsOsNode


defaults = {
    "data_mountpoint": "/psyopsos-data",
    "data_k3s_subpath": "overlays/var-lib-rancher-k3s",
    "data_containerd_subpath": "overlays/var-lib-containerd",
    "start_k3s": True,
}


def mount_k3s_binds(
    data_mountpoint: str,
    data_k3s_subpath: str,
    data_containerd_subpath: str,
):
    k3s_dir = "/var/lib/rancher/k3s"
    data_k3s_dir_path = f"{data_mountpoint}/{data_k3s_subpath}"

    containerd_dir = "/var/lib/containerd"
    data_containerd_dir_path = f"{data_mountpoint}/{data_containerd_subpath}"

    # TODO: do I need to manage /var/lib/docker also?

    for directory in [
        data_k3s_dir_path,
        data_containerd_dir_path,
        k3s_dir,
        containerd_dir,
    ]:
        os.makedirs(directory, mode=0o0700, exist_ok=True)

    mtpt_k3s = subprocess.run(f"mountpoint {k3s_dir}", shell=True, check=False, capture_output=True)
    if mtpt_k3s.returncode != 0:
        subprocess.run(f"mount --bind '{data_k3s_dir_path}' '{k3s_dir}'", shell=True, check=True)

    mtpt_nerd = subprocess.run(f"mountpoint {containerd_dir}", shell=True, check=False, capture_output=True)
    if mtpt_nerd.returncode != 0:
        subprocess.run(
            f"mount --bind '{data_containerd_dir_path}' '{containerd_dir}'",
            shell=True,
            check=True,
        )


def apply(
    node: PsyopsOsNode,
    server_token: str,
    data_mountpoint: str,
    data_k3s_subpath: str,
    data_containerd_subpath: str,
    start_k3s: bool,
):

    subprocess.run("apk add k3s", shell=True, check=True)

    mount_k3s_binds(data_mountpoint, data_k3s_subpath, data_containerd_subpath)

    # server_token_file = os.path.join(k3s_dir, "server", "token")
    # with open(server_token_file, 'w') as tfp:
    #     tfp.write(server_token)

    if start_k3s:
        logger.info("Starting k3s...")
        subprocess.run("rc-service cgroups start", shell=True, check=True)
        subprocess.run("rc-service k3s start", shell=True, check=True)
    else:
        logger.info("start_k3s was False, not starting k3s or cgroups")
