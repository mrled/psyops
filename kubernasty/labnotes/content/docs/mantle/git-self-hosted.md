---
title: Self-hosted git
weight: 80
---

(See also [bootstrapping]({{< ref "bootstrapping" >}}))

[Kubefirst](https://kubefirst.io/) has a cool idea --
using your cluster to host the Git repository that the CI/CD tool uses.
They can deploy Gitlab for you in AWS as part of the install process.

Can we do that ourselves?

## Bootstrap from nothing

I haven't done this yet, but what I want to do is self-host a git server and bootstrap flux off of that.

* Deploy a storage system
  * One idea: Ceph
    * Ceph is what I'm using for cluster storage generally. Just install this first.
    * More painful when installing from scratch, because there's no CI/CD yet
    * OTOH, get it working once and prove it out and no pain for future clusters
  * OpenEBS on controller nodes
    * Make a convention that controller nodes will always dedicate a small amount of storage to OpenEBS
    * Currently my server is all controlplane + worker anyway, but this would be relevant if I ever migrate to dedicated controlplane
    * Maybe lighter weight and simpler to configure than Ceph
* Deploy a barebones git server
  * Maybe a basic gitea instance
  * Maybe a simple container running just ssh git, or git with the cgit web frontend
  * Create a Job to create an empty repo with a special name in that server...
    could be done with just shell commands for a simple container,
    or via API calls for gitea.
  * Create a NodePort exposing the Git server's SSH service;
    the user can connect to any node in the cluster on that port to push to the repo
  * At this point the user can optionally create another Job that retrieves a backup of the repo from elsewhere and pushes it
* The user downloads the flux binary and bootstraps like normal, passing the cluster DNS name for the git server.
  * I think that should work; I assume that flux will run git checkout inside the cluster.
  * If that doesn't work, create a Job that downloads the flux binary and bootstraps from inside the cluster.
* Now the user can interact with flux via the `flux` command, and push to the repo. Success!
* Next steps probably involve some kind of load balancing and ingress so that the NodePort is not necessary.
  * The NodePort can then be removed

### Bootstrapping Gitea

If Gitea were the initial cluster server, here's how we could bootstrap on it.

* Deploy Gitea, using a RWX filesystem option like CephFS for /data
* Create a Job that runs the same Gitea container and mounts /data (and can talk to the Gitea database)
  * Looks for a Kubernetes secret with a name like `gitea-admin-access-token`
    * Ensure a service account exists.
      Can just run the create command, it will exit with code 1 if the account already exists.
      ```text
      21:01:11 E1 Naragua kubernasty ∴ k exec -itn gitea gitea-0 -- gitea admin user create --username testea  --email testea@example.com --admin --random-password --random-password-length 24
      Defaulted container "gitea" out of: gitea, sidecar, init-directories (init)
      generated random password is 'yIpIFq2HiE6mpgj5xaJuraLz'
      New user 'testea' has been successfully created!

      21:02:09 E0 Naragua kubernasty ∴ k exec -itn gitea gitea-0 -- gitea admin user create --username testea  --email testea@example.com --admin --random-password --random-password-length 24
      Defaulted container "gitea" out of: gitea, sidecar, init-directories (init)
      generated random password is 'Vs5EY0297I6j9ksl2m49zS42'
      Command error: CreateUser: user already exists [name: testea]
      command terminated with exit code 1
      ```
    * Adds an access token with `gitea admin user generate-access-token --username USERNAME --raw`
      and saves the result to `gitea-admin-access-token` Secret
      ```text
      21:05:19 E1 Naragua kubernasty ∴ k exec -itn gitea gitea-0 -- gitea admin user generate-access-token --username testea --raw  --token-name test2
      Defaulted container "gitea" out of: gitea, sidecar, init-directories (init)
      e02abc19ec0901a1dc22db4e7717cd2d83ebb5b3
      ```
      ... might consider giving it a unique name every time with `--token-name` because there is no way to delete or overwrite an existing token
* Create a Job that reads the secret and does initial configuration
  * (btw, Gitea endpoints can be explored with the `/api/swagger` URI on any Gitea server as long as its enabled, which it is by default)
  * All of these actions could be first checked so the script is idempotent
  * With the admin user's token
    * Create a service account for pulling code, pushing code, and pushing artifacts, with with `POST /admin/users`
      (these could be separate for better separation of concerns)
    * Create an org with `POST /orgs` for the cluster
    * Find the newly-created org's Owners team ID with `GET /orgs/{org}/teams/search`
    * Place the service account in the owner team for the cluster org with `PUT /teams/{id}/members/{username}`
    * Create the cluster git repo with `POST /orgs/{org}/repos`
    * Create a webhook that notifies Flux with `POST /repos/{owner}/{repo}/hooks`
    * Set an access token for the service account with `POST /users/{user}/tokens`
  * With the service account's token
    * Set an SSH key with `POST /user/keys`

## Bootstrap from Github

This is easier to get started with.

* Start in Github
* Deploy gitea via Flux
* Create a special org and repo via the gitea UI
* Create an ssh key
  * `ssh-keygen -t ed25519 -N '' -C "flux" -f gitea-flux-ssh-key`
  * Retrieve the Gitea SSH key and save it in known_hosts format
    ```sh
     k exec -it -n gitea gitea-0 -c gitea -- sh -c 'cat /data/ssh/gitea.ed25519.pub' |
        grep -v '^#'|
        sed 's/^/gitea.micahrl.me /' > gitea_known_hosts
    ```
  * Create a Secret from the ssh key and known hosts and saev it to a file called flux-system-secret-new.yaml.
    We won't commit this to the repo, but we use it in the next step.
    ```sh
    kubectl create secret generic flux-system \
        --namespace flux-system \
        --from-file=identity=./gitea-flux-ssh-key \
        --from-file=identity.pub=./gitea-flux-ssh-key.pub \
        --from-file=known_hosts=./gitea_known_hosts \
        --dry-run=client -o yaml
    ```
  * Add the SSH public key to the org by going to `gitea.micahrl.me/user/repo/settings/keys`...
    in my gitea installation that URL is not linked in the HTML for `/user/repo/settings`,
    not sure why, but it does exist for me.
* Create a repo in Gitea
  * Push the Github repo to the Gitea repo, without changing the path of anything
  * Update the Gitea repo to point to itself in
* Configure flux to use the new repo
  * Suspend flux reconciliation:
    ```sh
    flux suspend source git flux-system -n flux-system
    flux suspend kustomization -n flux-system --all
    ```
  * Save the old flux-system secret, in case you want to roll back:
    `kubectl get secret -n flux-system flux-system -oyaml > flux-system-secret-orig.yaml`
  * Replace the flux-system secret with the new one with gitea credentials:
    `k replace -f flux-system-secret-new.yaml`
  * Edit the git repo in the server:
    `kubectl patch gitrepository -n flux-system flux-system --type='merge' -p '{"spec":{"url":"ssh://git@gitea.micahrl.me:kubernasty/cluster.git"}}'`
  * Change the contents of `kubernasty/mantle/flux-system/gotk-sync.yaml` to point to the new repo
  * Push the repo changes
  * Resume flux reconciliation:
    ```sh
    flux resume source git flux-system -n flux-system
    flux resume kustomization -n flux-system --all
    ```
* Migrate to locally hosted gitea once you're happy with ingress, certs, etc

## Post bootstrap tasks

* Add a webhook for flux
  * This makes pushes instantly start a flux reconciliation; flux doesn't have to poll
  * Flux side
    * This can all be done by Flux itself
    * See `kubernasty/crust/flux-config`
  * Gitea side
    * `https://gitea.micahrl.me/kubernasty/cluster/settings/hooks`
    * Add Webhook -> Gitea
    * Target URL: `http://notification-controller.flux-system.svc.cluster.local`,
      using empty port specifier to get default port 80.
      Do not set to `http://webhook-receiver...` even though there is such a service.
    * HTTP Method: `POST`
    * Secret: same secret as is stored in Flux
    * Trigger On: Push Events
    * Branch filter: master
    * Also requires configuring `ALLOWED_HOST_LIST` in Gitea configuration
  * Note that webhooks are rate limited
    * <https://github.com/fluxcd/flux2/discussions/3571>
* Add a webhook for Argo Workflows
  * Argo Workflows side, see `kubernasty/crust/argowf/workflows/common/EventSource.webhook.yaml`
  * Gitea side
    * Target URL: `http://webhook-eventsource-svc.argowf.svc.cluster.local:12000/gitea`
    * HTTP Method: `POST`
    * Secret: empty
    * TODO: use a webhook secret for security? not sure this matters
