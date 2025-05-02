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
