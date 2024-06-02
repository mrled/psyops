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

    cluster_initialized: bool = False
    """If True, the cluster has been initialized and we can start k0scontroller etc.

    If False, we will only install the packages and set up the configuration files
    in preparation for running 'k0sctl apply ...'.
    """

    # A GitHub deploy key for the psyops repo for the Flux deployment
    flux_deploy_id: str

    # An age key for Flux to use with SOPS
    flux_agekey: str

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

        if not self.cluster_initialized:
            return

        # Flux GitHub deploy key for psyops repo
        self.localhost.set_file_contents(
            self.configdir / "flux" / "deploy_id",
            self.flux_deploy_id,
            "root",
            "root",
            0o600,
            dirmode=0o0700,
        )

        # Flux agekey for SOPS
        self.localhost.set_file_contents(
            self.configdir / "flux" / "flux.agekey",
            self.flux_agekey,
            "root",
            "root",
            0o600,
            dirmode=0o0700,
        )

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
        magicrun("rc-service k0scontroller start")

        # Create an admin kubeconfig for use with e.g. helm
        os.makedirs("/root/.kube", mode=0o0700, exist_ok=True)
        magicrun("ln -s /var/lib/k0s/pki/admin.conf /root/.kube/config")
