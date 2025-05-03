---
title: Traefik
weight: 30
---

I installed traefik by copying the manifests from their GitHub repo into
{{< repolink "kubernasty/crust/traefik" >}}.
In retrospect, I don't recommend this,
and I will update this to use Helm in the future.

TODO: Install traefik with Helm.

TODO: Add docs about various traefik listen ports.

Take note of the middleware that redirects to HTTPS:
{{< repolink "kubernasty/crust/traefik/common/Middleware.redirect-to-https.yaml" >}}.

## whoami service

A useful service for testing.
Deploy with: `kubectl apply -f manifests/mantle/whoami/deployments/whoami.yml`.
TODO: This manifest doesn't exist any more, add another test.

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
TODO: This manifest doesn't exist any more, add another test.

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

