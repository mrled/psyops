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
import time

from progfiguration import logger
from progfiguration.cmd import magicrun
from progfiguration.inventory.roles import ProgfigurationRole

from progfiguration_blacksite.roles.seedboxk8s.installdeps import (
    install_k0s_github_release,
    install_k0sctl_github_release,
    install_helm_website_release,
    install_kubeseal_github_release,
    install_flux_github_release,
)
from progfiguration_blacksite.sitelib.role_helpers import copy_role_dir_recursively, hash_file_nosecurity


@dataclass(kw_only=True)
class Role(ProgfigurationRole):

    # A GitHub deploy key for the psyops repo for the seedboxk8s Flux deployment
    psyops_seedboxk8s_flux_deploy_id: str

    # An age key for Flux to use with SOPS
    flux_agekey: str

    # Internal cluster CA
    ca_key: str
    ca_crt: str

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

    def apply(self):
        try:
            import requests
        except ImportError:
            # At the time of this writing, we're using Rocky Linux 8.x and python3.11 RPM
            magicrun("dnf install python3.11-requests -y")
            import requests  # noqa: F401

        magicrun("dnf install nfs-utils rpcbind -y")
        magicrun("systemctl enable --now nfs-server rpcbind")
        magicrun("systemctl start nfs-server rpcbind")
        self.localhost.cp(self.role_file("exports.txt"), "/etc/exports", "root", "root", 0o644)

        install_k0s_github_release(self.k0s_version)
        install_k0sctl_github_release(self.k0sctl_version)
        # install_crictl_github_release(self.crictl_version)
        install_helm_website_release(self.helm_version)
        install_kubeseal_github_release(self.kubeseal_version)
        install_flux_github_release(self.flux_version)

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

        # Internal CA for the cluster
        # Generate one like this:
        #       openssl genrsa -out seedboxk8s.ca.key 4096
        #       openssl req -x509 -new -nodes -key seedboxk8s.ca.key -sha256 -days 36500 -out seedboxk8s.ca.crt -subj "/CN=SeedboxK8s Internal CA"
        # That's valid for approximately 100 years.
        # There's no easy way to have cert-manager generate this for us in the cluster,
        # because we need to have it on the nodes,
        # and also because we want to have just the cert in a ConfigMap
        # which we will have to copy there anyway,
        # so we create it out of band and copy it to the places it needs to go all at once
        # and make it valid for 100 years.
        #
        # WARNING: It must be the same key and/or cert that is also found in:
        # - cluster-ca/ConfigMap.cluster-ca-cert.yaml
        # - cluster-ca/Secret.cluster-ca-backing-secret.yaml
        #
        # self.localhost.set_file_contents("/etc/seedboxk8s/ca.crt", self.ca_crt, "root", "root", 0o644)
        self.localhost.set_file_contents(
            "/usr/local/share/ca-certificates/seedboxk8s.ca.crt", self.ca_crt, "root", "root", 0o644
        )
        magicrun("update-ca-trust")

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
                    "--path=seedboxk8s/fluxroot",
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
        if magicrun("k0s kubectl get secret sops-age --namespace=flux-system", check=False).returncode != 0:
            magicrun(
                "k0s kubectl create secret generic sops-age --namespace=flux-system --from-file=/etc/seedboxk8s/flux.agekey"
            )
        elif oldkey_hash != newkey_hash:
            raise Exception("The flux age key changed and I'n not sure what to do about it. Lol!")
