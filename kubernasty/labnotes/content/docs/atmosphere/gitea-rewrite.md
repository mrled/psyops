---
title: Rewrite with on-cluster repository
weight: 24
---

[Kubefirst](https://kubefirst.io/) has a cool idea --
using your cluster to host the Git repository that the CI/CD tool uses.
They can deploy Gitlab for you in AWS as part of the install process.

* Cluster creation remains the same
* Deploy Longhorn by manifest
    * We are doing very little deploy-time configuration,
      and all configuration can be done in the admin web UI
    * Currently we set the data volume path in the deploy-time config and that's it;
      probably better to set that to a location that we expect to bind-mount or symlink
      so that even if the filesystem location changes
      that can just be a requirement for any nodes in our cluster.
* Deploy a Git server by manifest
    * Use storage we just created
    * Create a repo on the server
        * Add a personal SSH key to that repo for our own access in later steps
        * Generate and add a service account SSH key to that repo for Flux access
    * Push manifests to the repo.
      Probably just using kubectl port forwarding,
      so that we don't have to set up External DNS, certificates, etc.
* Allow restoration of backups
    * Restore Kubernetes Secret and Certificate objects from cert-manager,
      including endpoint certs/secrets and also Let's Encrypt account keys.
    * Restore Longhorn volumes
* Deploy Flux
    * Basically the same as how we do now,
      but pointing it at the internal repo and giving it the generated key
    * Consider deploying with Helm, a la
      <https://managedkube.com/gitops/flux/weaveworks/guide/tutorial/2020/05/01/a-complete-step-by-step-guide-to-implementing-a-gitops-workflow-with-flux.html>
* Everything else remains the same as we currently have it

However, the biggest question here is the Git server.
Our current Gitea server deployment depends on more than just Longhorn for persistent volumes:

* external-dns for a hostname
* cert-manager for a valid HTTPS certificate from Let's Encrypt
* LLDAP for user management
* In the future it may also require Keycloak and traefik-forward-auth for Gitea SSO

How to handle this:

* Can we have it redeploy the Git server with those customizations from Flux?
    * I think we can just do this, because I redeployed many times while building it
    * So we deploy a bare minimum Gitea, and then reconfigure it once Flux is up and running
* We could use a barebones gitops-only Git server that doesn't sync users or allow SSO;
  could be a separate Gitea instance or even something like gitweb

## Aside: improve certificate management

Tearing down and rebuilding the cluster many times will cause Let's Encrypt problems.
They allow 50 registrations/renewals for a top level domain per week --
and since kubernasty is using a subdomain of `micahrl.com`,
any bans would be a big deal.

Options and considerations:

* Backup/restore certificates
* Use a wildcard certificate for kubernasty
* Use one of my other domains, at least while I'm in dev mode
* Add docs on how to do this with the Let's Encrypt staging servers,
  allowing for easy spinups/teardowns of noncritical environments

## Aside: backups and restores

* Any persistent volumes, like Longhorn
* Secrets that aren't stored elsewhere
