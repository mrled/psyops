---
title: Flux GitOps
weight: 60
---

We'll use Flux for GitOps.

## Encrypted secrets with sops in flux

Via <https://fluxcd.io/flux/guides/mozilla-sops/#encrypting-secrets-using-age>.

Flux can handle `sops` secrets for you automatically.

First, make sure you have already [set up SOPS locally]({{< ref sops >}})
Now we need to add it to the cluster as a secret:

```sh
kubectl create namespace flux-system
kubectl create secret generic sops-age --namespace flux-system --from-file=age.agekey
```

Now you can use your newly created key for cluster secrets.

We can create manifest files containing secrets,
then commit the encrypted version to Git.
Flux will pull them down from the Git server and be able to apply them like any other manifest,
decrypting them transparently first.
See examples in [SOPS]({{< ref sops >}}).

## Bootstrapping Flux

See also the [official Flux documentation](https://fluxcd.io/flux/installation).

{{% hint info %}}
Note that you can use `flux bootstrap github ...`
with a GitHub Personal Access Token instead,
which will create a deploy key for you ---
see the Flux documentation for more.
I don't do that here because I want to be able to swap my Flux repo to one hosted in the cluster later.
{{% /hint %}}

* Create a new SSH key with `ssh-keygen`, and save it to `./flux_deploy_id`
* Add it to your gitops repository as a deploy key; it requires read/write
* `flux bootstrap git --url=ssh://git@github.com/mrled/psyops --path=kubernasty/mantle --branch=master --private-key-file=./flux_deploy_id`
* (Add `--silent` to make it go without manual confirmation)
* Delete the `./flux_deploy_id` file; it's saved to the cluster now
* Create an `age` key with `age-keygen` called `./flux.agekey` --
  note that this filename is important, as the next command uses the filename
  as the name for the secret value,
  and the secret value name must end with `.agekey`
* Add it as a SOPS key for Flux with
  `kubectl create secret generic sops-age --namespace=flux-system --from-file=./flux.agekey`
* Delete the `flux.agekey` file

Bootstrapping is idempotent, so running the bootstrap command multiple times won't hurt anything,
and changing the command will update the Flux configuration as you expect.

From this point forward, you shouldn't need to apply manifests with `kubectl apply ...` any more.
Instead you can commit manifests to this repository under `kubernasty/manifests/mantle/flux/<app name>/kustomization.yml`
(with the kustomization optionally referencing other manifests in the same subdirectory)
and Flux will automatically apply them to the cluster.

## What happens after Flux installs itself?

Now what happens depends on whether the Git repo you're using has Flux kustomizations in it or not.

### If you're installing Flux for the first time in this repo

When I first ran this, there was no `kubernasty/manifests/mantle/flux` subdirectory of this repository;
this was ok, flux created it.

Skip to the next section.

### If the repo already has Kustomizations in it

If there are already kustomizations at the `--path` listed above,
Flux will install itself and then immediately start trying to install those kustomizations.
That means that the rest of this page,
along with all other pages in this guide that were finished happen automatically;
you just need to monitor them to make sure they complete successfully.

### If you have uninstalled Flux and are reinstalling it to the same cluster

This is supported and should work without surprises.
Per the [uninstallation documentation](https://fluxcd.io/flux/installation/#uninstall):

> Note that the uninstall command will not remove any Kubernetes objects or Helm releases that were reconciled on the cluster by Flux. It is safe to uninstall Flux and rerun the bootstrap, any existing workloads will not be affected.

## Flux logs

* You can check flux logs with `flux logs`;
  I typically use `flux logs --since 20m --follow`.
  When it detects a new change from Git, it will show the commit message in the logs.
* You might also want to see flux kustomization status with
  `kubectl get kustomization -n flux-system`.
  and `kubectl describe kustomization <kustomization-name> -n flux-system`.
* `kubectl describe pod helm-controller -n flux-system` sometimes helps too.
* `flux get all` can show errors if something is failing to deploy
* Something really noisy like `kubectl get events -A` might help if you're stuck.
  `kubectl get events --sort-by=.metadata.creationTimestamp` to sort by time.
* Typical kubernetes stuff like `kubectl get pods -n <namespace>` and then `kubectl logs <pod-from-previous-command> -n <namespace>`.
* ... <https://kubernetes.io/docs/reference/kubectl/cheatsheet/>.

## TODO: consider enabling Flux earlier

Currently, we've deployed several things by hand, and only added Flux and GitOps at the end.

Perhaps this is a mistake.
Flux doesn't have a web UI and doesn't need ingresses, certificates, load balancers, or even kube-vip to work.
We could deploy Flux as soon as the cluster is up,
and leave configuration of all of those items to Flux itself.

On the other hand, progressing from a new cluster to `kubectl apply` to Flux and GitOps seems natural.

## Forcing flux to reconcile

When you push changes to the Git repo,
you can just wait for Flux to find them,
but you can also force it to look immediately with this command:

```sh
kubectl annotate --field-manager=flux-client-side-apply --overwrite gitrepository/flux-system -n flux-system reconcile.fluxcd.io/requestedAt="$(date +%s)"
```

See also <https://fluxcd.io/flux/components/source/gitrepositories/#triggering-a-reconcile>

## Flux vs Helm

* **Flux** will happily adopt resources you've deployed by by `kubectl create ...`,
  `kubectl apply -f ...`, etc.
* **Helm** does not like to adopt resources that it did not deploy the first time.

This can be confusing, as we use Flux to install Helm things.
You can try to force this, but it might not fully work.
See also "Helm fails to update manifests that have been installed by hand"
on the [Troubleshooting]({{< ref "troubleshooting" >}}) page.

## Flux and kustomizations

Flux leans heavily into [Kustomize](https://kubernetes.io/docs/tasks/manage-kubernetes-objects/kustomization/).
Even though it's apparently named by Kandy in Killeen who runs a shop called the Kountry Korner,
it's a useful way to:

* Deploy all of a service's manifests in a single command
* Apply (sigh) "kustomizations" to a given deployment so that the manifests are reusable in multiple environments

See also the [Flux Kustomize questions](https://fluxcd.io/flux/faq/#kustomize-questions).

## Suspending Flux reconciliation

Sometimes you need to make changes to the cluster without Flux reverting them.

```sh
kubectl annotate kustomization -n flux-system flux-system reconciler.fluxcd.io/pause=true
```

To undo this, set the value to false.

```sh
kubectl annotate kustomization -n flux-system flux-system reconciler.fluxcd.io/pause=false
```
