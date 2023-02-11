---
weight: 10
title: Troubleshooting
---

jesus h christ this is the most insane system i've ever seen in my life

## Kubernetes basics

* `kubectl get nodes` shows all nodes
* Everything is in a 'namespace'.
  If you do a `kubectl get ...` or similar command that returns nothing, try looking in all namespaces with `-A`.
  `kubectl get pods -A` shows all pods in all namespaces
* In general, `kubectl get <RESOURCE TYPE>` lists resources,
  while `kubectl describe <RESOURCE TYPE>` shows details about them;
  kind of like `ls` and `cat` but for Kubernetes objects.
* `kubectl logs -n <NAMESPACE> <PODNAME>` shows the logs for a particular pod
* `kubectl api-resources` shows a list of all resources that your Kubernetes cluster knows about --
  resources like Pods, DaemonSets, Ingresses, etc.
* `kubectl describe <RESOURCE>` provides some documentation on a resource type
* You can apply a YAML manifest file with `kubectl apply -f filename.yml`.
  This works with stdin, so you can `cat filename.yml | kubectl apply -f -`.
* You can remove objects defined in a manifest file with `kubectl delete -f filename.yml`.
* You can exec into containers with
  `kubectl exec --stdin --tty <container> -n <namespace> -- /bin/bash`.

### k3s Traefik basics

* Traefik defines an `IngressRoute` resource --
  **if you see `IngressRoute`, it's Traefik-specific**.
* `IngressRoute` resources is how you actually allow a client outside the cluster to talk to a service running in a pod.
* This is an example of a "Custom Resource Definition", or CRD.
  Installing Traefik via the official manifest also installs the CRDs like `IngressRoute`.

### Flux basics

