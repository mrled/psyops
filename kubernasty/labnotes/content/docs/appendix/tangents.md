---
title: Tangents
---

A few tangential things I needed in the course of building the cluster

## Resizing filesystems and volumes

Originally, kubernasty nodes were created in progfiguration
with the volume group taking up 100% of the available space on the block device.
With the need for minio or ceph to have a raw block device of its own,
we needed to change this.

* My disks are like 238GB disks
* The new datadisk role in progfiguration will fill up just 50% for new k3s nodes,
  but it won't go back and fix existing nodes. I need to do that myself.
* Going to just eyeball 50%; the exact amount doesn't matter.
* Stop k3s, unmount /psyopsos-data; see [cluster destruction]({{< ref "destruction" >}}).
* You may need to use `lsof +D /psyopsos-data` to find all relevant processes

Then:

```sh
umount /psyopsos-data

# resize2fs requires an e2fsck before each run
e2fsck -f /dev/mapper/psyopsos_datadiskvg-datadisklv
# Size it to BELOW what we think the final total will be
resize2fs /dev/mapper/psyopsos_datadiskvg-datadisklv 100G
# This resizes the underlying volume
lvresize --size 120g /dev/psyopsos_datadiskvg/datadisklv
# resize2fs requires an e2fsck before each run
e2fsck -f /dev/mapper/psyopsos_datadiskvg-datadisklv
# Without a size, it fills to the max of the (newly shrunk) volume
resize2fs /dev/mapper/psyopsos_datadiskvg-datadisklv
```

## Replacing a Kubernetes node

For proactive replacments, where the node is still online:

* Drain it, like `kubectl drain <node name> --delete-local-data --force --ignore-daemonsets`
* Delete it, like `kubectl delete node <node name>`
* You may wish to also follow the instructions in [Cluster destruction]({{< ref "destruction" >}})
  to kill various process that hang around,
  but I don't believe this is necessary unless you want to re-add the node without rebooting.
* Shut down the node

For reactive replacment, where the node hardware fails,
you have to just delete it with `kubectl delelete node <node name>`.

Then add the new node:

* Boot the node
* Follow adding secondary node instructions in [Cluster creation]({{< ref "creation" >}}).
* Longhorn should automatically replicate data to the new node,
  DaemonSets should deploy automatically, etc.
* TODO: Can Longhorn automatically remove old nodes?
  The old node object sticks around as failed,
  even if you create a new node with the same name as the old one.
  Actually, it looks like it cleans them up eventually, but it seems to take hours/days.
