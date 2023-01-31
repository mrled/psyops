---
title: Cluster destruction
weight: 80
---

* We use the Alpine k3s package, rather than curlbash'ing the installer.
  This means that we don't get a nice `k3s-uninstall.sh` script for us.
  We do have a `k3s-killall.sh` which we have adapted from upstream.
* On all nodes:
  * Run `k3s-killall.sh`, which will stop all containers and also the k3s service itself
  * `killall containerd-shim-runc-v2 traefik`, which is necessary for some reason
  * `umount /run/netns/* /var/lib/kubelet/pods/*/volumes/*/*`
  * `rm -rf /etc/rancher/k3s /psyopsos-data/overlays/var-lib-rancher-k3s/*` ...
    you don't want to remove `/var/lib/rancher/k3s` because it is an overlay mountpoint on psyopsOS!
  * `ip addr flush dev lo; ip addr add 127.0.0.1/8 dev lo;` as recommended in
    [the kube-vip k3s documentation](https://kube-vip.io/docs/usage/k3s/).
  * **Make sure that `/psyopsos-data/overlays/var-lib-rancher-k3s` is bind-mounted to `/var/lib/rancher/k3s`**,
    I have seen this bind mount be missing when trying to reset my cluster,
    maybe something wrong with my `umount` command above?
* Start over from the top of this document

See the [uninstall script code](https://github.com/k3s-io/k3s/blob/03885fc38532afcb944c892121ffe96b201fc020/install.sh#L407-L449)
for more context.
