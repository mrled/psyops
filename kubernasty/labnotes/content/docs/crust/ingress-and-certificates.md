---
title: Ingress and certificates
weight: 99
---

{{% hint "danger" %}}
⚠️ **TODO: Refactor this to work via Flux** ⚠️

Originally I did this with kubectl early,
and only added Flux later,
but I now deploy all this via Flux,
and I need to update this document to reflect that.
Some of this has already been refactored, like [cert-manager]({{< ref "cert-manager" >}}).

{{% /hint %}}

How to configure ingress with and without HTTPS certificates.

## Prerequisites

* DNS configured, including
    * A dedicated zone in Route53 for cluster records
    * `kubernasty.micahrl.com` pointing to the kube-vip IP address `192.168.1.200`
    * `whoami-http`, `whoami-https-staging`, `whoami-https-prod` subdomains of `kubernasty.micahrl.com` CNAME'd to `kubernasty.micahrl.com`
    * I handle this in CloudFormation under {{< repolink "ansible/cloudformation/MicahrlDotCom.cfn.yml" >}}
* An AWS IAM user with permission to modify the zone, for DNS challenges with Let's Encrypt
    * I create a group in the CloudFormation template, and then an IAM user in the AWS console

## whoami service

A useful service for testing.
Deploy with: `kubectl apply -f manifests/mantle/whoami/deployments/whoami.yml`.

Note that this does _not_ include any ingress definitions,
which means that you can't access this deployment from outside your cluster,
even if DNS is set up properly.

```txt
> curl http://whoami-http.kubernasty.micahrl.com
404 page not found
```

## HTTP ingress for whoami service

HTTP ingresses are pretty easy.
Deploy with `kubectl apply -f manifests/mantle/whoami/ingresses/http.yml`.

Once this is up, you can `curl http://whoami-http.kubernasty.micahrl.com` and see results:

```txt
> curl http://whoami-http.kubernasty.micahrl.com/
Hostname: whoami-5d4d578786-v724l
IP: 127.0.0.1
IP: ::1
IP: 10.42.1.12
IP: fe80::309c:1ff:fe40:1bae
RemoteAddr: 10.42.0.4:37916
GET / HTTP/1.1
Host: whoami-http.kubernasty.micahrl.com
User-Agent: curl/7.84.0
Accept: */*
Accept-Encoding: gzip
X-Forwarded-For: 10.42.0.2
X-Forwarded-Host: whoami-http.kubernasty.micahrl.com
X-Forwarded-Port: 80
X-Forwarded-Proto: http
X-Forwarded-Server: traefik-df4ff85d6-f5wxf
X-Real-Ip: 10.42.0.2
```

TODO: Have `whoami` show the client address, not a cluster address.
Note that the results are showing the _internal cluster IP address_ as `RemoteAddr`,
but we would like to see the client address here.
This is possible but apparently complicated judging by the one billion forums posts on the topic.

See also:

* <https://github.com/sleighzy/k3s-traefik-v2-kubernetes-crd>

## HTTPS ingress and cert-manager

* Traefik can handle Let's Encrypt certs itself...
* ... but the fucking thing charges money for this if using with HA, as we are in k3s.
* Instead, we can use `cert-manager` to create and store the certs, and let Traefik use them.

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
Use our normal [convention]({{< ref "conventions" >}}) to encrypt with `sops`
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

## Appendix: background on certificates

A thoughtful list of considerations about ingress controllers and certificates,
or a thinly disguised whine about the execrable state of basic tooling in the Kubernetes ecosystem.
You decide!

You can skip this section.
I keep it here to provide context on why I chose to do things this way.
Kubernetes has a _lot_ of Perl's TMTOWTDI design philosophy,
and comparing different methods of accomplishing the same result can be very confusing at first.

