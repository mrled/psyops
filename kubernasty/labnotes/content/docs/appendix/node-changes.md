---
title: Node changes
---

## Adding a node

* Add the node in `k0sctl.yaml`, see [creation]({{< ref "creation" >}})
* Add the node in the Ceph cluster, see [ceph]({{< ref "ceph" >}})

## Planned node downtime

Set some vars to make the below easier

```sh
node=NODENAME
```

Migrate all Ceph data off the node as describe4 in [ceph]({{< ref "ceph" >}}), "Ceph node planned maintenance".
Make sure that's totally finished and `ceph -s` says `HEALTH_OK` before continuing.

```sh
# Prevent new pods from being scheduled
kubectl cordon $node

# Drain node (ignore DaemonSets so OSD pods stay until reboot)
# Without --delete-local-data, drain will refust to evict any pod that declares non-removable local data.
kubectl drain $node --ignore-daemonsets --delete-emptydir-data
```

You can now safely perform your maintenance, reboot, swap hardware, etc.

```sh
# After it comes back
kubectl uncordon $node
```

Put the OSD back in the Ceph cluster as per instructions on the Ceph page.

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
