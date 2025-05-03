---
title: Traefik and cert-manager
---

* Traefik can handle Let's Encrypt certs itself...
* ... but the fucking thing charges money for this if using with HA, as we are in k3s.
* Instead, we can use `cert-manager` to create and store the certs, and let Traefik use them.

Ugh

* Traefik can automatically manage Let's Encrypt certificates
    * You can configure it to automatically request them based on the services it is load balancing for
    * I've done this in Docker Swarm for a while now
    * However, this only works with a single instance of Traefik Proxy; you have to pay for Traefik Enterprise for this to work in highly available clusters
    * Kubernasty will be a highly available cluster; any node should be able to go down and the server should keep running, and when running it should still keep using correct certificates
* Cert Manager is recommended to use instead when you need a highly available cluster with Traefik IngressController and HTTPS.