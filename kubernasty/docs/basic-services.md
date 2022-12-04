# Basic services

How to configure basic services once the cluster is up.

## whoami service

A useful service for testing.

`kubectl apply -f whoami/whoami.yml`

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
