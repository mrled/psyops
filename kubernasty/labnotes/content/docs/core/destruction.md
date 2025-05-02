---
title: Destruction
weight: 80
---

A few steps to remember when tearing down a cluster.

* Stop the k0s service on the nodes
  (this stops all containers that k0s started too)
* Delete cluster state
* Delete partition tables on disks usedd by [Ceph]({{< ref ceph >}})

Something like this on each node:

```sh
# Stop services
rc-service k0scontroller stop
rc-service containerd stop

# Remove old cluster config/state.
rm -rf /var/lib/k0s /etc/k0s

# Delete partition tables on Ceph disks
sgdisk --zap-all /dev/XXX
```