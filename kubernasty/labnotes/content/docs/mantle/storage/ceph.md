---
title: Ceph cluster
---

{{< hint warning >}}
**Take care when removing a Ceph cluster from Kubernetes**

See section below on deleting and reinstalling a cluster.
{{< /hint >}}

## Choosing Ceph

See [Storage options]({{< ref "storage-options" >}}) for more thoughts about storage in Kubernetes.

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

Currently, I have 3 nodes, each with a fresh 1TB nvme drive intended for Ceph.
They also have SSDs which are dedicated to the /psyopsos-data volume.
Ceph cannot encrypt disks unless it owns the entire disk :(.

```text
jesseta:~# lsblk
NAME                                 MAJ:MIN RM   SIZE RO TYPE  MOUNTPOINTS
loop0                                  7:0    0   537M  1 loop  /media/root-ro
loop1                                  7:1    0   151M  1 loop  /.modloop
sda                                    8:0    0 238.5G  0 disk
└─sda1                                 8:1    0 238.5G  0 part
  └─psyopsosdata                     253:0    0 238.5G  0 crypt
    └─psyopsos_datadiskvg-datadisklv 253:1    0 238.5G  0 lvm   /var/lib/k0s/kubelet/pods/ab22338a-2ca6-45ef-94c8-f1f1eade25d0/volume-subpaths/initsetup/configurator/6
                                                                /var/lib/k0s/kubelet/pods/ab22338a-2ca6-45ef-94c8-f1f1eade25d0/volume-subpaths/initsetup/configurator/5
                                                                /var/lib/k0s/kubelet/pods/e92a7724-4a38-433d-bab1-b264faca7bda/volume-subpaths/config/authelia/0
                                                                /var/lib/k0s/kubelet
                                                                /var/lib/containerd
                                                                /var/lib/k0s
                                                                /psyopsos-data
sdb                                    8:16   1  28.7G  0 disk
├─sdb1                                 8:17   1   128M  0 part
├─sdb2                                 8:18   1   128M  0 part  /mnt/psyops-secret/mount
├─sdb3                                 8:19   1   1.5G  0 part
└─sdb4                                 8:20   1   1.5G  0 part  /mnt/psyopsOS/b
nvme0n1                              259:0    0 931.5G  0 disk
```

It's worth using the software (Ceph) or the cluster name (cephalopod) or both
in the name of the storage class,
in case we add other storage classes like Longhorn,
per-node ephemeral storage, etc.

I also think the disk class should be in the name,
like nvme, ssd, hdd, etc.

## Ceph supported storage types

1. Block storage pools: a block device (basically a virtual disk) that can be attached to only one pod at a time
2. CephFS: a RWX/Read-Write-Many filesystem that can be mounted to multiple pods for writing at once
3. Object storage: S3 compatible API

It can also do other stuff, like NFS and iSCSI, but I don't need any of that right now.

Ceph issues warnings for any storage pool that is not redundant via replicas or erasure coding.
You can create single-replica pools,
but Ceph will warn you about this constantly,
and it won't allow itself to do regular maintenance that requires stopping its storage daemons ("OSDs"),
because when the daemon is stopped the pool will be completely unavailable.
**For this reason, you probably want at least 2 replicas for any storage pool you create.**
This is true even if there is redundancy at another level,
like hardware RAID,
or database clustering.

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

## Ceph object storage

### Create object bucket claim

Create `ObjectBucketClaim` resources to create a bucket and key pair automatically.
This will create an associated Secret resource with the same name
with `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` properties.
These keys automatically have read/write access to the bucket.

These are easier to automate, because you get a bucket and credentials right away.
The secret is created in the same namespace as the OBC.
I think there is supposed to be a way to create multiple OBCs (and credentials) for the same bucket,
but I haven't been able to make that work;
my workaround is to create a Job to annotate the credentials secret with reflector properties,
see {{ repolink "kubernasty/applications/argowf/Job.reflect-argowf-artifacts-secret.yaml }}.

See also the `cluster.sh` function `kaws_bucketclaim`.

### Create object storage users directly

Create `CephObjectStoreUser` resources to get an S3 user with permissions to talk to a bucket.
This will create an associated Secret resource with `AccessKey` and `SecretKey` properties.
The secrets will be named `rook-ceph-object-user-$objStoreName-$userName`,
so a user created for the `myObjects` object store is called `bob`
the secret will be `rook-ceph-object-user-myObjects-bob`.
You will then need to apply a policy to a bucket in order for the user to have access to anything.
Because of this, these are harder to automate.

See also the `cluster.sh` function `kaws_cephuser`.

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

### Ceph node planned maintenance

Migrate all Ceph data off the node:

```sh
# find the tools pod
toolspod=$(kubectl -n rook-ceph get pod -l app=rook-ceph-tools -o jsonpath='{.items[0].metadata.name}')

# Tell Ceph to migrate PGs off the OSDs on that node
osdpods=$(kubectl -n rook-ceph get pods --field-selector spec.nodeName=${node} -l app=rook-ceph-osd -o jsonpath='{range .items[*]}{.metadata.name}{"\n"}{end}')

# for each OSD pod, extract its ID and run ceph osd out inside the tools pod
osdids=""
for pod in $osdpods; do
  osdid=$(kubectl -n rook-ceph get pod $pod -o jsonpath='{.spec.containers[0].env[?(@.name=="ROOK_OSD_ID")].value}')
  if test "$osdid"; then
    echo "OSD ID: $osdid    POD: $pod"
    osdids="${osdids} $osdid"
    kubectl -n rook-ceph exec $toolspod -- ceph osd out $osdid
  fi
done

# Wait for no recovery io
watch kubectl -n rook-ceph exec $toolspod -- ceph -s
```

That command will show results like:

```text
Every 2.0s: kubectl -n rook-ceph exec rook-ceph-tools-67bf494bc8-s7fp5 -- ceph -s                                                               Naragua: 12:21:12

  cluster:
    id:     fbe42f47-44d7-4ba1-b63e-cee394eb7574
    health: HEALTH_OK

  services:
    mon: 3 daemons, quorum a,b,c (age 2w)
    mgr: b(active, since 2h), standbys: a
    mds: 1/1 daemons up, 1 hot standby
    osd: 4 osds: 4 up (since 2h), 3 in (since 13m); 6 remapped pgs
    rgw: 2 daemons active (2 hosts, 1 zones)

  data:
    volumes: 1/1 healthy
    pools:   14 pools, 63 pgs
    objects: 26.71k objects, 74 GiB
    usage:   120 GiB used, 2.6 TiB / 2.7 TiB avail
    pgs:     10297/62337 objects misplaced (16.518%)
             57 active+clean
             5  active+remapped+backfill_wait
             1  active+remapped+backfilling

  io:
    client:   1.4 KiB/s rd, 121 KiB/s wr, 2 op/s rd, 14 op/s wr
    recovery: 44 MiB/s, 11 objects/s
```

While there is recovery io at the end, it's still moving PGs around.
Wait for that to finish before proceeding.

Now you can do your maintenance.

When the node is back:

```sh
# for each OSD pod, extract its ID and run ceph osd in inside the tools pod
for osdid in $osdids; do
  kubectl -n rook-ceph exec $toolspod -- ceph osd in $osdid
done
```

### Stale MONs

A MON is locked to a specific Kubernetes node, see <https://github.com/rook/rook/discussions/12292>
If you take a node down, when it comes back up, it might not be able to schedule the mon the same way.
To handle that, you may need to fail over the mon primary. (...?)

I had a situation where Ceph saw mons a/b/d but Kubernetes only had pods for mons a/d,
and was trying to start mon e but was prevented by pod affinity rules.

```text
> kubectl -n rook-ceph exec deploy/rook-ceph-tools -- ceph mon stat
e5: 3 mons at {a=v2:10.104.72.254:3300/0,b=v2:10.102.76.185:3300/0,d=[v2:10.100.179.135:3300/0,v1:10.100.179.135:6789/0]} removed_ranks: {2} disallowed_leaders: {}, election epoch 178, leader 0 a, quorum 0,2 a,d
```

These pods were created (mon-e was not able to be scheduled):

```text
│ rook-ceph-mon-a-6fd76d4f76-jbj42
│ rook-ceph-mon-d-665f6f6d47-bfcl8
│ rook-ceph-mon-e-859bf9bd-jvd67
```

I had to remove the stale mon b from ceph,
and stale mon b resources from Kubernetes:

```sh
kubectl -n rook-ceph exec deploy/rook-ceph-tools -- ceph mon remove b
kubectl delete -n rook-ceph svc rook-ceph-mon-b
kubectl delete -n rook-ceph deployment rook-ceph-mon-b
kubectl delete -n rook-ceph endpoints rook-ceph-mon-b
```

That solved the pod affinity problem - mon e could then be scheduled on the node that formerly held mon b.

### HEALTH_WARN: 1 mgr modules have recently crashed

You might see errors like this:

```text
  cluster:
    id:     fbe42f47-44d7-4ba1-b63e-cee394eb7574
    health: HEALTH_WARN
            9 mgr modules have recently crashed
```

To fix this you can archive crashes:

```sh
kubectl -n rook-ceph exec $toolspod -- ceph crash archive-all
```

###

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

## Adding a node

To add a new node after Ceph comes up:

* Add it to the CephCluster resource

## Appendix: Caveats

* You cannot encrypt a block device with dmcrypt and then give it to Rook Ceph,
  although Rook Ceph can encrypt a raw block device.
  That is, you have to let Rook handle the encryption if you want encryption.
* You cannot give Rook Ceph an unencrypted _partition_ and set it to `encryptedDevice: "true"`.
  Apparently this only works with a whole disk? What the fuck man.
  <https://github.com/rook/rook/issues/10911>
