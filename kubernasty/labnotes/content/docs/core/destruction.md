---
title: Cluster destruction
weight: 80
---

* We use the Alpine k3s package, rather than curlbash'ing the installer.
  This means that we don't get a nice `k3s-uninstall.sh` script for us.
  We do have a `k3s-killall.sh` which we have adapted from upstream.
* See the [uninstall script code](https://github.com/k3s-io/k3s/blob/03885fc38532afcb944c892121ffe96b201fc020/install.sh#L407-L449)
  for more context.

Make an uninstall script like this and run it:

```sh
# Stop all containers and the k3s service itself
# Note: This does unmount /var/lib/rancher/k3s; we have to remount it below
k3s-killall.sh

# This is also necessary for some reason?
killall containerd-shim-runc-v2 traefik

# Unmount a bunch of bullshit that Docker mounts
umount /run/netns/* /var/lib/kubelet/pods/*/volumes/*/*

# Remove old cluster config/state.
# Do NOT remove /var/lib/rancher/k3s because that's an overlay mountpoint on psyopsOS
rm -rf /etc/rancher/k3s /psyopsos-data/overlays/var-lib-rancher-k3s/*

# Recommended in the kube-vip k3s documentation https://kube-vip.io/docs/usage/k3s/
ip addr flush dev lo
ip addr add 127.0.0.1/8 dev lo

# Make sure that /var/lib/rancher/k3s is mounted
mount -o bind /psyopsos-data/overlays/var-lib-rancher-k3s /var/lib/rancher/k3s
```
