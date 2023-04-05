# snapshot-controller

Kubernetes has a [snapshot controller](https://github.com/kubernetes-csi/external-snapshotter#readme),
but [it isn't installed by default in k3s](https://github.com/k3s-io/k3s/issues/2865).
Apparently per the k3s issue above,
the k3s team recommends the Piraeus chart,
so we'll install it here.
