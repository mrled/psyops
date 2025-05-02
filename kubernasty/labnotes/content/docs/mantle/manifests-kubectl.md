---
title: Manifests with kubectl
weight: 99
---

The examples here are not required for the cluster,
but it's really helpful to be able to deploy manifests with `kubectl`
before switching everything over to Flux.

## Organizing manifests

See [Directory layout]({{< ref "directory-layout" >}}).

In this section we'll use manifests in {{< repolink "kubernasty/mantle/" >}}.

## whoami service

A useful service for testing.
Deploy with: `kubectl apply -f manifests/mantle/whoami/deployments/whoami.yml`.

Note that this does _not_ include any ingress definitions,
which means that you can't access this deployment from outside your cluster.

## TODO: expand non-CI/CD manifests documentation

...
