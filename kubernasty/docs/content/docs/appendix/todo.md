---
weight: 80
title: Todo
---

* Using `flannel` for networking; is this encrypted? If not, can we move to a SDN that is encrypted?
* Consider using a separate subnet for kubernasty. Requires separate switch.
* Consider network redundancy for kubernasty. Requires USB NICs on my hosts (or different hardware with multiple NICs).
* Enable real load balancing with kube-vip per <https://kube-vip.io/docs/about/architecture/>
* Use something like [ExternalDNS](https://github.com/kubernetes-sigs/external-dns) to let me manage Route53 records from within Kubernetes
* Is traefik actually good?
    * Points against
        * Configuration is absolutely fucking insane, easily the worst thing about my Docker Swarm setup
        * Its biggest selling point is built-in Let's Encrypt support, but you can only use it with HA if you pay
    * Points in favor:
        * External DNS is designed to work with it directly, see <https://github.com/kubernetes-sigs/external-dns/blob/master/docs/faq.md>
* Bootstrap Gitea (or similar) onto the cluster, and do gitops based on that.
    * Similar to [kubefirst](https://kubefirst.io/), which looks dope except it doesn't work with local bare metal.
* Apps
    * Gitea private git server
    * Grafana
    * Private container registry
    * Private artifact server that can host arbitrary packages - Pip, Deb, Alpine APK...
    * Some kind of build server - Gitea CI, or Jenkins, or whatever
* Secure everything
    * I don't understand Kubernetes RBAC, and I'm not sure if my cluster is horribly insecure by default or something
    * Secret data is [not encrypted at rest by default](https://kubernetes.io/docs/tasks/administer-cluster/encrypt-data/)
