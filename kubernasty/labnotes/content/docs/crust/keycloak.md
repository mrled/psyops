---
title: Keycloak
weight: 50
---

## Deploying Keycloak

* The Helm chart is pretty magical (pejorative),
  and I had to do a lot of investigating to get it working for me.
  Aside from this page,
  you may need the [Troubleshooting]({{< ref "troubleshooting" >}}) document as well.
* The Helm chart we use creates the ingress for us
  (as we specify in our override config),
  so we have to adapt that section of
  {{< repolink "kubernasty/manifests/crust/keycloak/configmaps/keycloak.overrides.yaml" >}}
  to look like other Ingress objects we've created.
  * It was useful to compare the YAML for working ingresses I'd already made
    with the one that the chart generates.
    You can get any object in YAML format with
    `kubectl get OBJECT_TYPE -n NAMESPACE OBJECT_NAME -o yaml`.
* You should avoid having users with the same name in both the Keycloak and LLDAP databases.
  (Note your administrative users - don't call them `admin` in both places.
  I use the username `keymaker` for the Keycloak admin user,
  and vanilla `0p3r4t0r` for the LLDAP admin user.)
  * If there are users of the same name created independently, syncing users in Keycloak
    will show "1 user failed", and there will be an error in the container logs naming the user.

### Create `keycloak-credentials.secret.yaml`

```sh
gopass generate kubernasty/keycloak-admin-user-keymaster 64
adminpw="$(gopass cat kubernasty/keycloak-admin-user-keymaster)"

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
  postgres-password: $pgpass
EOF

sops --encrypt --in-place manifests/crust/keycloak/secrets/keycloak-pass.secret.yaml
```

## Configuring LLDAP

* Create a regular user for our own use, and add him to the group we just created.
  I call mine `mrled`.
  Save its password in your regular password manager.

## Configuring KeyCloak

* Log in to LLDAP
  * Create the Keycloak user
    * User named `keycloak`
    * Add it to the `lldap_admin` group.
      If you don't do this, it'll connect, but sync won't work.
    * Store password in gopass, `gopass generate kubernasty/lldap/keycloak 64`
* Log in to Keycloak
  * Configure LDAP
    * <https://github.com/nitnelave/lldap/blob/main/example_configs/keycloak.md>
    * Connection URL: `ldap://lldap.lldap:389`
    * TODO: Have Keycloak connect to LLDAP over TLS
    * Bind DN: `uid=keycloak,ou=people,dc=kubernasty,dc=micahrl,dc=com`
    * When it says to "sync users",
      this is done from the action dropdown in the upper right of the LDAP integration page.
    * TODO: I can't get it to sync only changed users --
      when I try, LLDAP logs
      `🚨 [error]: [LDAP] Service Error: while handling incoming messages: while receiving LDAP op: ldapmsg invalid` --
      but my directory will be small enough that I just have it do a full sync every 30 seconds.
    * Make sure to enable the `Trust email` option, so that Keycloak considers email address in LLDAP as "verified"

## Deploying `traefik-forward-auth`

[`traefik-forward-auth`](https://github.com/thomseddon/traefik-forward-auth)
is a service that provides SSO for traefik.
With it, we can protect all our apps behind one (hopefully) secure provider.
For most apps, this is better than any username/password authentication they may do natively,
since Keycloak is designed for this and gets a lot of security attention.

Note the `WHITELIST` environment variable in
{{< repolink "kubernasty/manifests/crust/keycloak/deployments/tfa.deployment.yaml" >}}.
List the email addresses if the users you want there.

### Configure Keycloak

* See also <https://geek-cookbook.funkypenguin.co.nz/recipes/keycloak/setup-oidc-provider/>
* Log in to Keycloak
  * Configure OIDC
    * `Master` realm -> Clients -> Create
    * Client type: `openid-connect`
    * Client ID: `kubernasty-tfa`
    * Save (moves to second page of create action)
    * Client Authentication: `On`
    * Save (creates the client and shows the full settings page)
    * Valid redirect URIs: `https://*.kubernasty.micahrl.com/*`
    * Valid post logout redirect URIs: `https://*.kubernasty.micahrl.com/*`
    * Save
    * Credentials -> Client secret -> copy

Now we can create the `tfa-secrets` secret.

### Create `tfa-secrets.secret.yaml` manifest

```sh
# Must match what was entered into Keycloak above
clientid="kubernasty-tfa"
# The key we copied above
clientsecret="... SECRET VALUE ..."
# We generate a random value here
authsecret="$(pwgen 64)"

cat > manifests/crust/keycloak/secrets/tfa-secrets.secret.yaml <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: tfa-secrets
  namespace: keycloak
  labels:
    app: traefik-forward-auth
type: Opaque
stringData:
  tfa-oidc-client-id: $clientid
  tfa-oidc-client-secret: $clientsecret
  tfa-auth-secret: $authsecret
EOF

sops --encrypt --in-place manifests/crust/keycloak/secrets/tfa-secrets.secret.yaml
```

### Testing `traefik-forward-auth`

* We deploy `tfawhoami` pod for this purpose
* Note that in the `traefik-forward-auth-mw` at
  {{< repolink "kubernasty/manifests/crust/keycloak/middlewares/tfa.middleware.yaml" >}},
  we create the middleware in the `kube-system` namespace.
  I think this is required, but I don't remember for sure.
* Note that in the `twawhoami` ingress at
  {{< repolink "kubernasty/manifests/crust/keycloak/ingresses/tfawhoami.ingress.yaml" >}},
  we add a label
  `traefik.ingress.kubernetes.io/router.middlewares: kube-system-traefik-forward-auth-mw@kubernetescrd`.
  See that the middleware specifier is `NAMESPACE-NAME@kubernetescrd`.
* Adding that label will protect other ingresses behind Keycloak.
* Be careful: if you don't add that label, an ingress is open to anyone who can talk to your cluster.
