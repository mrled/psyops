---
weight: 80
title: Todo
---

* Using `flannel` for networking; is this encrypted? If not, can we move to a SDN that is encrypted?
* Consider using a separate subnet for kubernasty. Requires separate switch.
* Consider network redundancy for kubernsaty. Requires USB NICs on my hosts (or different hardware with multiple NICs).
* Enable real load balancing with kube-vip per <https://kube-vip.io/docs/about/architecture/>
* Install the kubernetes dashboard: <https://docs.k3s.io/installation/kube-dashboard>
* Enable the traefik dashboard, securely
* Use something like [ExternalDNS](https://github.com/kubernetes-sigs/external-dns) to let me manage Route53 records from within Kubernetes
