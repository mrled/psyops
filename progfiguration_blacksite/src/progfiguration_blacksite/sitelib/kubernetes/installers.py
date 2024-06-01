import os
import re
import shutil

from progfiguration.cmd import magicrun
from progfiguration_blacksite.sitelib.githubrelease import download_github_release


def install_k0s_github_release(version: str):
    """Install k0s from GitHub release"""
    if (
        not os.path.exists("/usr/local/bin/k0s")
        or magicrun("/usr/local/bin/k0s version").stdout.read().strip() != version
    ):
        print("Downloading k0s")
        download_github_release(
            "k0sproject/k0s",
            f"k0s-{re.escape(version)}-amd64",
            outfile="/usr/local/bin/k0s",
            version=version,
        )


def install_k0sctl_github_release(version: str):
    """Install k0sctl binary from GitHub release

    On Alpine there is an available apk package for k0sctl, but not for k0s itself,
    so we'll use the GitHub release to have full control.
    """
    if (
        not os.path.exists("/usr/local/bin/k0sctl")
        or magicrun("/usr/local/bin/k0sctl version").stdout.read().strip().split("\n")[0] != f"version: {version}"
    ):
        print("Downloading k0sctl")
        download_github_release(
            "k0sproject/k0sctl", "k0sctl-linux-amd64", outfile="/usr/local/bin/k0sctl", version=version
        )


def install_crictl_github_release(version: str):
    """Install crictl from GitHub release

    Alpine has a package for this.
    Rocky Linux 8.x does not.
    """
    if not os.path.exists("/usr/local/bin/crictl") or magicrun(
        "/usr/local/bin/crictl --version"
    ).stdout.read().strip().endswith(version):
        print("Downloading crictl")
        try:
            os.mkdir("/tmp/crictl")
            download_github_release(
                "kubernetes-sigs/cri-tools",
                f"crictl-{re.escape(version)}-linux-amd64.tar.gz",
                outfile="/tmp/crictl/crictl.tgz",
                version=version,
            )
            magicrun(["tar", "xvf", "/tmp/crictl/crictl.tgz", "-C", "/tmp/crictl"])
            os.rename("/tmp/crictl/crictl", "/usr/local/bin/crictl")
        finally:
            shutil.rmtree("/tmp/crictl")


def install_helm_website_release(version: str):
    """Install the Helm binary directly from its website"""
    import requests

    if not os.path.exists("/usr/local/bin/helm") or magicrun(
        "/usr/local/bin/helm version"
    ).stdout.read().strip().startswith(version):
        print("Downloading helm")
        try:
            os.mkdir("/tmp/helminstall")
            response = requests.get(f"https://get.helm.sh/helm-{version}-linux-amd64.tar.gz", stream=True)
            if response.status_code == 200:
                with open("/tmp/helminstall/helm.tar.gz", "wb") as f:
                    for chunk in response.iter_content(1024):
                        f.write(chunk)
            else:
                raise Exception(f"Failed to download helm: {response.status_code}")
            magicrun(["tar", "xvf", "/tmp/helminstall/helm.tar.gz", "-C", "/tmp/helminstall"])
            os.rename("/tmp/helminstall/linux-amd64/helm", "/usr/local/bin/helm")
        finally:
            shutil.rmtree("/tmp/helminstall")


def install_flux_github_release(version: str):
    """Install Flux from GitHub release"""

    # flux binary
    if not os.path.exists("/usr/local/bin/flux") and not magicrun("flux --version").stdout.read().strip().endswith(
        version
    ):
        print("Downloading flux")
        try:
            os.mkdir("/tmp/flux")
            download_github_release(
                "fluxcd/flux2",
                "flux_.*_linux_amd64",
                outfile="/tmp/flux.tgz",
                version=f"v{version}",
            )
            magicrun(["tar", "xvf", "/tmp/flux/flux.tgz", "-C", "/tmp/flux"])
            os.rename("/tmp/flux/flux", "/usr/local/bin/flux")
        finally:
            shutil.rmtree("/tmp/flux")


def install_kubeseal_github_release(version: str):
    """Install kubeseal from GitHub release"""
    # kubeseal binary
    if not os.path.exists("/usr/local/bin/kubeseal") or not magicrun(
        "/usr/local/bin/kubeseal --version"
    ).stdout.read().strip().endswith(version):
        print("Downloading kubeseal")
        try:
            os.mkdir("/tmp/kubeseal")
            download_github_release(
                "bitnami-labs/sealed-secrets",
                "kubeseal-.*-linux-amd64.tar.gz$",
                outfile="/tmp/kubeseal/kubeseal.tgz",
                version=version,
            )
            magicrun(["tar", "xvf", "/tmp/kubeseal/kubeseal.tgz", "-C", "/tmp/kubeseal"])
            os.rename("/tmp/kubeseal/kubeseal", "/usr/local/bin/kubeseal")
        finally:
            shutil.rmtree("/tmp/kubeseal")
