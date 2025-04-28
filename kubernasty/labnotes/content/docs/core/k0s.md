---
weight: 20
title: k0s
---

TODO: Replace documentation elsewhere with this, and delete this file

I'm using k0s now instead of k3s.

In progfiguration:

* Set `start_kubernasty` to `False` for all nodes.
* Apply the progfigsite to all nodes,
  which installs k0s, and creates the k0s configuration file.

Now run `k0sctl`.
This is a one-time task that bootstraps the cluster.

* Write the `kubernasty/k0sctl.yaml` file
    * It very much helps to have a `k0s.yaml` file available for reference,
      generate one with `k0s config create`
    * We use [dynamic mode](https://docs.k0sproject.io/main/dynamic-configuration/)
      so that we can subsequently configure the cluster with CRs
      rather than changing `k0sctl.yaml` and re-runing `k0sctl apply`
    * We need to include the DNS names and IP addresses of the nodes,
      as well as those of any load balancers,
      in the spec.api.sans list.
* `k0sctl apply -c kubernasty/k0sctl.yaml`
* Wait for all the nodes to come up
* Get a kubeconfig with `k0sctl kubeconfig -c kubernasty/k0sctl.yaml`
  and place it into `~/.kube/config` on whatever machine you're using to administer the cluster
  (your laptop, whatever)
* See pods starting with `kubectl get pods -A` etc
* It will automatically substitute environment variables like `${THIS_EXAMPLE}`

Now configure Flux for gitops.
This is a one-time task that deploys Flux to the cluster,
and thereafter Flux will look in the Git repository for configuration.

* Create a new SSH key with `ssh-keygen`, and save it to `./flux_deploy_id`
* Add it to your gitops repository as a deploy key; it requires read/write
* `flux bootstrap git --url=ssh://git@github.com/mrled/psyops --path=kubernasty/fluxroot --branch=master --private-key-file=./flux_deploy_id`
* (Add `--silent` to make it go without manual confirmation)
* Delete the `./flux_deploy_id` file; it's saved to the cluster now
* Create an `age` key with `age-keygen` called `./flux.agekey` --
  note that this filename is important, as the next command uses the filename
  as the name for the secret value,
  and the secret value name must end with `.agekey`
* Add it as a SOPS key for Flux with
  `kubectl create secret generic sops-age --namespace=flux-system --from-file=./flux.agekey`
* You can delete the key from local disk

In progfiguration again

* Set `start_kubernasty` to `True` for all nodes
* Test that reboots come up properly

## Building the cluster for the first time took many tries

You probably can't go from nothing to a cluster without rebuilding it a few times.
Some thoughts:

* Get a single node cluster working with a hand-built `k0s.yaml`
  (modified from a default one from `k0s config create`).
* Get a multi node cluster working with `k0sctl` and a `k0sctl.yaml`.
  This creates a `k0s.yaml` on each host.
  See one version of this in {{< repolink "kubernasty/labnotes/content/docs/core/k0sctl.yaml" >}}
* Because we're using psyopsOS, our `k0s.yaml` doesn't persist between reboots.
  Build a templated `k0s.yaml` that progfiguration will apply based on the above.
  This also gives us the ability to change `k0s.yaml`,
  which is required for some types of changes
  even when using `k0sctl` and/or even when using k0s dynamic configuration.
* Check `k0s sysinfo` to see any warnings or errors

## Adding new nodes

Just add them to `k0sctl.yaml` and re-run.

## The layers of the earth

* First, we create the cluster and install Flux
* Flux installs things in phases:
  * Phase 1 sets the foundation for the rest of the cluster
    * Ceph: Storage
    * MetalLB: A load balancer
    * Gitea: Git repository, container registry

### Gitea

We started with the Gitea Helm chart,
but the default deploys dozens of resources in four thousand lines of unmaintainble YAML.

We whittled it down to 2 secrets, a deployment, and a service in just a few hundred lines by:

* Removing Redis, which we expect we don't need
* Skipping the Postgres deployment, in favor of using the CNPG operator instead

## Low level stuff handled by Flux

* Assuming `kubernasty/fluxroot` in the GitHub repository is empty and Flux has nothing to deploy,
  the cluster is pretty barebones at this point,
  and lacks many normal features.
    * It has no LoadBalancer implementation
    * It has no Ingress implementation
    * It has no default storage provider
* In psyops we have manifests to address these issues with (respectively)
    * MetalLB
    * Traefik
    * ... tbd
