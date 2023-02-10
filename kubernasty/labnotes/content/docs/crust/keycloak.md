---
title: Keycloak
weight: 50
---

## Deploying Keycloak

### Create `keycloak-credentials.secret.yaml`

```sh
gopass generate kubernasty/keycloak-admin 64
adminpw="$(gopass cat kubernasty/keycloak-admin)"

mkdir -p manifests/crust/keycloak/secrets
cat > manifests/crust/keycloak/secrets/keycloak-credentials.secret.yaml <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: keycloak-credentials
  namespace: keycloak
type: generic
stringData:
  adminpw: $adminpw
EOF

sops --encrypt --in-place manifests/crust/keycloak/secrets/keycloak-credentials.secret.yaml
```


### Create `keycloakdb-pass.secret.yaml`

```sh
kcpass="$(pwgen 64)"
pgpass="$(pwgen 64)"

mkdir -p manifests/crust/keycloak/secrets
cat > manifests/crust/keycloak/secrets/keycloak-pass.secret.yaml <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: keycloakdb-pass
  namespace: keycloak
type: generic
stringData:
  # The password for the 'keycloak' user
  password: $kcpass
  # The password for the 'postgres' database admin user
  postgresPassword: $pgpass
EOF

sops --encrypt --in-place manifests/crust/keycloak/secrets/keycloak-pass.secret.yaml
```
