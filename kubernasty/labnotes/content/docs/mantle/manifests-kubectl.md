---
title: Manifests with kubectl
weight: 99
---

The examples here are not required for the cluster,
but it's really helpful to be able to deploy manifests with `kubectl`
before switching everything over to Flux.

* Note that Kubernetes stores all of the manifests in its etcd database,
  but you should probably keep your own copy here so you know how the services work.
  There are gitops tools like argocd that can automatically apply them for you,
  but for a tiny home cluster you can also just save them to git and apply them on the command line yourself.
* You can run `kubectl` on any machine with network access to the cluster;
  you don't have to ssh to one of the cluster nodes first.
  (This also means you don't have to keep the git repo checked out on your cluster node(s).)
  See the k3s [Cluster Access page](https://docs.k3s.io/cluster-access) for instructions;
  basically you copy `/etc/rancher/k3s/k3s.yaml` and change the `server` to your server's IP.
  In this cluster, we use `kube-vip` to create a floating VIP on the cluster network,
  so wait to do this step until `kube-vip` is configured,
  and use the VIP (in my case `192.168.1.200`) as the `server` in the kube config.
  Save it to `~/.kube/config` on the machine you'll run `kubectl` from.
  I actually save mine to the normal place for psyops secrets in `/secrets/psyops-secrets/kubernasty/kubeconfig.yml`
  and set `KUBECONFIG=/secrets/psyops-secrets/kubernasty/kubeconfig.yml` instead.

## Organizing manifests

See [Directory layout]({{< ref "directory-layout" >}}).

In this section we'll use manifests in {{< repolink "kubernasty/mantle/" >}}.

## whoami service

A useful service for testing.
Deploy with: `kubectl apply -f manifests/mantle/whoami/deployments/whoami.yml`.

Note that this does _not_ include any ingress definitions,
which means that you can't access this deployment from outside your cluster.

## TODO: expand non-CI/CD manifests documentation

...
