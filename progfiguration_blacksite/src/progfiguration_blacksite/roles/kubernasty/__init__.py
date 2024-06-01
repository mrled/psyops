"""KuberNASTY: the NASTIEST Kubernetes cluster in the 'verse.

(Kubernetes at home.)
"""

from dataclasses import dataclass
import os
from pathlib import Path
import subprocess
import textwrap
import time

from progfiguration import logger
from progfiguration.cmd import magicrun
from progfiguration.inventory.roles import ProgfigurationRole
from progfiguration.localhost.disks import is_mountpoint

from progfiguration_blacksite.sitelib.kubernetes.installers import (
    install_k0s_github_release,
    install_k0sctl_github_release,
    install_helm_website_release,
    install_flux_github_release,
)
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

    # Probably need to update all of these at once
    k0s_version = "v1.30.0+k0s.0"
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
        install_k0sctl_github_release(self.k0sctl_version)
        # install_crictl_github_release(self.crictl_version)
        install_helm_website_release(self.helm_version)
        # install_kubeseal_github_release(self.kubeseal_version)
        install_flux_github_release(self.flux_version)

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

        # k0s configuration
        with TrackedFileChanges(Path("/etc/k0s/k0s.yaml")) as tracker:
            self.localhost.temple(
                self.role_file("k0s.yaml.temple"),
                "/etc/k0s/k0s.yaml",
                {"psy0ip": get_ip_address("psy0")},
                "root",
                "root",
                0o640,
            )
            k0s_yaml_didchange = tracker.changed

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

        # k0s service
        if not os.path.exists("/etc/init.d/k0scontroller"):
            # This just sets up the service in /etc/init.d,
            # it doesn't start it or create any cluster stuff like the CA.
            # --enable-worker allows both controller and worker on the same node.
            # We don't want --single which disables HA.
            magicrun("/usr/local/bin/k0s install controller --enable-worker -c /etc/k0s/k0s.yaml")
        elif k0s_yaml_didchange:
            magicrun("rc-service k0scontroller restart")
        magicrun("rc-service k0scontroller start")

        # Create an admin kubeconfig for use with e.g. helm
        os.makedirs("/root/.kube", mode=0o0700, exist_ok=True)
        # If we had to start/restart k0scontroller, we need to wait for it to be ready
        if k0s_yaml_didchange:
            time.sleep(5)
        magicrun("/usr/local/bin/k0s kubeconfig admin > /root/.kube/config")
        magicrun("chmod 0600 /root/.kube/config")

        # Bootstrap flux
        # This is idempotent, but a little slow, so we only do it if we have to.
        flux_ns_result = magicrun("k0s kubectl get ns flux-system", check=False)
        if flux_ns_result.returncode != 0:
            logger.info("Bootstrapping flux, this will take a minute or two the first time.")
            # You have to have already generated the private key and added to this repo as a progfiguration secret
            # and added the public key to the repo's deploy keys on GitHub in advance.
            magicrun(
                [
                    "flux",
                    "bootstrap",
                    "git",
                    "--url=ssh://git@github.com/mrled/psyops",
                    "--path=kubernasty/fluxroot",
                    "--branch=master",
                    "--private-key-file=/etc/kubernasty/flux/deploy_id",
                    "--toleration-keys=node-role.kubernetes.io/master",  # Or else it won't run on our nodes which are both master and worker
                    "--silent",  # or else it will hang waiting for confirmation
                ]
            )
        else:
            logger.info("Flux already bootstrapped, skipping.")

        # The secret filename must end with `.agekey`
        with TrackedFileChanges(Path("/etc/kubernasty/flux.agekey")) as tracker:
            self.localhost.set_file_contents("/etc/kubernasty/flux.agekey", self.flux_agekey, "root", "root", 0o600)
            if tracker.changed and not tracker.created:
                raise Exception("The flux age key changed and I'm not sure what to do about it. Lol!")
        if magicrun("k0s kubectl get secret sops-age --namespace=flux-system", check=False).returncode != 0:
            magicrun(
                "k0s kubectl create secret generic sops-age --namespace=flux-system --from-file=/etc/kubernasty/flux.agekey"
            )
