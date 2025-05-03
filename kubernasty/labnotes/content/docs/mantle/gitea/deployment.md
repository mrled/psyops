---
title: Gitea
weight: 10
---

TODO: Re-think this deployment so that it's easier to update, maybe reconsider helm.

A git server.

We started with the Gitea Helm chart,
but the default deploys dozens of resources in four thousand lines of unmaintainble YAML.

We whittled it down to 2 secrets, a deployment, and a service in just a few hundred lines by:

* Removing Redis, which we expect we don't need
* Skipping the Postgres deployment, in favor of using the CNPG operator instead

TODO: Expand Gitea instructions, place earlier so that other apps can use it

## Deploying gitea

Unfortunately, the Gitea Helm chart
[does not support a sqlite database](https://gitea.com/gitea/helm-chart/issues/95)
and [is not interested in doing so in the future](https://gitea.com/gitea/helm-chart/issues/388),
so our configuration is made more complicated by the need to deploy a Postgres server.
(We do not let the Helm chart configure a Postgres server for us,
because it provisions a shitty password,
and [there is no other way to use a secure one](https://gitea.com/gitea/helm-chart/issues/60).)

### Creating secrets files

```sh
pg_gitea_pass="$(pwgen 64)"
pg_admin_pass="$(pwgen 64)"
gt_admin_pass="$(pwgen 64)"
ll_gitea_pass="$(pwgen 64)"

mkdir -p manifests/atmosphere/gitea/secrets

cat > manifests/atmosphere/gitea/secrets/giteadb-credentials.secret.yaml <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: giteadb-credentials
  namespace: gitea
type: generic
stringData:
  # The password for the 'gitea' database user
  pgsql-gitea-password: $pg_gitea_pass
  # The password for the 'postgres' database admin user
  pgsql-admin-password: $pg_admin_pass
EOF

cat > manifests/atmosphere/gitea/secrets/gitea-admin-credentials.secret.yaml <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: gitea-admin-credentials
  namespace: gitea
type: generic
stringData:
  # Password for Gitea web admin user
  username: teamaster
  password: $gt_admin_pass
EOF

cat > manifests/atmosphere/gitea/secrets/lldap-credentials.secret.yaml <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: lldap-credentials
  namespace: gitea
type: generic
stringData:
  # Password for Gitea web admin user
  username: uid=gitea,ou=people,dc=kubernasty,dc=micahrl,dc=com
  password: $ll_gitea_pass
EOF

sops --encrypt --in-place manifests/atmosphere/gitea/secrets/giteadb-credentials.secret.yaml
sops --encrypt --in-place manifests/atmosphere/gitea/secrets/gitea-admin-credentials.secret.yaml
sops --encrypt --in-place manifests/atmosphere/gitea/secrets/lldap-credentials.secret.yaml
```

### Configure LLDAP

Create a gitea service account in LLDAP

* This must match the LLDAP secret created above
* Add this user to the `lldap_strict_readonly` group (TODO: is this ok?)

Create auth groups.
Note that group names must match what is in
{{< repolink "kubernasty/manifests/atmosphere/gitea/configmaps/gitea.overrides.yaml" >}}

* Add `gitadmins` group
    * Add a user to it
    * I add my `0p3r4t0r` administrative user to this.
* Add `totalgits` group
    * Add a user to it
    * You must also add your admin user to it, or else they will not be able to log in

## Log in as the administrator

* Log in as `teamaster` with the admin creds from `gitea-admin-credentials` secret,
  or a user in the `gitadmins` LLDAP group
* Top right button -> Site Administration
    * Configuration tab
        * Picture and Avatar Configuration section (... scroll down ...)
            * Disable Gravatar: true

## SSH connections from outside the cluster

Kubernetes does not have any native concept of a non-http(s) ingress.
However, Traefik can handle this.

First, we need to configure Traefik.

* Note the [k3s documentation](https://docs.k3s.io/networking) on configuring Traefik
* See the [Helm chart](https://github.com/traefik/traefik-helm-chart/blob/master/traefik/values.yaml)
  for a full list of Traefik configuration values.

We can do so with
{{< repolink "kubernasty/manifests/crust/traefik/traefik.config.yaml" >}}.

Once that's in place, we can use Traefik's custom `IngressRouteTCP` resource definition
to pass SSH traffic to the gitea-ssh service, in
{{< repolink "kubernasty/manifests/atmosphere/gitea/ingresses/gitea-ssh.in.yaml" >}}

We are restricted from using port 22 for reasons I haven't looked into yet,
so we have to use port 44822 instead.

## Create a second kube-vip interface

From your first cluster node, create another DaemonSet manifest.

```yaml
# Make sure this matches the version used to deploy
export KVVERSION=v0.5.8

alias kube-vip="ctr image pull ghcr.io/kube-vip/kube-vip:$KVVERSION; ctr run --rm --net-host ghcr.io/kube-vip/kube-vip:$KVVERSION vip /kube-vip"

kube-vip manifest daemonset \
    --interface psy0 \
    --address 192.168.1.201 \
    --inCluster \
    --taint \
    --controlplane \
    --services \
    --arp \
    --leaderElection
```

You must make changes before saving this to the manifests folder below.

* The name of the DaemonSet (I used `kube-vip-2`)
* The Prometheus port (I used `2212` rather than the default `2112`)

Then place in `/var/lib/rancher/k3s/server/manifest`.

TODO: Finish configuring this.
Right now it is just an extra IP address;
need to dedicate it to the `gitea.` subdomain
and use it for SSH and set SSH to port 22.

## TODO

* Enable Git LFS.
  I think this will require minio.
  <https://docs.gitea.io/en-us/config-cheat-sheet/#lfs-lfs>
* Run Git SSH on port 22.
  Actually not going to do this for now.
  Would require changing SSH config on k8s nodes.

## See also

* <https://github.com/nitnelave/lldap/blob/main/example_configs/gitea.md>
