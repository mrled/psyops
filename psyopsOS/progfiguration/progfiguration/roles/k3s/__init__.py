"""KuberNASTY: the NASTIEST k3s cluster in the 'verse.

(k3s at home.)
"""

import os
import subprocess
from importlib.resources import files as importlib_resources_files
import textwrap

from progfiguration import logger
from progfiguration.localhost import LocalhostLinuxPsyopsOs
from progfiguration.localhost.disks import is_mountpoint


module_files = importlib_resources_files("progfiguration.roles.k3s")


defaults = {
    "data_mountpoint": "/psyopsos-data",
    "data_k3s_subpath": "overlays/var-lib-rancher-k3s",
    "data_containerd_subpath": "overlays/var-lib-containerd",
    "data_etcrancher_subpath": "overlays/etc-rancher",
    "start_k3s": True,
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


def apply(
    localhost: LocalhostLinuxPsyopsOs,
    data_mountpoint: str,
    data_k3s_subpath: str,
    data_containerd_subpath: str,
    data_etcrancher_subpath: str,
    start_k3s: bool,
    k3s_interface: str,
    k3s_vipaddress: str,
    k3s_interface2: str,
    k3s_vipaddress2: str,
):

    # Some packages are not yet in the stable repos, so we have to use edgetesting
    package_list = [
        "cni-plugin-flannel",
        "etcd-ctl@edgetesting",
        "helm@edgecommunity",
        "k3s",
        "nfs-utils",
        "open-iscsi",
        "sgdisk",  # Useful for zapping block devices previously used for Ceph
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
    localhost.temple(
        module_files.joinpath("progfiguration-k3s.sh.temple"),
        "/usr/local/sbin/progfiguration-k3s.sh",
        {
            "k3s_interface": k3s_interface,
            "k3s_vipaddress": k3s_vipaddress,
            "k3s_interface2": k3s_interface2,
            "k3s_vipaddress2": k3s_vipaddress2,
        },
        owner="root",
        mode=0o0755,
        dirmode=0o0755,
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

    # Required for Longhorn
    subprocess.run("mount --make-rshared /", shell=True, check=True)

    # Required for Helm to work
    localhost.set_file_contents(
        "/etc/profile.d/progfiguration-k3s.sh",
        textwrap.dedent(
            """\
                export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
                alias k=kubectl
                alias k3s_etcdctl="etcdctl --cacert=/var/lib/rancher/k3s/server/tls/etcd/server-ca.crt --cert=/var/lib/rancher/k3s/server/tls/etcd/client.crt --key=/var/lib/rancher/k3s/server/tls/etcd/client.key"
            """
        ),
        "root",
        "root",
        0o0644,
    )

    # Create role storage
    localhost.makedirs(os.path.join(data_mountpoint, "roles/k3s/longhorn/data"), "root", "root", 0o0700)
    localhost.makedirs(os.path.join(data_mountpoint, "roles/k3s/rook-ceph/data"), "root", "root", 0o0700)

    k3s_initialized = os.path.exists("/etc/rancher/k3s/k3s.yaml")

    if start_k3s and k3s_initialized:
        logger.info("Starting k3s...")
        subprocess.run("rc-service k3s start", shell=True, check=True)
    else:
        logger.info(f"Not starting k3s. k3s.yaml exists: {k3s_initialized}; start_k3s: {start_k3s}.")
