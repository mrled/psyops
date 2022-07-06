"""kubernasty

The service prep for kubernasty, my home k3s cluster.

Expect the services to be configured by the k3s role.

Notes:

- Running `kubectl apply` is idempotent, so we can just do that here
  <https://stackoverflow.com/questions/59731524/making-kubectl-apply-command-idempotent-in-ansible>
"""

import subprocess
from importlib.resources import files as importlib_resources_files


def apply():

    module_files = importlib_resources_files("progfiguration.inventory.svcpreps.kubernasty")
    kube_vip = module_files.joinpath("kube-vip.yml")
    kube_dash = module_files.joinpath("kubernetes-dashboard.yml")

    subprocess.run(["kubectl", "apply", "-f", kube_vip])
