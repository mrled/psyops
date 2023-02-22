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
    # If this matches what's in the datadisk role, use the same VG
    # If you have your own VG to create, do that separately
    "treasury_vgname": "psyopsos_datadiskvg",
    "treasury_lvname": "treasurylv",
    "treasury_lvsize": r"100%FREE",
    "start_k3s": True,
    "kube_vip_interface": "eth0",
}


def make_treasury_volume(
    vgname: str,
    lvname: str,
    lvsize: str = r"100%FREE",
):
    if subprocess.run(f"vgs {vgname}", shell=True, check=False).returncode != 0:
        raise Exception(f"No volume group {vgname} exists -- has this host run the datadisk role?")

    lvs = subprocess.run(f"lvs {vgname}", shell=True, check=False, capture_output=True)
    if lvname not in lvs.stdout.decode():
        logger.info(f"Creating volume {lvname} on vg {vgname}...")
        subprocess.run(f"lvcreate -l {lvsize} -n {lvname} {vgname}", shell=True, check=True)


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
    treasury_vgname: str,
    treasury_lvname: str,
    treasury_lvsize: str,
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

    make_treasury_volume(treasury_vgname, treasury_lvname, treasury_lvsize)

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

    # Required for Longhorn
    subprocess.run("mount --make-rshared /", shell=True, check=True)

    # Required for Helm to work
    localhost.set_file_contents(
        "/etc/profile.d/kubeconfig.sh", "export KUBECONFIG=/etc/rancher/k3s/k3s.yaml", "root", "root", 0o0644
    )

    # Create role storage
    localhost.makedirs(os.path.join(data_mountpoint, "roles/k3s/longhorn/data"), "root", "root", 0o0700)
    localhost.makedirs(os.path.join(data_mountpoint, "roles/k3s/rook-ceph/data"), "root", "root", 0o0700)

    if not start_k3s:
        logger.info(
            "start_k3s was False, not starting k3s. If you are setting up a new cluster, refer to the psyopsOS/docs/kubernasty.md documentation"
        )
        return

    logger.info("Starting k3s...")
    subprocess.run("rc-service k3s start", shell=True, check=True)
