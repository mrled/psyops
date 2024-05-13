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
* Browse the [kubectl cheatsheet](https://kubernetes.io/docs/reference/kubectl/cheatsheet/)
  when you're stuck.

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

A few commands that are useful to keep running as you're deploying stuff.
(Run this in separate terminals.)

```sh
watch kubectl get kustomizations -A

watch kubectl get helmrelease -A

watch kubectl get certs -A
```

* When you push a change to Git and want Flux to notice immediately,
  `kubectl annotate --field-manager=flux-client-side-apply --overwrite gitrepository/flux-system -n flux-system reconcile.fluxcd.io/requestedAt="$(date +%s)"`
* If your `helmreleases` are saying things like `initial retries exhausted`,
  you can force them to try again with
  `flux suspend hr -n NAMESPACE RELEASENAME`
  and `flux resume hr -n NAMESPACE RELEASENAME`.
* Note that trying to reconcile a Helm release like that does not necessarily redploy its pods.
  You may also need to `kubectl delete pod -n NAMESPACE PODNAME` too.
* A better thing to do is probably `kubectl delete helmrelease -n NAMESPACE HRNAME`,
  and then `flux reconcile kustomization KUSTOMIZATION_NAME` for the kustomization that deploys that helmrelease.


You will often need to do things in this order:

```sh
kubectl annotate ...

#...

flux reconcile kustomization ...
```

And sometimes may need to delete pods or deployments,
and/or suspend/resume the release,
as well.


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

## Longhorn issues after power outage

* See [#3207](https://github.com/longhorn/longhorn/issues/3207).
* Note errors in `/var/log/k3s.log`
  like `E0217 11:29:42.115751   28640 pod_workers.go:951] "Error syncing pod, skipping" err="unmounted volumes=[data], unattached volumes=[dshm kube-api-access-k7jhz keycloakdb-data-vol data]: timed out waiting for the condition" pod="keycloak/keycloakdb-postgresql-0" podUID=ee7d21e6-b441-4416-a12a-afc004439ade`
* From a longhorn dev:

  > Two options:
  >
  > "You don't need to delete the dangling vol_data.json in the old mountpoint directory by manual.
  > After restart of the longhorn-csi plugin automatically and waiting for several minutes, the pod with a new volume mountpoint will be at Running state again." - in case crashed replica is rescheduled on same node.
  >
  > But If replica has been rescheduled to different node and you have dangling vol_data.json you need to go to
  > /var/lib/kubelet/pods/$pod_id/volumes/kubernetes.io~csi/pvc_$pvc_id/
  > and delete vol_data.json after making sure this is not "live" volume.
  >
  > As Derek said, this is not longhorn bug, that's how kubelet is handling folder cleanup (calling rmdir will always fail if this directory contains anything)

  and

  > I think if it attempts to cleanup it's not live, but you can check volume details in longhorn web ui. If it's not scheduled on that node, it should be safe to delete.

* Deleting that didn't change the error for me. Odd.
* After deleting that one with the exact pod_id (... I can't remember where I got the pod id, lol) I notice that I actually end up with multiples.

  ```text
  # ls -alF /var/lib/kubelet/pods/*/volumes/kubernetes.io\~csi/pvc-bd3cec31-4032-4433-adf6-f436c7834654/vol_data.json
  -rw-r--r-- 1 root root 291 Feb 17 00:27 /var/lib/kubelet/pods/bc52b9ea-b89a-41e3-baee-574d405240fc/volumes/kubernetes.io~csi/pvc-bd3cec31-4032-4433-adf6-f436c7834654/vol_data.json
  -rw-r--r-- 1 root root 291 Feb 17 11:47 /var/lib/kubelet/pods/ee7d21e6-b441-4416-a12a-afc004439ade/volumes/kubernetes.io~csi/pvc-bd3cec31-4032-4433-adf6-f436c7834654/vol_data.json
  ```

* Ok, delete BOTH of those that remain after deleting the first one.
* Still same errors. It created another vol_data.json. Deleting that too, just in case.
* And same errors. So it's just in one directory now, but still seeing errors in `k3s.log` like
  `E0217 12:09:27.160361   28640 nestedpendingoperations.go:348] Operation for "{volumeName:kubernetes.io/csi/driver.longhorn.io^pvc-bd3cec31-4032-4433-adf6-f436c7834654 podName: nodeName:}" failed. No retries permitted until 2023-02-17 12:11:29.160347027 -0600 CST m=+676618.002244475 (durationBeforeRetry 2m2s). Error: MountVolume.MountDevice failed for volume "pvc-bd3cec31-4032-4433-adf6-f436c7834654" (UniqueName: "kubernetes.io/csi/driver.longhorn.io^pvc-bd3cec31-4032-4433-adf6-f436c7834654") pod "keycloakdb-postgresql-0" (UID: "ee7d21e6-b441-4416-a12a-afc004439ade") : rpc error: code = DeadlineExceeded desc = context deadline exceeded`
* Double checking other nodes, they don't have a `vol_data.json` for `pvc-bd3cec31-4032-4433-adf6-f436c7834654`. It's confined to just one node (`jesseta`)
* Deleted replica from Jesseta node in the Longhorn web UI.
  It added it back.
  ... and is giving the same errors again, aaaaaaaa
* Maybe this is [filesystem corruption](https://longhorn.io/kb/troubleshooting-volume-filesystem-corruption/)?
  * Scale down workload with `kubectl scale`.
    This [should work with Flux](https://github.com/fluxcd/flux/pull/2908).
    This subcommand operates on `deployment, replica set, replication controller, or stateful set`
    per its `--help`.
    Keycloak Helm chart deploys statefulsets.
    `kubectl scale --replicas=0 statefulset/keycloak-keycloakx -n keycloak && kubectl scale --replicas=0 statefulset/keycloakdb-postgresql -n keycloak`,
    then wait for all pods to go away with `kubectl get pods -n keycloak`.
  * Got into an attach/fail/detach loop trying to attach to Jesseta.
    Maybe this is a problem bc I deleted the replica from Jesseta?
    It recreated the replica on Jesseta at the time,
    but now it isn't there.
* Ended up thinking it is just corrupted due to power outage and deleting
  * TODO: Graceful power outage shutdown
  * TODO: backup all longhorn volumes
  * `kubectl scale --replicas=1 statefulset/keycloak-keycloakx -n keycloak && kubectl scale --replicas=1 statefulset/keycloakdb-postgresql -n keycloak`
  * It creats a new volume for me
  * Then I have to go reconfigure Keycloak manually -- wait what, it's already configured?
    I'm very confused. What was in the database??

## Helm fails to update manifests that have been installed by hand

Example error message: `Helm install failed: rendered manifests contain a resource that already exists. Unable to continue with install: ServiceAccount "cert-manager-cainjector" in namespace "cert-manager" exists and cannot be imported into the current release: invalid ownership metadata; label validation error: missing key "app.kubernetes.io/managed-by": must be set to "Helm"; annotation validation error: missing key "meta.helm.sh/release-name": must be set to "cert-manager"; annotation validation error: missing key "meta.helm.sh/release-namespace": must be set to "cert-manager"`

This happens if you deploy something via `kubectl apply -f ...` or similar,
and then tell Helm to manage those same resources.

The easiest thing to do is delete the entire HelmRelease and/or the whole Namespace and redeploy.
However, in some cases this is inconvenient --
you might have persistent data,
such as with cert-manager,
that is hard to regenerate.
(Let's Encrypt might block us if we re-request too many ceretificates.)

Instead you can just add the annotations and labels as the error suggests.
A crappy script I wrote to partially automate this:

```sh
#!/bin/sh
# Usage: ./fixhelm.sh <RESOURCE TYPE> <RESOURCE NAME> [NAMESPACE]
# If the object is not namespaced, don't pass anything for the third option.
# E.g. with namespace: ./fixhelm.sh ServiceAccount cert-manager-cainjector cert-manager
# E.g. without namespace: ./fixhelm.sh MutatingWebhookConfiguration cert-manager-webhook
set -x
type="$1"
resource="$2"
namespace="$3"
kubectl annotate --overwrite "$type/$resource" -n "$namespace" "meta.helm.sh/release-name=cert-manager"
kubectl annotate --overwrite "$type/$resource" -n "$namespace" "meta.helm.sh/release-namespace=cert-manager"
kubectl label "$type" "$resource" -n "$namespace" app.kubernetes.io/managed-by="Helm"
```

After that you should tell Flux to tell Helm to try again,
with `flux suspend ... && flux resume ...` as mentioned previously.

For a nontrivial HelmRelease, you'll have to do this for a dozen different types, or more.

* Pay careful attention:
  the error message might change from
  `Unable to continue with install: ClusterRole "cert-manager-cainjector" in namespace "cert-manager"`
  referencing a **ClusterRole** to referencing a **ClusterRoleBinding** with the same name.
  Re-read the error message if you think it is repeating itself!
* You might want to `kubectl get TYPE | grep cert-manager` or similar,
  so that you can run `fixhelm.sh` on multiple resources of the same type without having to
  `flux suspend ... && flux resume ...` over and over again.
  You can even do this in a loop, like
  `for crb in $(k get ClusterRoleBinding -A | grep cert-manager | sed 's/ .*//g'); do ./fixhelm.sh ClusterRoleBinding "$crb"; done`,
  just be very careful to test this first nondestructively each time.
* Note that `meta.helm.sh/release-name` and `meta.helm.sh/release-namespace` are ANNOTATIONS,
  while `app.kubernetes.io/managed-by` is a LABEL.

## Flux-applied kustomizations

We have {{< repolink "kubernasty/manifests/mantle/flux/flux-system/kustomization.yaml" >}}
which references other kustomizations in
{{< repolink "kubernasty/manifests/mantle/flux/flux-system/" >}}.
We can simulate the way Flux applies them with a command like

```sh
kubectl apply --server-side --field-manager=kustomize-controller -f kubernasty/manifests/mantle/flux/flux-system/WHATEVER.yaml
```

[Via](https://github.com/fluxcd/kustomize-controller/issues/741#issuecomment-1271635186).

## CPU and memory limits

* `kubectl describe node <nodename>` shows resource consumption on the node,
  including CPU and memory,
  and shows which pods are consuming them.
* CPU is specified like `123m`, where the `m` is for `millicpu`
* <https://stackoverflow.com/questions/38869673/pod-in-pending-state-due-to-insufficient-cpu>

## Helm doesn't store its repos in the cluster

Helm doesn't store its repos in the cluster;
it stores them in a config file on whatever machine contains the Helm binary.
_Flux_ stores Helm repos in the cluster as a `HelmRepository` custom resource,
but the Helm binary running on your laptop or a cluster node doesn't know anything about these.

You can use this one liner to pull all the Flux-managed HelmRepository resources
from the cluster and save them to the local Helm configuration.

```sh
kubectl get HelmRepository -A -o \
    jsonpath="{range .items[*]}{.metadata.name}{'\t'}{.spec.url}{'\n'}{end}" |
      while read -r name url; do helm repo add "$name" "$url"; done
helm repo update
```

I include a function that does this in {{< repolink "kubernasty/cluster.sh" >}}.

This doesn't keep anything in sync;
you have to re-run it if you add any new repos to Flux.

## Modifying a Helm chart's values.yaml

A common pattern for Helm charts is to have a `values.yaml`
which allows custom settings or overrides.
In Flux, it's easiest to define these by making a new ConfigMap with a `values.yaml` key,
and including YAML as a _string_ as the value.

```yaml
apiVersion: helm.toolkit.fluxcd.io/v2beta1
kind: HelmRelease
metadata:
  name: example-chart
  namespace: examplens
spec:
  chart:
    spec:
      chart: example-chart
      version: 2.19.0
      sourceRef:
        kind: HelmRepository
        name: example-repository
        namespace: flux-system
  interval: 15m
  timeout: 5m
  releaseName: example-release
  valuesFrom:
  - kind: ConfigMap
    name: example-chart-values
    valuesKey: values.yaml

---
apiVersion: v1
kind: ConfigMap
metadata:
  name: example-chart-values
  namespace: examplens
data:
  values.yaml: |-
    someSetting: someValue
    more:
      stuff_like: "this"
    etc: true
```

**But if you modify the `values.yaml` and push, Flux will not redeploy the HelmRelease**.

Instead, you need to extract the contents of `values.yaml` into a temp file,
and apply it with Helm.

```yaml
someSetting: someValue
more:
  stuff_like: "this"
etc: true
```

```sh
helm upgrade -n examplens example-release example-repository/example-chart -f TEMP.yaml
```

This is one reason it's really useful to
[install the Helm binary]({{< ref "/docs/core/prerequisites" >}}#helm)
even though we are using Flux.

For this to work, your local Helm configuration must include all the repositories that Flux is configured to use.
You can set them with a simple command, see
[Helm doesn't store its repos in the cluster](#helm-doesnt-store-its-repos-in-the-cluster), above.
