---
title: Flux GitOps
weight: 60
---

We'll use Flux for GitOps.

## Bootstrapping Flux

See also the [official Flux documentation](https://fluxcd.io/flux/installation).

* Obtain the `flux` binary from the [releases page](https://github.com/fluxcd/flux2/releases).
* Create a GitHub Personal Access Token.
  (See the official docs for details.)
  I made mine a new-style fine-grained token, rather than a "classic" token with whole-account access.
  I gave it access just to this `mrled/psyops` repo,
  and gave it just `Administration` and `Content` repository permissions.

Now bootstrap.
Bootstrapping is idempotent, so running the bootstrap command multiple times won't hurt anything.

```sh
export GITHUB_TOKEN="<the personal access token created previously>"

flux bootstrap github \
    --owner=mrled \
    --repository=psyops \
    --path=kubernasty/flux \
    --branch=master \
    --personal
```

When I ran this, there was no `kubernasty/flux` subdirectory of this repository;
this was ok, flux created it.

From this point forward, you shouldn't need to apply manifests with `kubectl apply ...` any more.
Instead you can commit manifests to this repository under `kubernasty/flux/<app name>/kustomization.yml`
(with the kustomization optionally referencing other manifests in the same subdirectory)
and Flux will automatically apply them to the cluster.

## TODO: consider enabling Flux earlier

Currently, we've deployed several things by hand, and only added Flux and GitOps at the end.

Perhaps this is a mistake.
Flux doesn't have a web UI and doesn't need ingresses, certificates, load balancers, or even kube-vip to work.
We could deploy Flux as soon as the cluster is up,
and leave configuration of all of those items to Flux itself.

On the other hand, progressing from a new cluster to `kubectl apply` to Flux and GitOps seems natural.
