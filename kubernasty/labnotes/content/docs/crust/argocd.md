---
title: Argo CD
weight: 90
---

Install [recommendation](https://argo-cd.readthedocs.io/en/stable/operator-manual/installation/) I should probably be using elsewhere:

> The Argo CD manifests can also be installed using Kustomize. It is recommended to include the manifest as a remote resource and apply additional customizations using Kustomize patches.

I didn't know you could do this, but it seems like a good solution.

I think Flux will decrypt patches too,
so I think this will even work for patching secrets?
