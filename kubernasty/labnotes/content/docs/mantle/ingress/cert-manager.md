---
title: Cert Manager
weight: 40
---

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

## ACME certificate providers

### Let's Encrypt

The original.

Works without any accounts.
You can just get a cert, for free, with DNS credentials.

The staging servers do not issue trusted TLS certs,
but they resolve any problems with your DNS challenge setup.
Production servers have very long (7d) backoff periods during which you absolutely cannot issue any certs,
so you wan to make staging work first.

### ZeroSSL

[ZeroSSL](https://zerossl.com/) also offers free ACME certificates,
without the very long backoff period headaches that you can have with the Let's Encrypt production issuer.

However, to use it you must first create an account with them.

## Setting secrets

Now create a secret containing the IAM access key id and secret
so that cert-manager can use it to make Route53 changes for DNS challenges.

Mine is in
{{< repolink "kubernasty/applications/cert-manager/clusterissuer-kubernasty-ca/Secret.aws-route53-credential.yaml" >}}.
I created it like this:

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

## Certificate readiness

**It can take a while for certificates to become READY.**

In my experience on AWS Route53, it seems to usually take 2-5 minutes.
I have heard that other providers may take 30 minutes or longer.
Wait to proceed until your certificates enter the READY state.

## Troubleshooting

Verify things are working with commands like:

```sh
kubectl get certificates -A
kubectl get certificaterequests -A
kubectl get ingress -A
kubectl describe certificate ...
kubectl describe certificaterequest ...
```

Deeper troubleshooting:

```sh
# If certs are not going to 'Ready' state, look at the logs in the cert-manager container
kubectl get pods -n cert-manager
# Returns a list like:
# NAME                                       READY   STATUS    RESTARTS   AGE
# cert-manager-6544c44c6b-v25jr              1/1     Running   0          14h
# cert-manager-cainjector-5687864d5f-88kgf   1/1     Running   0          14h
# cert-manager-webhook-785bb86798-f9dn6      1/1     Running   0          14h
kubectl logs -f cert-manager-6544c44c6b-v25jr -n cert-manager

# If the certs look like they're being created, but the wrong cert is being served (see below),
# you may also want to see traefik logs
kubectl get pods -n kube-system
# Returns a list that includes:
# ... snip ...
# kube-system    svclb-traefik-75ce313c-74ggl               2/2     Running     2 (28h ago)   28h
# kube-system    svclb-traefik-75ce313c-9745x               2/2     Running     6 (28h ago)   29h
# kube-system    svclb-traefik-75ce313c-f76c6               2/2     Running     4 (28h ago)   28h
# kube-system    traefik-df4ff85d6-f5wxf                    1/1     Running     3 (28h ago)   29h
# ... snip ...
# You'll want the traefik container, not the svclb-traefik containers
kubectl logs -f traefik-df4ff85d6-f5wxf -n kube-system
```

## SSL certificate inspection

In my [cluster.sh]({{< ref "clustersh" >}}),
I added `certinfo` and `certissuer` commands
that make it easier to inspect certificates.

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
  {{< repolink "kubernasty/manifests/crust/cert-manager-config/certificates/micahrl-dot-me-wildcard.cert.yaml" >}}.

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

## See also

* <https://blog.crafteo.io/2021/11/26/traefik-high-availability-on-kubernetes-with-lets-encrypt-cert-manager-and-aws-route53/>
* [cert-manager troubleshooting guide](https://cert-manager.io/docs/troubleshooting/)
