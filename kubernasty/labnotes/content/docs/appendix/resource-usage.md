---
title: Resource usage
---

You need to manage the resource requests made by the pods you deploy,
or your cluster may hit capacity and stop working.
It isn't always obvious that this is the problem when this is happening.

In Kubernetes, a resource _request_ is a minimum amount required for the pod to run.
If you need 1 CPU but there is not a whole CPU available in the cluster,
the pod refuses to start.
A resource _limit_ is the maximum amount alloted for the pod.

The most obvious resources to track are CPU and memory.
Kubernetes can keep track of other resources as well, like hugepages.

## Tracking resource usage

I use a function like this (saved in {{< repolink "kubernasty/cluster.sh" >}}):

```sh
kube_resources() {
    if test "$1"; then
        namespace="--namespace $1"
        pod_ns_note="(in namespace $1)"
    else
        namespace="--all-namespaces"
        pod_ns_note="(all namespaces)"
    fi
    columns="Name:metadata.name"
    columns="$columns,CPU-request:spec.containers[*].resources.requests.cpu"
    columns="$columns,CPU-limit:spec.containers[*].resources.limits.cpu"
    columns="$columns,RAM-request:spec.containers[*].resources.requests.memory"
    columns="$columns,RAM-limit:spec.containers[*].resources.limits.memory"

    echo "Pod resource requests and limits $pod_ns_note:"
    kubectl get pods $namespace -o custom-columns="$columns"

    echo
    echo
    # This is always for all namespaces bc its node-wide
    echo "Node resource requests and limits (all namespaces):"
    kubectl describe nodes | grep -A 3 "Resource .*Requests .*Limits"
    echo
}
```

This shows the resources of all the pods in the cluster
(optionally restricted by namespace)
and the capacity of all the nodes in the cluster.

It shows output like this (truncated):

```text
Pod resource requests and limits:
Name                                                           CPU-request                CPU-limit                  RAM-request                     RAM-limit
csi-rbdplugin-provisioner-68c4484d66-zsxlf                     100m,100m,100m,100m,250m   200m,200m,200m,200m,500m   128Mi,128Mi,128Mi,128Mi,512Mi   256Mi,256Mi,256Mi,256Mi,1Gi
rook-ceph-operator-569fd8f9bf-rx5hp                            20m                        500m                       128Mi                           512Mi
uptime-kuma-0                                                  <none>                     <none>                     <none>                          <none>


Node resource requests and limits:
  Resource           Requests       Limits
  --------           --------       ------
  cpu                4960m (124%)   16300m (407%)
  memory             13332Mi (41%)  23300Mi (72%)
--
  Resource           Requests       Limits
  --------           --------       ------
  cpu                4180m (104%)   11700m (292%)
  memory             11816Mi (36%)  19726Mi (61%)
--
  Resource           Requests      Limits
  --------           --------      ------
  cpu                3760m (94%)   6200m (155%)
  memory             6600Mi (20%)  10752Mi (33%)
```

## Symptoms of resource contention

* The biggest thing to notice is if the CPU/RAM _requests_ are near or above 100%.
* Flux may have kustomizations stuck in "Reconciliation in progress" indefinitely
  (see this with `kubectl get kustomizations -n flux-system`)
* Pods wait to start indefinitely

## How to manage resource limits

<https://home.robusta.dev/blog/stop-using-cpu-limits> says:

* Set CPU requests (the minimum), but don't set CPU limits (the maximum).
  This allows pods to burst CPU usage if they need to.
* Set RAM requests (min) and limits (max), because you cannot reclaim RAM without killing a pod,
  so coming down from a RAM burst is more disruptive.

## What to do if the cluster is over-provisioned

* Make liberal use of `flux suspend kustomization ...`
* Delete any resources that are not in production yet, or that
