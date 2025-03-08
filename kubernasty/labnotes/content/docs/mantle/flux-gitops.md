---
title: Flux GitOps
weight: 60
---

We'll use Flux for GitOps.

## Better secrets with sops in flux

Via <https://fluxcd.io/flux/guides/mozilla-sops/#encrypting-secrets-using-age>.

Flux can handle `sops` secrets for you automatically.

First, you need an age key file for the cluster.
We've already done this (see [Conventions]({{< ref "conventions" >}})),
but to recap, run `age-keygen -o cluster.age`,
and save the public key value to `cluster.sh` like
`export SOPS_AGE_RECIPIENTS=age1869u6cnxhf7a6u6wqju46f2yas85273cev2u6hyhedsjdv8v39jssutjw9`.
Now we need to add it to the cluster as a secret:

```sh
kubectl create namespace flux-system
gopass -n kubernasty/flux.agekey |
    kubectl create secret generic sops-age --namespace flux-system --from-file=age.agekey=/dev/stdin
```

Now you can use your newly created key for cluster secrets.
You could run `sops` like this:

```sh
sops \
    --age="$SOPS_AGE_RECIPIENTS" \
    --encrypted-regex '^(data|stringData)$' \
    ...
```

... however, it's nicer to create a sops config file under {{< repolink "kubernasty/.sops.yaml" >}}:

```yaml
creation_rules:
  - path_regex: .*.yaml
    encrypted_regex: ^(data|stringData)$
    age: age1869u6cnxhf7a6u6wqju46f2yas85273cev2u6hyhedsjdv8v39jssutjw9
```

`sops` looks for this file in every parent directory of a file you try to de/en-crypt,
so it will find it automatically for files under `kubernasty/`.
It will only try to encrypt the `data`/`stringData` keys,
which is required because if we encrypt other keys in a secret manifest,
Kubernetes will not be able to use it.

We can create manifest files containing secrets,
then commit the encrypted version to Git.
Flux will pull them down from the Git server and be able to apply them like any other manifest,
decrypting them transparently first.

TODO: Test sops secrets in Flux.
This isn't tested at all yet.

## Bootstrapping Flux

See also the [official Flux documentation](https://fluxcd.io/flux/installation).

* Obtain the `flux` binary from the [releases page](https://github.com/fluxcd/flux2/releases).
* Create a GitHub Personal Access Token.
  (See the official docs for details.)
  I made mine a new-style fine-grained token, rather than a "classic" token with whole-account access.
  * Give access to just this `mrled/psyops` repo
    * Read and Write: `Administration`
    * Read and Write: `Contents`
    * Read and Write: `Commit Statuses`
    * Everything else is set to the default value
  * If you modify the repository permissions after generating the token,
    make sure to _regenerate the token_.

Now bootstrap.
Bootstrapping is idempotent, so running the bootstrap command multiple times won't hurt anything.

```sh
export GITHUB_TOKEN="<the personal access token created previously>"

flux bootstrap github \
    --owner=mrled \
    --repository=psyops \
    --path=kubernasty/mantle/flux \
    --branch=master \
    --personal
```

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
