---
title: Choosing a Kubernetes distribution
---

This cluster uses [k0s](https://k0sproject.io).

Vanilla Kubernetes is much more manual, and requires making a lot more choices.
For instance, you have to choose a cluster data store,
and deploy it externally.
Kubernetes distributions might include a datastore for you ---
k0s includes etcd in the binary and configures it with the same configuration file,
so that it feels like a part of Kubernetes itself,
even though it's a pluggable dependency
for which you could choose an alternative if you like.

Other options:

* k3s.
  I used this in the first versions of this cluster.
  * No cluster HA (I added kube-vip)
  * Required some networking CNI binary installed separately I forget
  * Required manual cluster bring-up by touching nodes one-by-one.
  * Required all nodes have a network interface with the same name (like `eth0`).
  * Stopping k3s would keep all containers running;
    you had to stop containers in a separate step.

TODO: Add more about Kubernetes distribution options
