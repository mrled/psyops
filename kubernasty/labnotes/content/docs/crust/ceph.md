---
title: Ceph cluster
weight: 35
---

{{< hint warning >}}
**Take care when removing a Ceph cluster from Kubernetes**

See section below on deleting and reinstalling a cluster.
{{< /hint >}}

## Storage options

* Longhorn is a little easier to get started with, and we did use it originally,
  but it is less flexible.
  It uses free disk spaces on an existing filesystem.
  (Is there a performance penalty for that?)
* Ceph is more mature, and more featureful.
  It offers block, object, and filesystem storage.
  It can use raw storage in various formats;
  we use raw block devices here.
* OpenEBS: ?
* SeaweedFS: ?
* Others?

## Choosing Ceph

We will use Ceph for block storage

* `ceph` is the storage cluster software;
  `rook` is a Kubernetes orchestrator that runs Ceph in a k8s cluster.
* The `rook-ceph` HelmChart deploys the Rook operator and CRDs.
  This is not deploying a cluster;
  this is deploying a Kubernetes operator that can deploy Ceph clusters.
* The `rook-ceph-cluster` HelmChart deploys a Ceph cluster.
  It contains the cluster definition/configuration,
  and requires that `rook-ceph` already be present.

## Prerequisite: CSI snapshotter bullshit

* wtf: https://github.com/k3s-io/k3s/issues/2865
* So we have to install the stuff ourselves
* see snapshot-controller directory in manifests/crust
* This is mentioned in <https://rook.io/docs/rook/latest/Troubleshooting/ceph-csi-common-issues/>, along with some troubleshooting steps

I found this after I tried to deploy, and installing it didn't fix the deployment.

* Found the problem with `kubectl -n rook-ceph logs deploy/csi-rbdplugin-provisioner -c csi-snapshotter -f`
* That showed many log lines like this `E0405 22:52:52.850626       1 reflector.go:140] github.com/kubernetes-csi/external-snapshotter/client/v6/informers/externalversions/factory.go:117: Failed to watch *v1.VolumeSnapshotClass: failed to list *v1.VolumeSnapshotClass: the server could not find the requested resource (get volumesnapshotclasses.snapshot.storage.k8s.io)`
* Note that `k get crd -A | grep -i snapshot` should show nothing if the snapshot-controller stuff isn't installed, and should show 3 CRDs if it is installed: `volumesnapshotclasses.snapshot.storage.k8s.io`, `volumesnapshotcontents.snapshot.storage.k8s.io`, `volumesnapshots.snapshot.storage.k8s.io`. After installing snapshot-controller, check to make sure these are present.
* Killed the rbdplugin-provisioner pods in rook-ceph namespace `k delete pod -n rook-ceph csi-rbdplugin-provisioner-68c4484d66-2rvzs csi-rbdplugin-provisioner-68c4484d66-p6h2r`

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

## Deployment

Once Flux notices the manifests are in the repo, it will take a long fucking time to install Ceph.
From a recent install:

* Flux sees the kustomization in the repo and applies it
* The tools pod and the first `mon` pod start quickly
* 21 minutes later, the second `mon` pod starts
* 22 minute slater, the third `mon` pod starts
* (Maybe these are doing some kind of filesystem format? That takes 21 minutes? For some reason?)
* 75 minutes later nothing has happened and I'm going to bed
* 4 hours after the 3rd `mon` pod started, all the other pods started.
  When I woke up the next day I could log in to the web UI.

If you're just looking at a small number of pods with `kubectl get pods -n cephalopod`,
the deployment is not finished.
Read logs and/or just wait.

## Logging in

When the cluster is deployed, the operator generates dashboard credentials.

```sh
kubectl -n cephalopod get secret rook-ceph-dashboard-password -o jsonpath="{['data']['password']}" | base64 --decode && echo
```

The username is `admin`.

## Migrating data between storage classes and volumes

After deploying StatefulSet or other resources with PVCs,
you may need to migrate the data between storage classes.
This requires creating a new volume,
moving the data,
attaching the new volume to the PVC,
and deleting the old volume.

