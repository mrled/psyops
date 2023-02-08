---
title: cert-manager
weight: 10
---

cert-manager issues certificates for us automatically.

It should be created when Flux bootstraps.
This contains notes for things I had to do manually the first time,
like create the secret object containing AWS credentials.

## Prerequisites

* DNS configured, including
    * A dedicated zone in Route53 for cluster records
    * `kubernasty.micahrl.com` pointing to the kube-vip IP address `192.168.1.200`
    * `whoami-http`, `whoami-https-staging`, `whoami-https-prod` subdomains of `kubernasty.micahrl.com` CNAME'd to `kubernasty.micahrl.com`
    * I handle this in CloudFormation under {{< repolink "ansible/cloudformation/MicahrlDotCom.cfn.yml" >}}
* An AWS IAM user with permission to modify the zone, for DNS challenges with Let's Encrypt
    * I create a group in the CloudFormation template, and then an IAM user in the AWS console

I created a Kubernasty zone for this (see {{< repolink "ansible/cloudformation/MicahrlDotCom.cfn.yml" >}}).
It contains an A record `kubernasty.micahrl.com` pointing to the cluster IP address of `192.168.1.200`,
and CNAME records for each service as subdomains, like `whoami-https-staging.kubernasty.micahrl.com`.
(TODO: also show more advanced configurations that support multiple zones.)
I also created an IAM access key in the AWS console.

## Setting secrets

Now create a secret containing the IAM access key id and secret
so that cert-manager can use it to make Route53 changes for DNS challenges.
See the unencrypted example at
{{< repolink "kubernasty/manifests/crust/cert-manager/secrets/aws-route53-credential.example.yaml" >}}
Use our normal [convention]({{< ref "conventions" >}}) to encrypt with `sops`
and save the encrypted version of the real manifest as
{{< repolink "kubernasty/manifests/crust/cert-manager/secrets/aws-route53-credential.yaml" >}}
before applying it.

```sh
# Write the manifest
vim tmpsecret.yml
# Encrypt the manifest
sops --encrypt tmpsecret.yml > manifests/crust/cert-manager/secrets/aws-route53-credential.yaml
# Remove the unencrypted manifest
rm tmpsecret.yml

# Apply the encrypted manifest
sops --decrypt manifests/crust/cert-manager/secrets/aws-route53-credential.yaml | kubectl apply -f -
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
The ACME protocol also supports other kinds of challenges, like HTTP,
however, HTTP challenges require your Kubernetes server to be accessible on the open Internet.
DNS challenges can be used for clusters that are never exposed to the Internet,
making them more appropriate for home labs.

We also need a programmatic DNS service anyway for
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