* k3s uses Traefik as its ingress controller by default
* Traefik can automatically manage Let's Encrypt certificates
    * You can configure it to automatically request them based on the services it is load balancing for
    * I've done this in Docker Swarm for a while now
    * However, this only works with a single instance of Traefik Proxy; you have to pay for Traefik Enterprise for this to work in highly available clusters
    * Kubernasty will be a highly available cluster; any node should be able to go down and the server should keep running, and when running it should still keep using correct certificates
* Cert Manager is recommended to use instead when you need a highly available cluster with Traefik IngressController and HTTPS.
* Kubernetes has a generic resource called `Ingress`.
    * Traefik supports `Ingress`, but has a more natural extension called `IngressRoute`. It's unclear to me what the differences are.
    * (The `IngressRoute` name is also used by other proxies that work with Kubernetes, but its nonstandard, and each project's `IngressRoute` is completely different and incompatible.)
    * <https://stackoverflow.com/questions/60177488/what-is-the-difference-between-a-kubernetes-ingress-and-a-ingressroute>
    * > Ingress is a shared abstraction that can be implemented by many providers (Nginx, ALBs, Traefik, HAProxy, etc). It is specifically an abstraction over a fairly simple HTTP reverse proxy that can do routing based on hostnames and path prefixes. Because it has to be a shared thing, that means it's been awkward to handle configuration of provider-specific settings. Some teams on the provider side have decided the benefits of a shared abstraction are not worth the complexities of implementation and have made their own things, so far Contour and Traefik have both named them IngressRoute but there is no connection other than similar naming.
* Traefik's built in Let's Encrypt support works fine with its `IngressRoute`, but Cert Manager cannot work with `IngressRoute`. To use Cert Manager, you need to use `Ingress` instead.
    * <https://doc.traefik.io/traefik/providers/kubernetes-crd/>
    * > If you want to keep using Traefik Proxy, high availability for Let's Encrypt can be achieved by using a Certificate Controller such as Cert-Manager. When using Cert-Manager to manage certificates, it creates secrets in your namespaces that can be referenced as TLS secrets in your ingress objects. When using the Traefik Kubernetes CRD Provider, unfortunately Cert-Manager cannot yet interface directly with the CRDs. A workaround is to enable the Kubernetes Ingress provider to allow Cert-Manager to create ingress objects to complete the challenges. Please note that this still requires manual intervention to create the certificates through Cert-Manager, but once the certificates are created, Cert-Manager keeps them renewed.
    * Note that this means that you have to define your own certificates when spinning up new services. This isn't that bad; you're already writing a gigantic blob of YAML to write the various namespace/service/secret/ingress manifests, you might as well add one more fucking blob of YAML for the cert too. The whole point of computers is to enable humans to write more YAML, and this is just another way to accomplish this goal.
* It's worth mentioning there is a _new_ thing called the Kubernetes `Gateway`
    * It is a first party resource like `Ingress`
    * It's more generic than `Ingress`, hopefully solving the problems that Traefik tries to solve with its proprietary `IngressRoute`
    * Support is in progress for Traefik, Cert Manager, ExternalDNS... most things are expected to support it since it will become standard
    * It seems too early right now, things are still rough, e.g. Traefik's support is still "experimental"
* Why work with Traefik at all?
    * k3s uses traefik by default (although you can disable it at install time and install something else instead once the cluster is up).
    * Maybe we should use nginx instead? No idea if nginx has its own problems. Probably!
    * nginx _does_ offer much less fucked up logs.
    * WARNING: `kubernetes/ingress-nginx` is an ingress controller maintained by the Kubernetes community; `nginxinc/kubernetes-nginx` is an ingress controller maintained by F5 NGINX. <https://www.nginx.com/blog/guide-to-choosing-ingress-controller-part-4-nginx-ingress-controller-options/>. Naturally, there are two versions of the one maintained by F5, and F5 is also contracted to maintain the community one, so who knows.
    * maybe try this? <https://gist.github.com/pkeech/24ed00b699509732c4cd33ee89767f49>
* So for Cert Manager, we need to use the first party `Ingress` resources.