1. Suspend Flux reconciliation
2. Scale down the StatefulSet:
  ```sh
  kubectl scale statefulset NAME -n NAMESPACE --replicas=0
  ```
  When a StatefulSet is scaled down, its PVCs remain.
3. Take a snapshot of each PVC
  ```sh
  apiVersion: snapshot.storage.k8s.io/v1
  kind: VolumeSnapshot
  metadata:
    name: dirsrv-data-dirsrv-0-20250312
    namespace: directory
  spec:
    # Important to use a volume snapshot class that retains data after the PVC is deleted,
    # because we are about to delete and recreate the PVC
    volumeSnapshotClassName: cephalopodblk-retain-snapclass
    source:
      persistentVolumeClaimName: dirsrv-data-dirsrv-0
  ```
  You'll need to do this for all the replicas in the StatefulSet, -0, -1, -2, etc.
  Wait until `k get volumesnapshot NAME -n NAMESPACE`
  shows `ReadyToUse: true` for each.
4. Delete all of the original PVCs from the StatefulSet
  ```sh
  namespace="default"
  pvcname="<volume-claim-template-name>-<statefulset-name>-0"
  k patch pvc -n $namespace $pvcname --type=json -p '[{"op": "remove", "path": "/metadata/finalizers"}]'
  k delete pvc -n $namespace $pvcname
  ```
  Again, you must do this for all replicas in the StatefulSet.
  We have to remove finalizers because by default there will be a `kubernetes.io/pvc-protection` finalizer
  that prevents the PVC from being deleted.
  You can check this with `k describe pvc ...`.
5. Restore PVCs from snapshots, matching the original naming scheme,
  and using the new storage class.
  ```yaml
  apiVersion: v1
  kind: PersistentVolumeClaim
  metadata:
    name: <volume-claim-template-name>-<statefulset-name>-0
    namespace: <namespace>
  spec:
    storageClassName: <new-storage-class>
    dataSource:
      name: my-pvc-snapshot-0
      kind: VolumeSnapshot
      apiGroup: snapshot.storage.k8s.io
    accessModes:
      - ReadWriteOnce
    resources:
      requests:
        storage: 10Gi
  ```
  Again, for all replicas in the StatefulSet.
6. Modify the StatefulSet to specify the new `storageClassName`.
7. Scale the StatefulSet back to its original number of replicas
  ```sh
  k scale statefulset NAME -n NAMESPACE --replicas=COUNT
  ```

## Troubleshooting

