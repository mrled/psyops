---
title: metallb
weight: 20
---

See {{< repolink "kubernasty/crust/metallb/kustomization.yaml" >}}.

That file installs the metallb controller,
including L2Advertisement and IPAddressPool CRDs,
which allows the cluster to accept traffic on the IP address(es) in the pool.

