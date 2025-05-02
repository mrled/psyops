---
weight: 20
title: Creation
---

Write a `k0sctl.yaml` file, and run `k0sctl`.
This declarative tool connects to all nodes and deploys the cluster.
It's also used for updating the `k0s` version
and adding or removing nodes.

* Write the `k0sctl.yaml` file
    * It very much helps to have a `k0s.yaml` file available for reference,
      generate one with `k0s config create`
    * We use [dynamic mode](https://docs.k0sproject.io/main/dynamic-configuration/)
      so that we can subsequently configure the cluster with CRs
      rather than changing `k0sctl.yaml` and re-runing `k0sctl apply`
    * We need to include the DNS names and IP addresses of the nodes,
      as well as those of any load balancers,
      in the spec.api.sans list.
* `k0sctl apply -c k0sctl.yaml`
* Wait for all the nodes to come up
* Get a kubeconfig with `k0sctl kubeconfig -c k0sctl.yaml`
  and place it into `~/.kube/config` on whatever machine you're using to administer the cluster
  (your laptop, whatever)
* See pods starting with `kubectl get pods -A` etc
* It will automatically substitute environment variables like `${THIS_EXAMPLE}`

You can change the `k0sctl.yaml` configuration or add new nodes there and re-apply.

## Building the cluster for the first time took many tries

You probably can't go from nothing to a cluster without rebuilding it a few times.
Some thoughts:

* Get a single node cluster working with a hand-built `k0s.yaml`
  (modified from a default one from `k0s config create`).
* Get a multi node cluster working with `k0sctl` and a `k0sctl.yaml`.
  This creates a `k0s.yaml` on each host.
  See one version of this in {{< repolink "kubernasty/k0sctl.yaml" >}}
* Check `k0s sysinfo` to see any warnings or errors.
* See [Destruction]({{< ref "destruction" >}}) for details on tearing down the cluster.

## An empty cluster

At this point, your cluster is pretty barebons,
running just a few containers like the cluster DNS server and other low level system containers.
It lacks many normal features like:

* It has no LoadBalancer implementation
* It has no Ingress implementation
* It has no default storage provider

We'll use [Flux]({{< ref "flux-gitops" >}}) to install these components.
