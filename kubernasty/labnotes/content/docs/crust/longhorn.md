---
title: Longhorn storage
weight: 30
---

Longhorn is a distributed storage system.

Kubernetes assumes all its pods/services/etc are stateless,
but many apps you might want to run will require state.

Longhorn will consume storage from individual nodes in your cluster
and present it to containers as a regular POSIX filesystem.
It can provide fault tolerance by ensuring two or more copies of certain data exists in the pool.

## Installing

Flux installs this via
{{< repolink "kubernasty/manifests/crust/longhorn/" >}}.
Note that in addition to the `helmrelease`,
we define our own `ingresses`, `certificate`, and `dnsendpoints`.
All resources use the `longhorn-system` namespace,
which is required by Longhorn and cannot be changed.

For configuration, see `spec.values` in
{{< repolink "kubernasty/manifests/crust/longhorn/helmrelease/longhorn.helmrelease.yaml" >}}
and [this section of the Longhorn manual](https://longhorn.io/docs/1.4.0/advanced-resources/deploy/customizing-default-settings/).
I use a custom data path due to the undrelying OS
(TODO: add useful link to psyopsOS here),
but other configuration can be done in the Longhorn UI later.

Once these files are added to the repo and pushed,
we can monitor the deployment with this command.
Don't proceed until all pods and certs are READY.

```sh
kubectl describe kustomization longhorn -n flux-system
kubectl get pods -n longhorn-system
kubectl get certs -n longhorn-system
```

Once that's done, browse to the admin UI at <https://longhorn.kubernasty.micahrl.com/>,
and log in with the `clusteradmin` user.

## Configuring Longhorn

* Change the data path as appropriate
* TODO: can you set a default data path without having to change it for each node?
  On my psyopsOS nodes I want it to always be `/psyopsos-data/roles/k3s/longhorn/data`.
* TODO: configure Longhorn backups
* TODO: test Longhorn restores
