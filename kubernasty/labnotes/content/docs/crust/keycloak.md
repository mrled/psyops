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

* Create a group that will have the ability to log in to Keycloak-protected endpoints.
  In the future, we might want to create groups that can only log in to some endpoints,
  so this group is a more expansive group we will place our own regular user into.
  I call mine `kubernasty-apps-all`.
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

I CAN'T GET THIS TO WORK, idk

[`traefik-forward-auth`](https://github.com/thomseddon/traefik-forward-auth)
is a service that provides SSO for traefik.
With it, we can protect all our apps behind one (hopefully) secure provider.
For most apps, this is better than any username/password authentication they may do natively,
since Keycloak is designed for this and gets a lot of security attention.

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

## Deployoing `oauth2-proxy`

* Use the [Keycloak OIDC Auth Provider instructions](https://oauth2-proxy.github.io/oauth2-proxy/docs/configuration/oauth_provider#keycloak-auth-provider)
* Note that the [Keycloak UI has changed](https://github.com/oauth2-proxy/oauth2-proxy/issues/1931#issuecomment-1374875310),
  so the official instructions should be changed in light of that Github comment.
  (Hopefully they fix this soon.)
* New client
  * Client type: `OpenID Connect`
  * Name: `kubernasty-oauth2-proxy`
  * Client authentication: `on`
  * Valid redirect URIs: `https://oauth2-proxy.kubernasty.micahrl.com/oauth2/callback`
  * Valid post logout redirect URIs: `https://*.kubernasty.micahrl.com/*`
  * Client scopes -> scope named after the client, like `kubernasty-oauth2-proxy-dedicated`
    * Configure new mapper -> Group Membership
      * Name: `client-group-manager`
      * Token claim name: `groups`
      * Full group path: `off`
    * Add mapper -> By configuration -> Audience
      * Name: `aud-mapper-client`
      * Included client audience: select the name of the client, like `kubernasty-oauth2-proxy`
      * Included custom audience: select the name of the client, like `kubernasty-oauth2-proxy`
* Show whether it's working
  * Client -> the client we created -> Client scopes -> Evaluate tab
    * Enter a user. It looks like this should populate with a list, but it doesn't just start typing.
    * Click "Generated user info" in bottom right
* Restrict to only members of the `kubernasty-apps-all` group
  * Via <https://stackoverflow.com/questions/54305880/how-can-i-restrict-client-access-to-only-one-group-of-users-in-keycloak>
  * Client -> the client we created
    * Roles tab -> Create role
      * I named it after the group `kubernasty-apps-all`
  * Realm -> Client scopes (NOT client scopes inside our client, but at the realm level)
    * Email scope
      * Scope tab -> Assign role.
        * Change filter dropdown to "Filter by clients"
        * Select the `kubernasty-apps-all` scope we created inside `kubernasty-oauth2-proxy`.
  * Groups -> `kubernasty-apps-all` group
    * This must have synced from LLDAP for this to work; make sure sync is working if you don't see it
    * Role mapping tab -> Assign role -> Filter by clients -> `kubernasty-apps-all`

### Create `oauth2-proxy-secrets.secret.yaml` manifest

Get the client secret from Keycloak -> the client we created -> Credentials tab.

{{< hint warning >}}
**You must create a base64-encoded `data` secret.**

Note that we have to do this as a `data` secret with base64-encoded values.
It doesn't work as a `stringData` secret with string values.
Be careful to `echo -n`, so that we don't get spurious newlines.
The oauth2-proxy helm chart requires this.
{{< /hint >}}

{{< hint warning >}}
**The oauth2-proxy documentation on generating the cookie secret is unreliable.**

I'm not sure if their `tr` invocations are GNU or just wrong,
but you probably want `| tr '+' '/' | tr '-' '_'` rather than `| tr -- '+/' '-_'`.

The Python, Bash, and OpenSSL options they provide all failed to deploy for me.
{{< /hint >}}

```sh
# Must match what was entered into Keycloak above
clientid_plain="kubernasty-oauth2-proxy"
# The key we copied above
clientsecret_plain="... SECRET VALUE ..."
# We generate a random value here
# This must be 32 bytes
cookiesecret="$(pwgen 32 | tr -d '\n' | base64 -w 0)"

clientid="$(echo -n "$clientid_plain" | base64 -w 0)"
clientsecret="$(echo -n "$clientsecret_plain" | base64 -w 0)"

cat > manifests/crust/keycloak/secrets/oauth2-proxy-secrets.secret.yaml <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: oauth2-proxy-secrets
  namespace: keycloak
  labels:
    app: oauth2-proxy
type: Opaque
data:
  client-id: $clientid
  client-secret: $clientsecret
  cookie-secret: $cookiesecret
EOF

sops --encrypt --in-place manifests/crust/keycloak/secrets/oauth2-proxy-secrets.secret.yaml
```
