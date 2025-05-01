---
title: Prerequisites
weight: 11
---

I am using psyopsOS for my cluster.
psyopsOS is an operating system I build based on Alpine Linux;
see {{< repolink "psyopsOS" >}}.

## Other tools to install

### Age

Used for encryption in a few places, including SOPS.

### Gopass

We store our passwords in this.

### SOPS

Flux can decrypt SOPS secrets,
which allows you to commit encrypted secrets to a Git repo and have Flux deploy them automatically.
You need the SOPS binary to do this.

### Helm

We will install [Flux]({{ ref "docs/mantle/flux-gitops" }})
early on in these instructions.
Once installed, Flux will look for kustomize manifests
in a specific directory inside the psyops Git repo
{{< repolink "kubernasty/flux" >}}
and deploy them automatically,
including Helm charts.

That means that in theory,
aside from Kubernetes itself and Flux,
you won't need the Helm binary deployed to your cluster nodes.
However, I recommend installing it anyway,
perhaps on the cluster nodes if you expect to do maintenance from a shell on those nodes,
but at least on your workstation,
as it can help make cluster management easier.

<https://helm.sh>