* You definitely want to read the
  [troubleshooting guide](https://fluxcd.io/flux/cheatsheets/troubleshooting).
* Specifically note that Flux ships some CRDs which are also in k3s,
  so you have to use a fully qualified CRD names.

## What does 'Evicted' mean?

```
> kubectl get pods -A
NAMESPACE      NAME                                       READY   STATUS      RESTARTS        AGE
cert-manager   cert-manager-6544c44c6b-tlrn9              1/1     Running     0               139m
cert-manager   cert-manager-cainjector-5687864d5f-g4275   1/1     Running     0               139m
cert-manager   cert-manager-webhook-785bb86798-xd264      1/1     Running     0               139m
kube-system    coredns-d76bd69b-ktqlt                     1/1     Running     0               3h52m
kube-system    helm-install-traefik-crd-knpq4             0/1     Completed   0               3h52m
kube-system    helm-install-traefik-w9gx2                 0/1     Completed   0               10m
kube-system    kube-vip-ds-4s9q2                          1/1     Running     2 (3h25m ago)   3h52m
kube-system    kube-vip-ds-pc4fk                          0/1     Evicted     0               6m56s
kube-system    kube-vip-ds-q64tw                          1/1     Running     0               3h23m
kube-system    local-path-provisioner-6c79684f77-t4lqd    1/1     Running     0               3h52m
kube-system    metrics-server-7cd5fcb6b7-dsdmd            1/1     Running     0               3h52m
kube-system    svclb-traefik-27gq9                        0/2     Evicted     0               6m56s
kube-system    svclb-traefik-hmlhp                        0/2     Pending     0               10m
kube-system    svclb-traefik-vghh6                        2/2     Running     0               14m
kube-system    traefik-5f4f7f44c5-zc8r6                   1/1     Running     0               10m
whoami         whoami-5d4d578786-zjmj5                    1/1     Running     0               3h1m
```

You can investigate this with `kubectl describe`.

```
> kubectl describe pods --namespace kube-system kube-vip-ds-pc4fk | less

# ... shows a bunch of output, with this at the bottom:

Events:
  Type     Reason     Age   From               Message
  ----     ------     ----  ----               -------
  Normal   Scheduled  8m1s  default-scheduler  Successfully assigned kube-system/kube-vip-ds-pc4fk to kenasus
  Warning  Evicted    8m1s  kubelet            The node had condition: [DiskPressure].
```

From there, I ssh'd to kenasus and saw that indeed / was full.
When I fixed that problem, kube-vip and svclb-traefik pods automatically started on that host.

See also:

* <https://www.padok.fr/en/blog/kubernetes-pods-evicted>

## `netstat -an` doesn't include Kubernetes services

I'm used to doing `netstat -an| grep LISTEN` to see what ports are open on a machine.
But Kubernetes services don't seem to show up there.

I'm not sure what to look at instead.
Probably some `kubectl` command.

## traefik, ServiceLB, and kube-vip: wtf

* Kubernetes doesn't have an implementation of LoadBalancer for bare-metal clusters.
  Cloud providers use their own external load balancers, which are configured outside the cluster,
  to do something like this, e.g. AWS load balancer services for AWS EKS clusters.

* kube-vip provides a virtual IP address which moves around to a working cluster node.
  This provides high availability; any node can go down and the cluster keeps working.

---

* See <https://docs.k3s.io/networking>

* k3s ships with traefik by default, as an "ingress controller".
  * e.g. in the output of `kubectl get pods -A`:
        kube-system   traefik-df4ff85d6-f5wxf                   1/1     Running     3 (23m ago)   82m
* k3s ships with ServiceLB (formerli Klipper) by default, as a "load balancer".
  * e.g.:
        kube-system   svclb-traefik-75ce313c-74ggl              2/2     Running     2 (28m ago)   51m
        kube-system   svclb-traefik-75ce313c-9745x              2/2     Running     6 (23m ago)   82m
        kube-system   svclb-traefik-75ce313c-f76c6              2/2     Running     4 (22m ago)   62m
* Some documentation on the web tells you to install traefik, but you don't need to do this, because it comes with k3s.
* To configure traefik, don't change the file that ships with k3s which gets installed to `/var/lib/rancher/k3s/server/manifests/traefik.yaml`.
  Instead, create an extra `HelmChargConfig` manifest that modifies the existing k3s installation.
  See <https://docs.k3s.io/helm#customizing-packaged-components-with-helmchartconfig>
  and <https://github.com/traefik/traefik-helm-chart/tree/master/traefik>
* TODO: show example traefik configuration using HelmChartConfig

## `subset not found`

This error could mean literally anything, because Traefik is insane.

* It might be that the `Service` and `IngressRoute` are being deployed at the same time.
  [Via](https://www.reddit.com/r/kubernetes/comments/lfi838/k3s_traefik_24_tls_doesnt_work/hyxbqfe/).
  "You'll get this error because you create the Service and the IngressRoute resource in one go. It takes longer to create a resource of kind Service than of kind IngressRoute and therefore Traefik can't find the service to your ingress route in the first few seconds. To prevent this error from showing create the IngressRoute resource after your Service resource is created (shouldn't take longer than 5 seconds)."
* I also had this happen when I created a `Service` resource as `type: LoadBalancer` rather than `type: ClusterIP`.
  (`ClusterIP` is actually the default, so you can remove the `spec.type` altogether from the `Service` resource to create a `ClusterIP` service.)

## Writing manifests from scratch

* See [The beginners guide to creating Kubernetes manifests](https://prefetch.net/blog/2019/10/16/the-beginners-guide-to-creating-kubernetes-manifests/).
* [kubeconform](https://github.com/yannh/kubeconform) may help when something gives a bullshit low-level YAML decoding error rather than something useful with the specific key it's having trouble with

## Reboots and power outages

Note that if the entire cluster is taken down
(for instance, by a power outage),
you will need to boot _at least two nodes_ of the control plane
before Kubernetes will start the API server and become ready.

(psyopsOS-specific note: since the OS is stateless and all configuration happens after boot,
the easiest thing to do here is sometimes to just reboot the host again.
This is especially true if the network is not available immediately on boot,
which is sometimes the case for power outages
if eg the network equipment is booting slower than the cluster nodes.)
