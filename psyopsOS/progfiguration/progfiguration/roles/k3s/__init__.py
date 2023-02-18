"""KuberNASTY: the NASTIEST k3s cluster in the 'verse.

(k3s at home.)
"""

import os
import subprocess
from importlib.resources import files as importlib_resources_files

from progfiguration import logger
from progfiguration.localhost import LocalhostLinuxPsyopsOs
from progfiguration.roles.datadisk import is_mountpoint


module_files = importlib_resources_files("progfiguration.roles.k3s")


defaults = {
    "data_mountpoint": "/psyopsos-data",
    "data_k3s_subpath": "overlays/var-lib-rancher-k3s",
    "data_containerd_subpath": "overlays/var-lib-containerd",
    "data_etcrancher_subpath": "overlays/etc-rancher",
    "start_k3s": True,
    "kube_vip_interface": "eth0",
}


def mount_k3s_binds(
    data_mountpoint: str,
    data_k3s_subpath: str,
    data_containerd_subpath: str,
    data_etcrancher_subpath: str,
):

    # TODO: do I need to manage /var/lib/docker also?
    mounts = {
        "/var/lib/rancher/k3s": os.path.join(data_mountpoint, data_k3s_subpath),
        "/var/lib/containerd": os.path.join(data_mountpoint, data_containerd_subpath),
        "/etc/rancher": os.path.join(data_mountpoint, data_etcrancher_subpath),
    }
    for mountpoint, overlay in mounts.items():
        os.makedirs(mountpoint, mode=0o0700, exist_ok=True)
        os.makedirs(overlay, mode=0o0700, exist_ok=True)
        if not is_mountpoint(mountpoint):
            logger.debug(f"Mounting {overlay} on {mountpoint}")
            subprocess.run(["mount", "--bind", overlay, mountpoint], check=True)
        else:
            logger.debug(f"Not mounting {overlay} on {mountpoint}, because something is already mounted there")


#### TODO:  Have Kubernetes nodes listen only on their main IP address on port 22
#           Also listen on some other port on truly all interfaces
#           This allows Kubernetes ingresses to use port 22 on the kubernetes VIPs
#           Add these 2 lines to /etc/ssh/sshd_config:
#               ListenAddress 0.0.0.0:9922
#               ListenAddress 192.168.1.153:22


def apply(
    localhost: LocalhostLinuxPsyopsOs,
    data_mountpoint: str,
    data_k3s_subpath: str,
    data_containerd_subpath: str,
    data_etcrancher_subpath: str,
    start_k3s: bool,
    kube_vip_interface: str,
    kube_vip_address: str,
):

    # Some packages are not yet in the stable repos, so we have to use edgetesting
    package_list = [
        "cni-plugin-flannel",
        "etcd-ctl@edgetesting",
        "helm@edgecommunity",
        "k3s",
        "nfs-utils",
        "open-iscsi",
    ]
    packages = " ".join(package_list)

    subprocess.run(f"apk add {packages}", shell=True, check=True)

    localhost.cp(
        module_files.joinpath("k3s-killall.sh"),
        "/usr/local/sbin/k3s-killall.sh",
        owner="root",
        group="root",
        mode=0o0755,
    )

    # ... wtf
    # I'm not crazy though, this is a step that is listed here too
    # <https://wiki.alpinelinux.org/wiki/K8s#2._Node_Setup_.F0.9F.96.A5.EF.B8.8F>
    if not os.path.exists("/usr/libexec/cni/flannel"):
        os.symlink("/usr/libexec/cni/flannel-amd64", "/usr/libexec/cni/flannel")

    mount_k3s_binds(data_mountpoint, data_k3s_subpath, data_containerd_subpath, data_etcrancher_subpath)

    subprocess.run("rc-service cgroups start", shell=True, check=True)
    subprocess.run("rc-service containerd start", shell=True, check=True)
    subprocess.run("rc-service iscsid start", shell=True, check=True)

    if not start_k3s:
        logger.info(
            "start_k3s was False, not starting k3s or cgroups. If you are setting up a new cluster, refer to the psyopsOS/docs/kubernasty.md documentation"
        )
        return

    # Required for Longhorn
    subprocess.run("mount --make-rshared /", shell=True, check=True)

    # Required for Helm to work
    localhost.set_file_contents(
        "/etc/profile.d/kubeconfig.sh", "export KUBECONFIG=/etc/rancher/k3s/k3s.yaml", "root", "root", 0o0644
    )

    # Create role storage
    localhost.makedirs(os.path.join(data_mountpoint, "roles/k3s/longhorn/data"), "root", "root", 0o0700)

    logger.info("Starting k3s...")
    subprocess.run("rc-service k3s start", shell=True, check=True)
