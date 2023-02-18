---
weight: 80
title: Todo
---

* Using `flannel` for networking; is this encrypted? If not, can we move to a SDN that is encrypted?
* Consider using a separate subnet for kubernasty. Requires separate switch.
* Consider network redundancy for kubernasty. Requires USB NICs on my hosts (or different hardware with multiple NICs).
* Enable real load balancing with kube-vip per <https://kube-vip.io/docs/about/architecture/>
* Is traefik actually good?
    * Points against
        * Configuration is absolutely fucking insane, easily the worst thing about my Docker Swarm setup
        * Its biggest selling point is built-in Let's Encrypt support, but you can only use it with HA if you pay
    * Points in favor:
        * External DNS is designed to work with it directly, see <https://github.com/kubernetes-sigs/external-dns/blob/master/docs/faq.md>
* Bootstrap Gitea (or similar) onto the cluster, and do gitops based on that.
    * Similar to [kubefirst](https://kubefirst.io/), which looks dope except it doesn't work with local bare metal.
* Apps
    * Grafana
    * Private container registry - Gitea can do this
    * Private artifact server that can host arbitrary packages - Pip... - Gitea can do this
    * Private HTTP files server
        * Alpine APK
        * Debian .deb
        * Random large files that I might want CI/CD access to
    * Some kind of build server - Gitea CI, or Jenkins, or whatever
    * ArchiveBox
        * Some auto-retry thing
        * Some auto-ingest thing
    * SyncThing server
    * Deploy the labnotes to the cluster itself (not important, just for fun)
    * Linkding
    * Some stats stuff - prometheus, grafana, whatever
        * <https://geek-cookbook.funkypenguin.co.nz/recipes/swarmprom/>
    * Centralized logging! Is this ELK? Please have something better than ELK
    * Maybe a photos thing?
        * <https://geek-cookbook.funkypenguin.co.nz/recipes/photoprism/>
        * <https://geek-cookbook.funkypenguin.co.nz/recipes/immich/>
    * I wonder if this location sharing thing is any good? Skeptical about battery life. <https://owntracks.org/>
    * Nextcloud
        * I don't think I actually need this, idk if it is worth the effort
* My own code / existing stuff to move here
    * Ifrit Matrix bot
    * SalaciousPatronym Twitter bot
    * wiki.micahrl.com private WikiJS instance
* Secure everything
    * I don't understand Kubernetes RBAC, and I'm not sure if my cluster is horribly insecure by default or something
    * Secret data is [not encrypted at rest by default](https://kubernetes.io/docs/tasks/administer-cluster/encrypt-data/)
* Can we use firecracker?
* Accessibility over VPN
    * psynet
    * Tailscale
* Back up the cluster
    * Certs
    * Any generated encryption key
    * Persistent storage
    * ... what else?
* Change up certificate model
    * Probably need to move to a wildcard cert at this point
    * Consider moving off of micahrl.com ? I don't want to fuck up production Let's Encrypt availability. OTOH, that might not matter at all if I am just getting a single wildcard cert for *.kubernasty.micahrl.com.
    * I think there is no need for my cluster to own certs to other domain names -- I'm not going to ever expose this cluster to the public Internet, and I don't need it to server any `*.micahrl.com` names that aren't part of `*.kubernasty.micahrl.com`.
* Improve configuration DRY
    * TONS of repetition in my configuration
    * Would be nice if there was a top-level set of input vars files, and everything else flowed out naturally from there
* Rewrite sections that were reordered
    * At first, I did several things to deploy by hand (the "mantle" section)
    * Now, more of those are handled by Flux, but the docs and manifests are still there
    * Need to rewrite these so that the useful examples of how to deploy things by hand remain, without needing the old notes in place that no longer reflect reality
* Something should be telling me when containers and/or helm charts are out of date
