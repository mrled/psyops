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

See also:

* Why we use [IngressRoute]({{< ref ingressroute >}}) instead of Ingress
* Why [we can't use traefik]({{< ref "traefik-cert-manager" >}}) for certificate creation

## First bringup

The first time deploying a cluster from scratch,
I recommend doing these ingress steps in stages:

0. Empty clustert
1. Deploy a [whoami](https://hub.docker.com/r/containous/whoami) container
   or some other dead simple HTTP container.
   Add a Kubernetes `Service` to give it a consistent network name,
   using the `default` namespace,
   so the Service has a hostname of e.g. `whoami.default.svc.cluster.local`.
2. Access it from within the cluster like
   `kubectl run -it --rm curlimages/curl -- curl http://whoami.default.svc.cluster.local`.
   Note that you can't access it from outside the cluster.
3. Add Traefik and a whoami Ingress using your domain name,
   and curl from outside the cluster with e.g.
   `curl http://whoami.example.com`.
4. Add cert-manager and a self-signed cert,
   and make HTTPS with with `curl -k https://whoami.example.com`.
   (`-k` ignores TLS errors.)
5. Add a Let's Encrypt issuer that issues from the **staging** Let's Encrypt servers,
   and make HTTPS work with `curl -k https://whoami.example.com`.
   The staging servers do not issue trusted TLS certs,
   but they resolve any problems with your DNS challenge setup.
   Production servers have very long (7d) backoff periods during which you absolutely cannot issue any certs,
   so you wan to make staging work first.
6. Add a Let's Encrypt production issuer
   and make HTTPS work with `curl https://whoami.example.com` (without `-k`).
7. Add HTTPS middleware,
   and make sure that `http://whoami.example.com` redirects to `https://whoami.example.com`
   (test with `curl -L`, which follows 3xx redirects).

Once that's done, you can delete the `whoami` deployment,
and use [Flux]({{< ref "flux-gitops" >}}) to deploy all the other services directly.
