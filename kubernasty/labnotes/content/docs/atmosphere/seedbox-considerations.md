---
title: Seedbox considerations
---

Currently, I have a separaet single-node Kubernetes deployment for my seedbox.
Really it's like an complicated Docker Compose stack.
{{< repolink "seedboxk8s" >}}.

Should I merge that into the main Kubernasty cluster, or not?

Pros of a combined cluster:

* Simpler to manage once the cluster is up
* I can set up common infrastructure once:
  * Backups
  * Container registry
  * CI/CD pipelines
  * Container updates

Pros of separate clusters:

* Currently, the seedbox is on entirely separate hardware, which is preferable for security reasons
* The seedbox is not dependent on the more complicated kubernasty cluster,
  so disaster recovery is easier
  (although this is kind of tempered by a much dumber CI/CD pipeline setup, so maybe not actually a win)

Complications and considerations of combining clusters

* Do I need more powerful nodes for Plex and ErsatzTV?
* The Seedbox kustomizations use configmap variable interpolation, while the Kubernasty ones don't
