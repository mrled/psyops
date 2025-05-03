---
title: Prerequisites
weight: 11
---

## DNS

You'll need a DNS server that you have full programmatic control over, like a Route53 zone.
See [dns]({{< ref dns >}}) for specifics.

## Networking

Aside from IP addresses for each cluster node,
you'll need two additional addresses on your local network:

* The control plane HA IP; mine is `192.168.1.220`.
  This goes in `k0sctl.yaml`
* THe cluster ingress VIPO; mine is `192.168.1.221`.
  This is used by [metallb]({{< ref metallb >}})

## Cluster nodes

You need nodes to dedicate to Kubernetes,
whether VMs or physical machines.
Some options:

* A single-node cluster for labs, testing, etc.
  Sort of like an extremely heavyweight docker-compose.
* Three controller+worker nodes for high availability
* Three, five, or seven nodes for the controller,
  plus any number of worker nodes.
  Controller nodes should be an odd number.

You'll need an ssh key that can talk to all the nodes as root.

## k0s Kubernetes distribution

I use [k0s](https://k0sproject.io/).
It has its own delcarative
[k0sctl](https://github.com/k0sproject/k0sctl) tool
which makes deployments simple,
and it has useful optional Kubernetes features built in.

* A single binary with dependencies baked in,
  including etcd and coredns
* Networking with kube-router
* Cluster HA with VRRP

For more details on your choices here, see [Kubernetes distribution]({{< ref "kubernetes-distribution" >}}).

## Prerequisites on each node

I use my own Alpine Linux -based {{< repolink "psyopsOS" >}},
but in these labnotes I'll just treat it like a regular Alpine system.
It should translate pretty well to other Linux distributions too.

* k0s itself doesn't actually need to be installed on each node in advance;
  `k0sctl` will do that for us later.
* Alpine packages:
  ```sh
  apk add containerd containerd-ctr cri-tools sgdisk wireguard-tools
  ```
  * `cri-tools` for `crictl`, which is useful when troubleshooting
  * `sgdisk` for `sgdisk --zap-all /dev/XXX` when cleaning up and redeploying a Ceph cluster
  * `wireguard-tools` to support encrypted networking between the nodes

## Prerequisites on your workstation

* [k0sctl](https://github.com/k0sproject/k0sctl):
  an installation and management tool that talks to all the nodes.
* [flux](https://fluxcd.io/):
  automatic deployment of apps based on a Git repository.
* [age](https://github.com/FiloSottile/age):
  a file encryption tool.
* [sops](https://getsops.io/):
  a tool built on age that can encrypt data in YAML files.
  Flux can store an age key and decrypt sops files in the cluster,
  allowing us to safely keep secrets in Git.
* [helm](https://helm.sh) (optional):
  a package manager for Kubernetes.
  In theory Flux can handle this for us entirely within the cluster,
  but it's nice to have the command available for troubleshooting.
