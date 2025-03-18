---
title: Bootstrapping
---

(See also [git-self-hosted]({{< ref "git-self-hosted" >}}))

Bootstrapping a Kubernetes cluster can be difficult,
depending on what you want the cluster to handle.

## External resources

Keeping some things out of scope of the cluster can make your life easier when bootstrapping the cluster.

* DNS: I use Route53
* HTTPS certificates: you really need a trusted CA for this like Let's Encrypt.
  For many use cases, this also requires programmatic DNS access,
  which is theoretically possible to host yourself
  but a topic complex enough on its own that you need to go with an external provider like Route53.
  (Programmatic DNS is required for wildard certs,
  and for any cert you might want to use for a DNS name pointing to an internal IP address like 192.168.0.0/16.)
* Trusting an external container registry will make your life much easier,
  whether that's the public Docker registry,
  GitHub's free open source registries,
  AWS ECR,
  or something else.
* A git repository for Flux or Argo.
  If this is in the cluster, this takes some special planning.
  <https://kubefirst.io/> have a whole product around deploying this with in-cluster GitLab and ArgoCD.
* This kind of doesn't fit here, but you also need to be able to dedicate an IP address to your ingress.
  Really this means somewhere with real port 443 (and more) that you can use.

## Circular dependencies

Let's say you wanted to build a cluster that would use Flux for CI/CD,
and would also host the Git repository in an in-cluster git server.
This is a circular dependency:
The git server is deployed by Flux,
which requires the git server to be set up.

To get around this you can carefully deploy with `kubectl apply -f ...` when bootstrapping.

## Limited Kubernetes primitives

In Kubernetes, you *can* do anything, but some things are hard to do without primitives.

## A container registry

Let's say you want to use a Git repository for Flux as above,
and you want to use a customized container for the Git repository pod,
and you also want to host the container registry in cluster.

However, the cluster cannot talk to the container unless you expose it outside the cluster.
E.g. with an Ingress.

### Certificates

Docker and CRI tooling, including `docker`, `podman`, `buildah`,
the container pulling component of the `kubelet` running on each cluster node, etc
all very much want to insist on HTTPS certificates.

If you fight them on this, you'll have to configure each tool separately to allow the insecure container registry.
(This seems egregious to me because who is building a cluster on an untrusted network?)
This includes configuring each Kubernetes node outside of Kubernetes itself.

You can use `cert-manager` to generate self-signed certificates for this,
but this also requires configuring each tool separately to allow the insecure registry,
including configuring each individual Kubernetes node.
In some cases, you have to actually modify the list of trusted certificate authorities on the entire system.
Ridiculous!

Automatic updates for `cert-manager` certificates are not possible out of the box securely.
You can use `reflector` to copy a secret,
but you can't copy only a cert (without the private key).
You can use KEDA to perform tasks on certain cluster events,
but it can't see when an individual secret (the CA cert) is renewed.

You could generate self-signed certificates outside of the cluster for this
and then import them into the cluster, but then they won't get automatically updated.
You can have `cert-manager` do it one time and produce a CA cert valid for 20 years,
and then copy just the cert into a configmap for use elsewhere.

Or you could get real certs from Let's Encrypt or another ACME provider.
This requires using a public DNS name (not `registry.NAMESPACE.cluster.local`)
for the registry's hostname,
and exposing the registry outside of the cluster which might not be otherwise required.
It also requires all cluster use to go through your ingress controller.
If something goes wrong with cert generation --
which can happen with very restrictive ACME providers like Let's Encrypt
who blacklist you for too many requests --
pulling containers will be broken for the entire cluster.
