---
title: Keycloak with oauth2-proxy
weight: 51
---

This is an abandoned attempt to use `oauth2-proxy` instead of `traefik-forward-auth`.

oauth2-proxy has two advantages over TFA:

* It's more actively maintained
* It supports LDAP groups directly, with no need for a whitelist

However, I couldn't get it to work --
it is not able to get the correct claims,
probably a configuration issue of some kind.

Notes for as far as I got.

## Configuring LLDAP

* Create a group that will have the ability to log in to Keycloak-protected endpoints.
  In the future, we might want to create groups that can only log in to some endpoints,
  so this group is a more expansive group we will place our own regular user into.
  I call mine `kubernasty-apps-all`.
* Create a regular user for our own use, and add him to the group we just created.
  I call mine `mrled`.
  Save its password in your regular password manager.

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

### Still having problems

Need to come back to this.

* oauth2-proxy says it can't get the email or there isn't the right claim or something
* Keycloak saying scope requested was just profile -- does not include email scope even when I added it explicitly to `oauth2-proxy-value-overrides`.
