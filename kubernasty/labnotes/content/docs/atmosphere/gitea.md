---
title: Gitea
weight: 20
---

A git server.

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

### Create a gitea user in LLDAP

* This must match the LLDAP secret created above
* Add this user to the `lldap_strict_readonly` group (TODO: is this ok?)

## TODO

* Enable Git LFS.
  I think this will require minio.
  <https://docs.gitea.io/en-us/config-cheat-sheet/#lfs-lfs>
