---
title: Directory layout
---

Store app/service manifests in git, in subdirectories under this one.
Inside each service subdirectory, have a sub-subdir for each type of kubernetes object,
with manifests inside.
[Similar to this suggestion](https://boxunix.com/2020/05/15/a-better-way-of-organizing-your-kubernetes-manifest-files/).

This works well with [Flux]({{< ref flux-gitops >}})
or any other gitops tool.
