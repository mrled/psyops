---
title: "Ingress"
weight: 30
---

It surprised me to learn that out of the box,
vanilla Kubernetes has no way to accept traffic from outside the cluster
other than port mappings tied to an individual node.
This is obviously not intended for production use;
instead you're supposed to use an appropriate load balancer for your environment
to provide a highly available IP address for the cluster,
and an ingress controller to accept traffic and route it to the correct pods in the cluster.

(Vanilla Kubernetes _also_ has no way to place the Kubernetes control plane on a highly available IP address out of the box,
but [k0s]({{< ref creation >}}) does provide this functionality for us via `controlPlaneLoadBalancing`.)

* metallb for our load balancer
* Traefik for our ingress controller

We'll also configure cert-manager to provision HTTPS certificates for the cluster,
since that's required to have the browser trust any sites we host.
