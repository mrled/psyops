# Basic services

How to configure basic services once the cluster is up.

## whoami service

A useful service for testing.
Deploy with: `kubectl apply -f whoami/whoami.yml`.
This includes an HTTP-only `IngressRoute` resource;
we will enable HTTPS after configuring `cert-manager`.

This requires DNS configured properly, with `whoami.kubernasty.micahrl.com` pointing to the kube-vip IP address.

Once this is up, you can `curl http://whoami.kubernasty.micahrl.com` and see results:

```txt
21:20:34 E0 haluth J1 ~ > curl http://whoami.kubernasty.micahrl.com/
Hostname: whoami-5d4d578786-v724l
IP: 127.0.0.1
IP: ::1
IP: 10.42.1.12
IP: fe80::309c:1ff:fe40:1bae
RemoteAddr: 10.42.0.4:37916
GET / HTTP/1.1
Host: whoami.kubernasty.micahrl.com
User-Agent: curl/7.84.0
Accept: */*
Accept-Encoding: gzip
X-Forwarded-For: 10.42.0.2
X-Forwarded-Host: whoami.kubernasty.micahrl.com
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

## Using `cert-manager` for HTTPS certificates

* Traefik can handle Let's Encrypt certs itself...
* ... but the fucking thing charges money for this if using with HA, as we are in k3s.
* Instead, we can use `cert-manager` to create and store the certs, and let Traefik use them.

First, install cert-manager using kubectl with cert-manager’s release file:

```sh
mkdir -p cert-manager/{deployments,secrets,clusterissuers}
curl -L -o cert-manager/deployments/cert-manager.yml https://github.com/cert-manager/cert-manager/releases/download/v1.9.1/cert-manager.yaml
kubectl apply -f cert-manager/deployments/cert-manager.yml
```

This will create the `cert-manager` namespace and deploy the resources.

This step requires an AWS Route53 zone,
and an IAM user that has permission to update records in the zone.
I created a Kubernasty zone for this (see `ansible/cloudformation/MicahrlDotCom.cfn.yml` in this repository).
It contains an A record `kubernasty.micahrl.com` pointing to the cluster IP address of `192.168.1.200`,
and CNAME records for each service as subdomains, like `whoami.kubernasty.micahrl.com`.
(TODO: also show more advanced configurations that support multiple zones.)
I also created an IAM access key in the AWS console.

Now create a secret containing the IAM access key id and secret
so that cert-manager can use it to make Route53 changes for DNS challenges.
See the unencrypted example at `cert-manager/secrets/aws-route53-credential.example.yml`.
Use our normal [convention](./conventions.md) to en/de-crypt with `sopsandstrip`,
and save the encrypted version of the real manifest as `cert-manager/secrets/aws-route53-credential.yml`
before applying it.

```sh
# Write the manifest
vim tmpsecret.yml
# Encrypt the manifest
sopsandstrip --encrypt tmpsecret.yml > cert-manager/secrets/aws-route53-credential.yml
# Remove the unencrypted manifest
rm tmpsecret.yml

# Apply the encrypted manifest
sopsandstrip --decrypt cert-manager/secrets/aws-route53-credential.yml | kubectl apply -f -
```

Then apply the issuer.
We have both a staging and a production issuer available;
we'll use the staging issuer first so that Let's Encrypt doesn't give us a temp ban for too many requests
while we are trying to make this work.

```sh
kubectl apply -f cert-manager/clusterissuers/letsencrypt-issuer-staging.yml
```

Then enable HTTPS for the whoami service.
Note that we have to define a `Certificate` resource in this file.
Traefik can do this if you pay for Enterprise or are not using HA,
but when using Traefik Proxy + Cert Manager, we have to create it ourselves.

```sh
kubectl apply -f whoami/enable-https.yml
```

TODO: explain why using DNS challenges is important with Let's Encrypt.
Short version: they work well for clusters that aren't on the public Internet.

See also:

* <https://blog.crafteo.io/2021/11/26/traefik-high-availability-on-kubernetes-with-lets-encrypt-cert-manager-and-aws-route53/>
