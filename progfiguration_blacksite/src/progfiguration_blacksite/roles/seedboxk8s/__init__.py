"""The Kubernetes seedbox role

* Built for a machine running Rocky Linux 8.x (based on RHEL).
  That requires adding python3.11 via dnf and age via GitHub release out of band.
* Uses flux which looks for manifests in seedboxk8s/manifests in the root of this repo.
* We can use /var/lib/k0s/manifests for manifests that k0s should manage,
  but that doesn't seem to handle renames and deletions very cleanly,
  while flux does that well automatically.
* Flux also supports SOPS secrets out of the box.
"""

from dataclasses import dataclass
import os
import re
import shutil
import time

from progfiguration import logger
from progfiguration.cmd import magicrun
from progfiguration.inventory.roles import ProgfigurationRole

from progfiguration_blacksite.sitelib.githubrelease import download_github_release
from progfiguration_blacksite.sitelib.role_helpers import copy_role_dir_recursively, hash_file_nosecurity


@dataclass(kw_only=True)
class Role(ProgfigurationRole):

    # A GitHub deploy key for the psyops repo for the seedboxk8s Flux deployment
    psyops_seedboxk8s_flux_deploy_id: str

    # An age key for Flux to use with SOPS
    flux_agekey: str

    k0s_version = "v1.29.4+k0s.0"
    k0sctl_version = "v0.17.5"
    helm_version = "v3.14.4"
    kubeseal_version = "0.26.0"
    flux_version = "2.2.3"

    def apply(self):
        try:
            import requests
        except ImportError:
            # At the time of this writing, we're using Rocky Linux 8.x and python3.11 RPM
            magicrun("dnf install python3.11-requests -y")
            import requests

        # k0s binary
        if (
            not os.path.exists("/usr/local/bin/k0s")
            or magicrun("/usr/local/bin/k0s version").stdout.read().strip() != self.k0s_version
        ):
            print("Downloading k0s")
            download_github_release(
                "k0sproject/k0s",
                f"k0s-{re.escape(self.k0s_version)}-amd64",
                outfile="/usr/local/bin/k0s",
                version=self.k0s_version,
            )

        # k0sctl binary
        if (
            not os.path.exists("/usr/local/bin/k0sctl")
            or magicrun("/usr/local/bin/k0sctl version").stdout.read().strip().split("\n")[0]
            != f"version: {self.k0sctl_version}"
        ):
            print("Downloading k0sctl")
            download_github_release(
                "k0sproject/k0sctl", "k0sctl-linux-amd64", outfile="/usr/local/bin/k0sctl", version=self.k0sctl_version
            )

        # helm binary
        if not os.path.exists("/usr/local/bin/helm") or magicrun(
            "/usr/local/bin/helm version"
        ).stdout.read().strip().startswith(self.helm_version):
            print("Downloading helm")
            try:
                response = requests.get(f"https://get.helm.sh/helm-{self.helm_version}-linux-amd64.tar.gz", stream=True)
                if response.status_code == 200:
                    with open("/tmp/helm.tar.gz", "wb") as f:
                        for chunk in response.iter_content(1024):
                            f.write(chunk)
                else:
                    raise Exception(f"Failed to download helm: {response.status_code}")
                self.localhost.makedirs("/tmp/helminstall")
                magicrun(["tar", "xvf", "/tmp/helm.tar.gz", "-C", "/tmp/helminstall"])
                os.rename("/tmp/helminstall/linux-amd64/helm", "/usr/local/bin/helm")
            finally:
                if os.path.exists("/tmp/helminstall"):
                    shutil.rmtree("/tmp/helminstall")
                if os.path.exists("/tmp/helm.tar.gz"):
                    os.unlink("/tmp/helm.tar.gz")

        # flux binary
        if not os.path.exists("/usr/local/bin/flux") and not magicrun("flux --version").stdout.read().strip().endswith(
            self.flux_version
        ):
            print("Downloading flux")
            try:
                download_github_release(
                    "fluxcd/flux2",
                    "flux_.*_linux_amd64",
                    outfile="/tmp/flux.tgz",
                    version=f"v{self.flux_version}",
                )
                self.localhost.makedirs("/tmp/flux")
                magicrun(["tar", "xvf", "/tmp/flux.tgz", "-C", "/tmp/flux"])
                os.rename("/tmp/flux/flux", "/usr/local/bin/flux")
            finally:
                if os.path.exists("/tmp/flux"):
                    shutil.rmtree("/tmp/flux")
                if os.path.exists("/tmp/flux.tgz"):
                    os.unlink("/tmp/flux.tgz")

        # kubeseal binary
        if not os.path.exists("/usr/local/bin/kubeseal") or not magicrun(
            "/usr/local/bin/kubeseal --version"
        ).stdout.read().strip().endswith(self.kubeseal_version):
            print("Downloading kubeseal")
            try:
                self.localhost.makedirs("/tmp/kubeseal")
                download_github_release(
                    "bitnami-labs/sealed-secrets",
                    "kubeseal-.*-linux-amd64.tar.gz$",
                    outfile="/tmp/kubeseal.tgz",
                    version=self.kubeseal_version,
                )
                magicrun(["tar", "xvf", "/tmp/kubeseal.tgz", "-C", "/tmp/kubeseal"])
                os.rename("/tmp/kubeseal/kubeseal", "/usr/local/bin/kubeseal")
            finally:
                if os.path.exists("/tmp/kubeseal"):
                    shutil.rmtree("/tmp/kubeseal")
                if os.path.exists("/tmp/kubeseal.tgz"):
                    os.unlink("/tmp/kubeseal.tgz")

        # profile.d setup
        self.localhost.cp(
            self.role_file("profile.d.k0s.sh"),
            "/etc/profile.d/k0s.sh",
            "root",
            "root",
            0o644,
        )

        # Flux GitHub deploy key for psyops repo
        self.localhost.set_file_contents(
            "/etc/seedboxk8s/flux/psyops_seedboxk8s_flux_deploy_id",
            self.psyops_seedboxk8s_flux_deploy_id,
            "root",
            "root",
            0o600,
            dirmode=0o0700,
        )

        # k0s configuration
        changed_k0s_yaml = True
        oldhash = None
        if os.path.exists("/etc/k0s/k0s.yaml") and os.path.exists("/etc/systemd/system/k0scontroller.service"):
            oldhash = hash_file_nosecurity("/etc/k0s/k0s.yaml")
        self.localhost.cp(self.role_file("k0s.yaml"), "/etc/k0s/k0s.yaml", "root", "root", 0o640)
        if oldhash:
            newhash = hash_file_nosecurity("/etc/k0s/k0s.yaml")
            changed_k0s_yaml = oldhash != newhash

        # k0s service
        if not os.path.exists("/etc/systemd/system/k0scontroller.service"):
            magicrun("/usr/local/bin/k0s install controller --single -c /etc/k0s/k0s.yaml")
        elif changed_k0s_yaml:
            magicrun("systemctl restart k0scontroller")
        magicrun("systemctl start k0scontroller")

        # A place to put manifests without applying them
        copy_role_dir_recursively(
            self, self.role_file("manifests/staging"), "/etc/seedboxk8s/staging.manifests", sync=True
        )

        # k0s will automatically apply manifests in /var/lib/k0s/manifests,
        # and update them if the files change.
        # If you aren't getting what you expect, try `k0s apply -f /var/lib/k0s/manifests/yourfile.yaml`
        # and it will print any errors it encounters trying to apply it.

        # Apply templates individually.

        # Copy manifests as-is.
        # Be careful not to place any items in the manifests/auto directory
        # that match the k0s controller's managed resources.
        # Do NOT use sync=True for this, as it will delete files that k0s created.
        copy_role_dir_recursively(self, self.role_file("manifests/auto"), "/var/lib/k0s/manifests")

        # Copy Helm values
        copy_role_dir_recursively(self, self.role_file("helm"), "/etc/seedboxk8s/helm", sync=True)

        # Create an admin kubeconfig for use with e.g. helm
        os.makedirs("/root/.kube", mode=0o0700, exist_ok=True)
        # If we had to start/restart k0scontroller, we need to wait for it to be ready
        if changed_k0s_yaml:
            time.sleep(3)
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
                    "--path=seedboxk8s/manifests",
                    "--branch=master",
                    "--private-key-file=/etc/seedboxk8s/flux/psyops_seedboxk8s_flux_deploy_id",
                    "--silent",  # or else it will hang waiting for confirmation
                ]
            )
        else:
            logger.info("Flux already bootstrapped, skipping.")

        # The secret filename must end with `.agekey`
        oldkey_hash = None
        if os.path.exists("/etc/seedboxk8s/flux.agekey"):
            oldkey_hash = hash_file_nosecurity("/etc/seedboxk8s/flux.agekey")
        self.localhost.set_file_contents("/etc/seedboxk8s/flux.agekey", self.flux_agekey, "root", "root", 0o600)
        newkey_hash = hash_file_nosecurity("/etc/seedboxk8s/flux.agekey")
        if oldkey_hash != newkey_hash:
            magicrun(
                "k0s kubectl create secret generic sops-age --namespace=flux-system --from-file=/etc/seedboxk8s/flux.agekey"
            )

        # Configure Helm repositories
        # These operations are idempotent
        # magicrun("helm repo add bitnami https://charts.bitnami.com/bitnami")
        # magicrun("helm repo add traefik https://traefik.github.io/charts")
        # magicrun("helm repo update")

        # Apply Helm charts
        # magicrun(
        #     "helm upgrade --install traefik traefik/traefik --version 28.0.0 --values /etc/seedboxk8s/helm/traefik.values.yaml"
        # )
