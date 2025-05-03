---
title: Cert Manager (old)
weight: 41
---

First, install cert-manager using kubectl with cert-manager’s release file:

```sh
mkdir -p manifests/mantle/cert-manager/{deployments,secrets,clusterissuers}
curl -L -o manifests/mantle/cert-manager/deployments/cert-manager.yml https://github.com/cert-manager/cert-manager/releases/download/v1.9.1/cert-manager.yaml
kubectl apply -f manifests/mantle/cert-manager/deployments/cert-manager.yml
```

This will create the `cert-manager` namespace and deploy the resources.

This step requires an AWS Route53 zone,
and an IAM user that has permission to update records in the zone.
I created a Kubernasty zone for this (see {{< repolink "ansible/cloudformation/MicahrlDotCom.cfn.yml" >}}).
It contains an A record `kubernasty.micahrl.com` pointing to the cluster IP address of `192.168.1.200`,
and CNAME records for each service as subdomains, like `whoami-https-staging.kubernasty.micahrl.com`.
(TODO: also show more advanced configurations that support multiple zones.)
I also created an IAM access key in the AWS console.

Now create a secret containing the IAM access key id and secret
so that cert-manager can use it to make Route53 changes for DNS challenges.
See the unencrypted example at
{{< repolink "kubernasty/manifests/mantle/cert-manager/secrets/aws-route53-credential.example.yml" >}}
Encrypt with [SOPS]({{< ref sops >}})
and save the encrypted version of the real manifest as
{{< repolink "kubernasty/manifests/mantle/cert-manager/secrets/aws-route53-credential.yaml" >}}
before applying it.

```sh
# Write the manifest
vim tmpsecret.yml
# Encrypt the manifest
sops --encrypt tmpsecret.yml > manifests/mantle/cert-manager/secrets/aws-route53-credential.yaml
# Remove the unencrypted manifest
rm tmpsecret.yml

# Apply the encrypted manifest
sops --decrypt manifests/mantle/cert-manager/secrets/aws-route53-credential.yaml | kubectl apply -f -
```

Then apply the issuer.
We have both a staging and a production issuer available,
and we can apply them both now.
We'll use the staging issuer first so that Let's Encrypt doesn't give us a temp ban for too many requests
while we are trying to make this work,
but we can go ahead and apply the prod one as well.

```sh
kubectl apply -f manifests/mantle/cert-manager/clusterissuers/letsencrypt-issuer-staging.yml
kubectl apply -f manifests/mantle/cert-manager/clusterissuers/letsencrypt-issuer-prod.yml
```

Now we're ready to start requesting certificates.

TODO: explain why using DNS challenges is important with Let's Encrypt.
Short version: they work well for clusters that aren't on the public Internet.

## HTTPS ingress for whoami service using Let's Encrypt staging certificates

Now we can enable HTTPS for the whoami service.
We'll use the Let's Encrypt staging infrastructure first so that they don't ban us if something is wrong.

Note that we have to define a `Certificate` resource in this file.
Traefik can do this if you pay for Enterprise or are not using HA,
but when using Traefik Proxy + Cert Manager, we have to create it ourselves.

```sh
kubectl apply -f manifests/mantle/whoami/ingresses/https-staging.yml
```

Verify things are working with commands like:

```sh
kubectl get certificates -A
kubectl get certificaterequests -A
kubectl get ingress -A
kubectl describe certificate ...
kubectl describe certificaterequest ...
```

{{< hint info >}}
**It can take a while for certificates to become READY.**

In my experience on AWS Route53, it seems to usually take 2-5 minutes.

I have heard that other providers may take 30 minutes or longer.

Wait to proceed until your certificates enter the READY state.
{{< /hint >}}

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

It will take a few minutes for the certificate to be issued.
Once it is issued, check that it's working with `curl` (ignoring SSL errors, as this is the staging server)
and `certissuer`, which is a function defined in {{< repolink "kubernasty/cluster.sh" >}}.

```sh
curl -k https://whoami-https-staging.kubernasty.micahrl.com
# Should return results similar to those returned by the http request earlier

certissuer whoami-https-staging.kubernasty.micahrl.com
# Should show the staging Let's Encrypt CA, something like:
# Issuer: C=US, O=(STAGING) Let's Encrypt, CN=(STAGING) Artificial Apricot R3
```

Make sure that it's showing the staging LE CA!
If it is instead showing something like `Issuer: CN=TRAEFIK DEFAULT CERT`,
that means that you don't have certificates configured properly,
and getting a production LE cert in the next step will not work.

See also:

* <https://blog.crafteo.io/2021/11/26/traefik-high-availability-on-kubernetes-with-lets-encrypt-cert-manager-and-aws-route53/>

## HTTPS ingress for whoami service using Let's Encrypt production certificates

This is very similar to the staging setup, just using a different ClusterIssuer to get real certs.

```sh
kubectl apply -f manifests/mantle/whoami/ingresses/https-prod.yml

# ... wait ...

# Don't use -k - we want this to fail if the cert isn't trusted
curl https://whoami-https-prod.kubernasty.micahrl.com
# Should return results similar to last time

certissuer whoami-https-prod.kubernasty.micahrl.com
# Should show the production Let's Encrypt CA, something like:
# Issuer: C=US, O=Let's Encrypt, CN=R3
```

## Troubleshooting

* Try commands like `kubectl describe certificate whoami-cert-prod -n whoami`
* Note the message `Issuing certificate as Secret does not exist` is a generic error --
  it just means the cert doesn't exist locally.
  If it stays in this state for a long time,
  you'll have to do some cert-manager troubleshooting.
* See the [cert-manager troubleshooting guide](https://cert-manager.io/docs/troubleshooting/)

