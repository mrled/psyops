---
title: Flux GitOps
weight: 60
---

We'll use Flux for GitOps.

## Bootstrapping Flux

See also the [official Flux documentation](https://fluxcd.io/flux/installation).

* Obtain the `flux` binary from the [releases page](https://github.com/fluxcd/flux2/releases).
* Create a GitHub Personal Access Token.
  (See the official docs for details.)
  I made mine a new-style fine-grained token, rather than a "classic" token with whole-account access.
  I gave it access just to this `mrled/psyops` repo,
  and gave it just `Administration` and `Content` repository permissions.

Now bootstrap.
Bootstrapping is idempotent, so running the bootstrap command multiple times won't hurt anything.

```sh
export GITHUB_TOKEN="<the personal access token created previously>"

flux bootstrap github \
    --owner=mrled \
    --repository=psyops \
    --path=kubernasty/flux \
    --branch=master \
    --personal
```

When I ran this, there was no `kubernasty/flux` subdirectory of this repository;
this was ok, flux created it.

From this point forward, you shouldn't need to apply manifests with `kubectl apply ...` any more.
Instead you can commit manifests to this repository under `kubernasty/flux/<app name>/kustomization.yml`
(with the kustomization optionally referencing other manifests in the same subdirectory)
and Flux will automatically apply them to the cluster.

## Better secrets with sops in flux

Via <https://fluxcd.io/flux/guides/mozilla-sops/#encrypting-secrets-using-age>.

Flux can handle `sops` secrets for you automatically,
which is less kludgy than our way with `sopsandstrip` defined in `cluster.sh`.
From this point forward, we'll use secrets like that, without `sopsandstrip`.

First, you need an age key file for the cluster.
We've already done this (see [Conventions](conventions.md)),
but to recap, run `age-keygen -o cluster.age`,
and save the public key value to `cluster.sh` like
`export SOPS_AGE_RECIPIENTS=age1869u6cnxhf7a6u6wqju46f2yas85273cev2u6hyhedsjdv8v39jssutjw9`.
We also added it to gopass.

Now we need to add it to the cluster as a secret:

```sh
gopass -n kubernasty/sops.age |
    kubectl create secret generic sops-age --namespace flux-system --from-file=age.agekey=/dev/stdin
```

We need a place to store secrets.
For this cluster, I want to use the `kubernasty/secrets` path in the psyops repo --
the repo containing this file,
which is also the main Flux repo we specified to `flux bootstrap ...`.
Flux sees git repositories as "sources";
you can see the source that Flux created during `flux bootstrap ...` with
`flux get sources all`.
Note that, _unlike_ when we ran `flux bootstrap ...`,
this directory must already exist before we tell Flux about it.
I created a file `kubernasty/secrets/.keep` and committed/pushed it before creating the kustomization.

Now we can configure Flux to use sops.
(Note that `gitrepository/flux-system` is a name that `flux get sources all` shows us.)

```sh
flux create kustomization kubernasty-secrets \
    --source=gitrepository/flux-system \
    --path=./kubernasty/secrets \
    --prune=true \
    --interval=10m \
    --decryption-provider=sops \
    --decryption-secret=sops-age
```

Now you can use your newly created key for cluster secrets.
You could run `sops` like this:

```sh
sops \
    --age="$SOPS_AGE_RECIPIENTS" \
    --encrypted-regex '^(data|stringData)$' \
    ...
```

... however, it's nicer to create a sops config file.
Save this to `secrets/.sops.yaml`:

```yaml
creation_rules:
  - path_regex: .*.yaml
    encrypted_regex: ^(data|stringData)$
    age: age1869u6cnxhf7a6u6wqju46f2yas85273cev2u6hyhedsjdv8v39jssutjw9
```

`sops` looks for this file in every parent directory of a file you try to de/en-crypt,
so it will find it automatically for files under `secrets`.

We can create manifest files containing secrets,
then commit the encrypted version to Git.
Flux will pull them down from the Git server and be able to apply them like any other manifest,
decrypting them transparently first.

TODO: Test sops secrets in Flux.
This isn't tested at all yet.

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
