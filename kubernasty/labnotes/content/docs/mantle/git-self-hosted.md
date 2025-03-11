---
title: Self-hosted git
weight: 80
---

I haven't done this yet, but what I want to do is self-host a git server and bootstrap flux off of that.

* Deploy a barebones git server
  * Maybe a basic gitea instance
  * Maybe a simple container running just ssh git, or git with the cgit web frontend
  * Create a Job to create an empty repo with a special name in that server
  * Create a NodePort exposing the Git server's SSH service;
    the user can connect to any node in the cluster on that port to push to the repo
  * At this point the user can optionally create another Job that retrieves a backup of the repo from elsewhere and pushes it
* The user downloads the flux binary and bootstraps like normal, passing the cluster DNS name for the git server.
  * I think that should work; I assume that flux will run git checkout inside the cluster.
  * If that doesn't work, create a Job that downloads the flux binary and bootstraps from inside the cluster.
* Now the user can interact with flux via the `flux` command, and push to the repo. Success!
* Next steps probably involve some kind of load balancing and ingress so that the NodePort is not necessary.
  * The NodePort can then be removed