You can also use the [toolbox container](https://rook.io/docs/rook/v1.10/Troubleshooting/ceph-toolbox/#interactive-toolbox)
to run Ceph commands against the cluster.
Enter the toolbox with

```sh
kubectl -n cephalopod exec -it deploy/rook-ceph-tools -- bash
```

Then you can run commands like `ceph -s`:

```text
[root@kenasus /]# ceph -s
  cluster:
    id:     caf4f951-74a8-490e-bcf1-599a6acd4c04
    health: HEALTH_WARN
            1 MDSs report slow metadata IOs
            Reduced data availability: 60 pgs inactive
            1 daemons have recently crashed
            OSD count 0 < osd_pool_default_size 3

  services:
    mon: 3 daemons, quorum a,b,c (age 32m)
    mgr: a(active, since 43m), standbys: b
    mds: 1/1 daemons up, 1 standby
    osd: 0 osds: 0 up, 0 in

  data:
    volumes: 1/1 healthy
    pools:   11 pools, 60 pgs
    objects: 0 objects, 0 B
    usage:   0 B used, 0 B / 0 B avail
    pgs:     100.000% pgs unknown
             60 unknown
```

Useful commands:

* `ceph -s`
* `ceph health detail`

### What if 0 OSDs are reported?

In the previous output, note that it shows 0 OSDs: `osd: 0 osds: 0 up, 0 in`.
How can you investigate this?

You can check the Ceph operator logs from the `rook-ceph` namespace, like
`kubectl logs -n rook-ceph rook-ceph-operator-89bc5cc67-tlgbw`

However, I've gotten more value from looking at the OSD prep containers in the `cephalopod` namespace:

```text
> kubectl get pods -n cephalopod
NAME                                                           READY   STATUS      RESTARTS         AGE
rook-ceph-crashcollector-jesseta-57d49dc484-5hpmt              1/1     Running     0                29m
rook-ceph-crashcollector-kenasus-6bcfddcb57-b5f8g              1/1     Running     0                105m
rook-ceph-crashcollector-zalas-654744f96b-6hb2q                1/1     Running     0                79m
rook-ceph-mds-cephalopod-nvme-3rep-fs-a-6755865c76-fb884       2/2     Running     0                29m
rook-ceph-mds-cephalopod-nvme-3rep-fs-b-5bf9c85bbc-x87nc       2/2     Running     0                105m
rook-ceph-mgr-a-7797bb5bcf-r7dw4                               3/3     Running     0                105m
rook-ceph-mgr-b-54f4c56b64-db9s6                               3/3     Running     0                50m
rook-ceph-mon-a-5bc4cdcc46-hf7lp                               2/2     Running     0                105m
rook-ceph-mon-b-5cd75674d6-6f5kk                               2/2     Running     0                111m
rook-ceph-mon-c-cb7c866c4-jzdqc                                2/2     Running     0                45m
rook-ceph-osd-prepare-jesseta-qpj6l                            0/1     Completed   0                26m
rook-ceph-osd-prepare-kenasus-w2wzp                            0/1     Completed   0                26m
rook-ceph-osd-prepare-zalas-w6ts2                              0/1     Completed   0                26m
rook-ceph-rgw-cephalopod-nvme-3rep-object-a-7555f69bbb-8zszc   1/2     Running     10 (2m42s ago)   41m
rook-ceph-tools-84849c46dc-wwk7t                               1/1     Running     0                105m

> kubectl logs -n cephalopod rook-ceph-osd-prepare-jesseta-qpj6l
...snip...
2023-03-19 20:25:00.974456 W | cephosd: skipping OSD configuration as no devices matched the storage settings for this node "jesseta"
```

Aha. Something wrong with the storage settings.

### How to run the osd-prepare pods again

After changing the configuration in
{{< repolink "kubernasty/manifests/crust/cephalopod/configmaps/cephalopod.overrides.yaml" >}}
to deal with the above issue,
the osd-prepare pods do not automatically restart.
To restart them, you have to restart the operator in the `rook-ceph` namespace.

```sh
kubectl delete pod -n rook-ceph rook-ceph-operator-89bc5cc67-tlgbw
```

**It may take several minutes for the `osd-prepare` pods to restart**.
I'm not sure why this takes so long.
The `AGE` field will reset to 0 when they run.

....... wait a second.

[Apparently](https://rook.io/docs/rook/v1.11/CRDs/Cluster/ceph-cluster-crd/#node-updates)
changing the overrides configmap after the cluster has been created doesn't apply the change AT ALL?
Instead, you have to do
`kubectl -n cephalopod edit cephcluster cephalopod`
and edit it live????????
TODO: Fucking find a better nicer way to deal with this, what the fuck

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
rookceph_cluster_ns=rook-ceph
rookceph_cluster_name=cephalopod

# Delete the CephCluster CRD
kubectl -n $rookceph_cluster_ns patch cephcluster $rookceph_cluster_name --type merge -p '{"spec":{"cleanupPolicy":{"confirmation":"yes-really-destroy-data"}}}'
kubectl -n $rookceph_cluster_ns delete cephcluster $rookceph_cluster_name
# **WARNING**: Don't proceed until the cluster has been actually deleted! Verify with:
kubectl -n $rookceph_cluster_ns get cephcluster
# If it doesn't delete itself for a while, you may need to manually remove some dependent resources.
# I found this in my cluster when I did `kubectl describe cephcluster` and saw a message like
# `CephCluster "cephalopod/cephalopod" will not be deleted until all dependents are removed: CephBlockPool: [cephalopod-nvme-3rep-block], CephFilesystem: [cephalopod-nvme-3rep-fs], CephObjectStore: [cephalopod-nvme-3rep-object]`.
# I had to remove those manually (`kubectl delete cephfilesystem ...`, etc) and then the cluster was removed right away.

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

**It's important to delete Ceph data before reinstalling.**

The first thing we have to do is stop the LVM stuff.

```sh
vgs

vgremove ...

# etc
```

Suggestions from the Ceph docs include:

```sh
DISK="/dev/sdX"

# Zap the disk to a fresh, usable state (zap-all is important, b/c MBR has to be clean)
sgdisk --zap-all $DISK

# Wipe a large portion of the beginning of the disk to remove more LVM metadata that may be present
dd if=/dev/zero of="$DISK" bs=1M count=100 oflag=direct,dsync

# SSDs may be better cleaned with blkdiscard instead of dd
blkdiscard $DISK

# Inform the OS of partition table changes
partprobe $DISK
```

You also have to delete the Ceph data directory specified in `dataDirHostPath`
(`/var/lib/rook` by default).

I have a more nuclear option that makes some assumptions for my environment
and both removes the data directory and wipes the disks that Ceph used.

```sh
#!/bin/sh
set -eu

# WARNING: THIS SCRIPT WILL DELETE ALL CEPH DATA.
# WARNING: THIS SCRIPT ASSUMES ANY DEVICE WITH A CEPH LVM ON IT CAN BE SAFELY WIPED.
#           (Meaning it assumes that any Ceph device is not used for anything else.)

# We have to take special care to remove encrypted Ceph block devices
# If we don't do this, we can still zap/dd/etc it below and it'll work,
# however we might have to reboot, which is annoying.
for mappeddev in /dev/mapper/*; do
    # A result to this command indicates that $mappeddev is an encrypted block device,
    # and $underlyingdev is the underlying block device.
    underlyingdev=$(cryptsetup status "$mappeddev" | grep '  device:' | awk '{print $2}')
    if test "$underlyingdev"; then
        case "$underlyingdev" in /dev/mapper/ceph-*)
            # If the underlying device is a ceph LVM volume, close the encrypted device on top of it
            cryptsetup luksClose "$mappeddev"
            ;;
        esac
    fi
done

# Now look for all ceph LVM devices
for cephdev in /dev/mapper/ceph-*; do
    # First, find the device that contains the LVM volume
    deps=$(dmsetup deps "$cephdev")
    major=$(echo "$deps" | awk '{print $4}' | sed 's/(//' | sed 's/,//')
    minor=$(echo "$deps" | awk '{print $5}' | sed 's/)//')
    physdev=$(ls -l /dev | grep " $major, *$minor " | awk '{print $10}')

    # Remove the LVM volume
    dmsetup remove --force "$cephdev"

    # Remove the LVM volume's physical device
    sgdisk --zap-all $physdev
    dd if=/dev/zero of="$physdev" bs=1M count=100 oflag=direct,dsync
    blkdiscard $physdev
    partprobe $physdev
done

# Remove the ceph data dir
rook_ceph_data_dir="/var/lib/rook"
if test "$rook_ceph_data_dir"; then
    rm -rf "$rook_ceph_data_dir"
fi
```

### Improperly deleted clusters

Ceph is VERY precious about deletion,
which might be a good thing in production but is very annoying in development.

* If you fail to set `yes-really-destroy-data`, the cluster will not delete properly, and you're on your own
* If you do not remove the ceph data dir on the host, a new cluster will not come up properly,
  and will have to be entirely deleted and recreated
* If you do not wipe the disk(s) that ceph used on the host, a new cluster will not come up properly,
  and will have to be entirely deleted and recreated

## Appendix: Why not minio?

Minio looks cool, and I have heard it is less complex than Ceph.
However, its recommended storage driver `directpv`
[cannot be installed via CI/CD](https://github.com/minio/directpv/issues/436).

Ceph doesn't have this limitation, so we're using it for now.

## Appendix: Caveats

* You cannot encrypt a block device with dmcrypt and then give it to Rook Ceph,
  although Rook Ceph can encrypt a raw block device.
  That is, you have to let Rook handle the encryption if you want encryption.
* You cannot give Rook Ceph an unencrypted _partition_ and set it to `encryptedDevice: "true"`.
  Apparently this only works with a whole disk? What the fuck man.
  <https://github.com/rook/rook/issues/10911>
