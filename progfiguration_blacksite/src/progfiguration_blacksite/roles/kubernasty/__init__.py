"""KuberNASTY: the NASTIEST Kubernetes cluster in the 'verse.

(Kubernetes at home.)
"""

from dataclasses import dataclass
import os
from pathlib import Path
import subprocess

from progfiguration import logger
from progfiguration.cmd import magicrun
from progfiguration.inventory.roles import ProgfigurationRole
from progfiguration.localhost.disks import is_mountpoint

from progfiguration_blacksite.sitelib.kubernetes.installers import install_k0s_github_release
from progfiguration_blacksite.sitelib.networking import get_ip_address
from progfiguration_blacksite.sitelib.tracked_file_changes import TrackedFileChanges


def mount_binds(binds: dict[str, str]):
    """Mounts a dictionary of bind mounts.

    The keys are the mountpoints, and the values are the overlays.
    E.g., {"/var/lib/docker": "/psyopsos-data/overlays/var-lib-docker"}.
    """
    for mountpoint, overlay in binds.items():
        os.makedirs(mountpoint, mode=0o0700, exist_ok=True)
        os.makedirs(overlay, mode=0o0700, exist_ok=True)
        if not is_mountpoint(mountpoint):
            logger.debug(f"Mounting {overlay} on {mountpoint}")
            subprocess.run(["mount", "--bind", overlay, mountpoint], check=True)
        else:
            logger.debug(f"Not mounting {overlay} on {mountpoint}, because something is already mounted there")


@dataclass(kw_only=True)
class Role(ProgfigurationRole):

    # Expects a psy0 interface with an IPv4 address already provisioned.

    # A GitHub deploy key for the psyops repo for the Flux deployment
    flux_deploy_id: str

    # An age key for Flux to use with SOPS
    flux_agekey: str

    vrrp_authpass: str
    """The VRRP authentication password for the k0s cluster."""

    # Probably need to update all of these at once
    k0s_version = "v1.30.1+k0s.0"
    k0sctl_version = "v0.17.5"

    # This must match the containerd version on the system
    # Better to use system packages for this,
    # except that I think my Rocky Linux 8.x is too old or something.
    crictl_version = "1.6.31"

    helm_version = "v3.14.4"
    kubeseal_version = "0.26.0"
    flux_version = "2.2.3"

    # Config directory, can be ephemeral
    configdir: Path = Path("/etc/kubernasty")

    role_dir: Path = Path("/psyopsos-data/roles/kubernasty")

    @property
    def node_initialized_file(self):
        return self.role_dir / "node_initialized"

    def apply(self):
        packages = [
            "containerd",
            "containerd-ctr",
            "containerd-openrc",
            "cri-tools",  # crictl
            "wireguard-tools",
        ]
        magicrun(["apk", "add", *packages])

        install_k0s_github_release(self.k0s_version)

        # profile.d setup
        self.localhost.cp(
            self.role_file("profile.d.k0s.sh"),
            "/etc/profile.d/k0s.sh",
            "root",
            "root",
            0o644,
        )
        # Bind mount the persistent directories
        mount_binds(
            {
                "/var/lib/k0s": "/psyopsos-data/overlays/var-lib-k0s",
                "/var/lib/containerd": "/psyopsos-data/overlays/var-lib-containerd",
            }
        )

        if not self.node_initialized_file.exists():
            logger.info(
                f"MANUAL CONFIGURATION REQUIRED. Node not initialized; skipping k0s setup. Join the node to the cluster and then create the file {self.node_initialized_file.as_posix()}"
            )
            return

        # Deploy k0s.yaml
        # We generated this file with `k0sctl`,
        # but we have to copy a templated version here because /etc/k0s is not persisted.
        with TrackedFileChanges(Path("/etc/k0s/k0s.yaml")) as tracker:
            self.localhost.temple(
                self.role_file("k0s.yaml.temple"),
                "/etc/k0s/k0s.yaml",
                {
                    "psy0ip": get_ip_address("psy0"),
                    "vrrp_authpass": self.vrrp_authpass,
                },
                "root",
                "root",
                0o640,
            )
            k0s_yaml_didchange = tracker.changed

        # Set up the k0s service.
        # This is how you bring up the cluster once already joined;
        # but joining a new node to the cluster must be done manually first.
        if not os.path.exists("/etc/init.d/k0scontroller"):
            # This just sets up the service in /etc/init.d,
            # it doesn't start it or create any cluster stuff like the CA.
            # --enable-worker allows both controller and worker on the same node.
            # We don't want --single which disables HA.
            magicrun("/usr/local/bin/k0s install controller --enable-worker -c /etc/k0s/k0s.yaml")

        # Start k0s
        if k0s_yaml_didchange:
            magicrun("rc-service k0scontroller restart")
        magicrun("rc-service k0scontroller start")
