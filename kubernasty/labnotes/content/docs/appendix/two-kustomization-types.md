---
title: Two kinds of kustomizations
---

When using Flux, you interact with two separate `Kustomization` types.

* `kustomization.kustomize.config.k8s.io`:
  Used by [kustomize](https://kustomize.io/),
  which is now built in to `kubectl apply -k ...`.
  I'll call these **Kustomize overlays**.
* `kustomization.kustomize.toolkit.fluxcd.io`:
  Native to Flux.
  I'll call these **Flux kustomizations**.

See also the Flux FAQ:
[Are there two Kustomization types?](https://fluxcd.io/flux/faq/#are-there-two-kustomization-types)
and the subsequent
[How do I use them together?](https://fluxcd.io/flux/faq/#how-do-i-use-them-together).

imho this was a fucking **terrible** design decision by the Flux team,
and it makes talking about kustomizations really difficult.
