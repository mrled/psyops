---
title: cert-manager
weight: 10
---

{{< hint warning >}}
This is undergoing updates.

I am moving from using individual certificates for domains under `.kubernasty.micahrl.com`
to a single wildcard certificate for domains under `.micahrl.me`.
Currently the repo supports both, until I can migrate everything to the new way.
{{< /hint >}}

cert-manager issues certificates for us automatically.

It should be created when Flux bootstraps.
This contains notes for things I had to do manually the first time,
like create the secret object containing AWS credentials.

## Prerequisites

I am using `.micahrl.me` for my cluster.
This is otherwise used for my [mirror universe](https://com.micahrl.me).

* DNS configured, including
    * A dedicated zone in Route53 for cluster records
    * I handle this in CloudFormation under {{< repolink "ansible/cloudformation/MicahrlDotMe.cfn.yml" >}}
* An AWS IAM user with permission to modify the zone, for DNS challenges with Let's Encrypt
    * I create a group in the CloudFormation template, and then an IAM user in the AWS console

{{< hint warning >}}
When using the production issuer we define here,
cert-manager requests Let's Encrypt certs for this domain.

If the cluster is misconfigured (requesting too many times, losing certs in a botched backup restore, etc),
it could cause Let's Encrypt to temporarily block certificate requests for the entire domain.
If the cluster is using a TLD that is also used elsewhere,
this could mean that Let's Encrypt prevents those certs from being renewed for a while.

* Consider using the staging issuer when appropriate (development, testing, etc)
* Consider using a domain name that isn't used for other services
{{< /hint >}}

## Setting secrets

Now create a secret containing the IAM access key id and secret
so that cert-manager can use it to make Route53 changes for DNS challenges.

```sh
keyid=xxxx
keysecret=yyyy

cat >manifests/crust/cert-manager/secrets/aws-route53-credential.yaml <<EOF
kind: Secret
apiVersion: v1
type: Opaque
metadata:
    name: aws-route53-credential
    # Must be in same namespace as Cert Manager deployment
    namespace: cert-manager
stringData:
    access-key-id: $keyid
    secret-access-key: $keysecret
EOF

sops --encrypt --in-place manifests/crust/cert-manager/secrets/aws-route53-credential.yaml
```

Then apply the issuer.
We have both a staging and a production issuer available,
and we can apply them both now.
We'll use the staging issuer first so that Let's Encrypt doesn't give us a temp ban for too many requests
while we are trying to make this work,
but we can go ahead and apply the prod one as well.

Now we're ready to start requesting certificates.

## Why do we use DNS challenges?

We require Route53 credentials so we can do ACME DNS challenges.

* DNS challenges are required for wildcard certs
* DNS challenges work even if you're not exposing HTTP ports from your cluster to the Internet
  (unlike HTTP challenges, which require an Internet-accessible webserver)
* We also need a programmatic DNS service anyway for
  [external-dns]({{< ref "external-dns" >}}),
  and we can use the same credentials here.

## Fixing DNS propagation errors

I was seeing errors like this in the cert-manager pod,
not resolving and repeating every few seconds:

```text
E0208 01:35:57.904547       1 sync.go:190] cert-manager/challenges "msg"="propagation check failed" "error"="Could not determine authoritative nameservers for \"_acme-challenge.longhorn.kubernasty.micahrl.com.\"" "dnsName"="longhorn.kubernasty.micahrl.com" "resource_kind"="Challenge" "resource_name"="longhorn-cert-backing-secret-lhmbc-2271850782-994157330" "resource_namespace"="longhorn-system" "resource_version"="v1" "type"="DNS-01"
```

To fix, we have to pass additional arguments `--dns01-recursive-nameservers-only` and `--dns01-recursive-nameservers=1.1.1.1:53`.
To do that, we use the `extraArgs` key in
{{< repolink "kubernasty/manifests/crust/cert-manager/configmaps/cert-manager.overrides.yaml" >}}.

... or actually maybe that's wrong?
[Per this bug](https://github.com/cert-manager/cert-manager/issues/2741),
this is what finally got me un-stuck:

```sh
kubectl rollout restart deployment -n cert-manager cert-manager
```

ffs

## Replicating the wildcard

* An ingress can only use a secret defined in its namespace
* When using individual certificates for each hostname, you can just put the secret in the right namespace
* However the wildcard cert exists in the cert-manager namespace
* We use [reflector](https://github.com/emberstack/kubernetes-reflector) to copy it where it is needed.
* See {{< repolink "manifests/crust/reflector" >}},
  and note that we provide reflector annotations in
  {{< repolink "manifests/crust/cert-manager/certificates/micahrl.me.cert.yaml" >}}.

## A note on dependencies

Flux can represent dependency relationship for kustomizations in
{{< repolink "kubernasty/manifests/mantle/flux/flux-system" >}}.
This is necessary for cert-manager,
so we end up with
{{< repolink "kubernasty/manifests/mantle/flux/flux-system/crust/cert-manager-issuers.yaml" >}} which depends on
{{< repolink "kubernasty/manifests/mantle/flux/flux-system/crust/cert-manager.yaml" >}}.
If we don't do this, we get weird errors like
`error: the server could not find the requested resource (patch clusterissuers.cert-manager.io letsencrypt-staging`.
[See also](https://github.com/fluxcd/flux2/discussions/1944).

We take this opportunity to add a `dependsOn` relationship to other kustomizations as well,
like all of the deployments that deploy a certificate should have a `dependsOn`
for the `cert-manager-issuers` kustomization,
all the deployments that need persistent storage should depend on Longhorn, etc.

## Reinstalling cert-manager

I needed to do this when I moved from running `kubectl apply -f ...` to install cert-manager
to having it managed by Flux.

{{< hint danger >}}
If you set the `--enable-certificate-owner-ref` flag to `true` at any point in the past,
certificates could be deleted and require being re-issued when cert-manager is reinstalled.
See also [the docs](https://cert-manager.io/docs/installation/upgrading/#reinstalling-cert-manager).

Especially if you are using the TLD for other purposes aside from this Kubernetes cluster,
this could impact you.
Let's Encrypt has a relatively low limit of the number of certificate requests per week,
and this limit applies to the TLD -- not just the specific hostname or subdomain.

This repository never sets `--enable-certificate-owner-ref`.
{{< /hint >}}

As long as there are no issues with `--enable-certificate-owner-ref`:

```sh
kubectl delete helmrelease -n cert-manager cert-manager
flux delete kustomization -n flux-system cert-manager
```

Here you can verify that the secret containing the certificate is still in the cluster,
at least if you follow my convention of naming these secrets `CERTNAME-cert-backing-secret`, with:

```sh
kubectl get secret -A | grep cert-backing-secret
```

Then make a no-op commit to the cert-manager kustomization in flux-system.
You might need to hit it with `flux reconcile`.
