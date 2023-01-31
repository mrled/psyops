---
title: Kubernetes dashboard
weight: 50
---

Using what we've learned so far,
we'll install the official Kubernetes dashboard,
adapted from [these instructions](https://docs.k3s.io/installation/kube-dashboard).

We're also going to add one more tool: Kustomize.
Even though it's apparently named by Kandy in Killeen who runs a shop called the Kountry Korner,
it's a useful way to:

* Deploy all of a service's manifests in a single command
* Apply (sigh) "kustomizations" to a given deployment so that the manifests are reusable in multiple environments

## Deploying the Kubernetes dashboard

First, make sure you have a domain name set;
I use `dashboard.kubernasty.micahrl.com`.

Get the manifest:

```sh
GITHUB_URL=https://github.com/kubernetes/dashboard/releases
VERSION_KUBE_DASHBOARD=$(curl -w '%{url_effective}' -I -L -s -S ${GITHUB_URL}/latest -o /dev/null | sed -e 's|.*/||')
DEPLOY_AIO_URL="https://raw.githubusercontent.com/kubernetes/dashboard/${VERSION_KUBE_DASHBOARD}/aio/deploy/alternative.yaml"
curl -o kubernetes-dashboard/deploy-aio.yml "$DEPLOY_AIO_URL"
```

Then examine the `kustomization.yml` file.
It's already present in this repo, and it looks like this:

```yaml
namespace: kubernetes-dashboard
commonLabels:
  app: kubernetes-dashboard
resources:
- deploy-aio.yml
- admin-user.yml
- certificate.yml
- ingress.yml
```

This applies the same namespace and `app:` label to all resources,
and then lists the manifest files that contain resources.
(Note that the same namespace is specified in the `deploy-aio.yml` manifest from the official project;
we just duplicate it here so that it applies to all of the resources we've added ourselves.)

```sh
# Show the result of the Kustomize transformations - what will actually be deployed
kubectl kustomize ./kubernetes-dashboard/

# Deploy the dashboard
kubectl apply -k ./kubernetes-dashboard/

# Retrieve the bearer token
kubectl -n kubernetes-dashboard describe secret admin-user-token | grep '^token'
```

Wait until the cert is issued, and then navigate to
`https://dashboard.kubernasty.micahrl.com`.
Enter the token from the previous command to log in.

## Updating the dashboard

You must apply updates manually by removing the dashboard resources and re-applying them.
You probably _don't_ want to delete the whole `kubernetes-dashboard` namespace,
as we are storing our Let's Encrypt certificate there.
