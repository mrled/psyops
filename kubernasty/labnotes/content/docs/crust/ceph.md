---
title: Ceph cluster
weight: 35
---

{{< hint warning >}}
**Take care when removing a Ceph cluster from Kubernetes**

See section below on deleting and reinstalling a cluster.
{{< /hint >}}

We will use Ceph for block storage

* `ceph` is the storage cluster software;
  `rook` is a Kubernetes orchestrator that runs Ceph in a k8s cluster.
* The `rook-ceph` HelmChart deploys the Rook operator and CRDs.
  This is not deploying a cluster;
  this is deploying a Kubernetes operator that can deploy Ceph clusters.
* The `rook-ceph-cluster` HelmChart deploys a Ceph cluster.
  It contains the cluster definition/configuration,
  and requires that `rook-ceph` already be present.

## cephalopod

My Rook Ceph cluster is called `cephalopod`.
In case we later need other clusters in the future,
this one will be the main/system cluster.

## Storage classes

Currently, I have 3 nodes, each with a fresh 1TB nvme drive,
which has 256GB dedicated to the /psyopsos-data volume (including Longhorn storage)
and the rest intended for Ceph.
Ceph will use the LVM volume at `/dev/psyopsos_datadiskvg/cephalopodlv`.

```text
jesseta:~# lsblk
NAME                             MAJ:MIN RM   SIZE RO TYPE MOUNTPOINTS
loop0                              7:0    0 122.5M  1 loop /.modloop
sda                                8:0    1   956M  0 disk /mnt/psyops-secret/mount
sdb                                8:16   1   7.5G  0 disk /media/sdb
├─sdb1                             8:17   1   706M  0 part
└─sdb2                             8:18   1   1.4M  0 part
nvme0n1                          259:0    0 931.5G  0 disk
├─psyopsos_datadiskvg-datadisklv 253:0    0   256G  0 lvm  /etc/rancher
│                                                          /var/lib/containerd
│                                                          /var/lib/rancher/k3s
│                                                          /psyopsos-data
└─psyopsos_datadiskvg-cephalopodlv 253:1    0 675.5G  0 lvm
```

It's worth using the software (Ceph) or the cluster name (cephalopod) or both
in the name of the storage class,
as we are already using [Longhorn]({{< ref "longhorn" >}}) too.

I also think the disk class should be in the name.
These hosts can all take a second internal SATA 2.5" disk,
and it is possible we will use it in the future for more storage.

* `cephalopod-nvme-3rep`: a class with 3 replicas

## Logging in

When the cluster is deployed, the operator generates dashboard credentials.

```sh
kubectl -n cephalopod get secret rook-ceph-dashboard-password -o jsonpath="{['data']['password']}" | base64 --decode && echo
```

The username is `admin`.


You can also use the [toolbox container](https://rook.io/docs/rook/v1.10/Troubleshooting/ceph-toolbox/#interactive-toolbox)
to run Ceph commands against the cluster.
Enter the toolbox with

```sh
kubectl -n cephalopod exec -it deploy/rook-ceph-tools -- bash
```

## Deleting and reinstalling a cluster

You must follow the [cleanup procedure](https://rook.io/docs/rook/latest-release/Getting-Started/ceph-teardown/),
or else you may cause problems trying to deploy again later.

When following the cleanup procedure,
note that it expects you to use the same `rook-ceph` namespace for both
the Ceph operator and the Ceph cluster.
We don't do that;
we use `rook-ceph` for the operator only,
and `cephalopod` for this Ceph cluster.

```sh
rookceph_orchestrator_ns=rook-ceph
rookceph_cluster_ns=cephalopod
rookceph_cluster_name=cephalopod

# Delete the CephCluster CRD
kubectl -n $rookceph_cluster_ns patch cephcluster $rookceph_cluster_name --type merge -p '{"spec":{"cleanupPolicy":{"confirmation":"yes-really-destroy-data"}}}'
kubectl -n $rookceph_cluster_ns delete cephcluster $rookceph_cluster_name
# **WARNING**: Don't proceed until the cluster has been actually deleted! Verify with:
kubectl -n $rookceph_cluster_ns get cephcluster

# Remove the finalizers
# Should not be necessary under normal conditions
kubectl -n $rookceph_cluster_ns patch configmap rook-ceph-mon-endpoints --type merge -p '{"metadata":{"finalizers": []}}'
kubectl -n $rookceph_cluster_ns patch secrets rook-ceph-mon --type merge -p '{"metadata":{"finalizers": []}}'

# Removing the Cluster CRD finalizers
# This should not be necessary under normal conditions
for CRD in $(kubectl get crd -n $rookceph_cluster_ns | awk '/ceph.rook.io/ {print $1}'); do
    kubectl get -n $rookceph_cluster_ns "$CRD" -o name |
        xargs -I {} kubectl patch -n $rookceph_cluster_ns {} --type merge -p '{"metadata":{"finalizers": []}}'
done

# Run this to show stuck items so you can remove them manually
# Should not be necessary under normal conditions
kubectl api-resources --verbs=list --namespaced -o name |
  xargs -n 1 kubectl get --show-kind --ignore-not-found -n $rookceph_cluster_ns
```

## Appendix: Why not minio?

Minio looks cool, and I have heard it is less complex than Ceph.
However, its recommended storage driver `directpv`
[cannot be installed via CI/CD](https://github.com/minio/directpv/issues/436).

Ceph doesn't have this limitation, so we're using it for now.
