---
title: Authelia
weight: 50
---

TODO: talk about the rest of the authelia config, how to deploy and connect to LDAP, etc

TODO: make a doc about how I'm using 389 Directory Server but instead recommend LLDAP

Authelia can talk to an LDAP server and provide

* middleware for traefik that requires cookie auth
* headers to pass to backend services
* OIDC provider, including for kubectl

## OIDC provider for kubectl

* Requires [kubelogin](https://github.com/int128/kubelogin)
* Configure an OIDC confidential client, the kind with a client secret --
  as far as I can tell, this must be a confidential client rather than a public client,
  and you must share the client secret with all admin users.
  However, without accompanying admin _credentials_,
  I believe the secret is useless.
  There may be a better solution out there somewhere.

First, configure OIDC in Authelia:

```yaml
    identity_providers:
      oidc:
        authorization_policies:
          patricii:
            # Require membership in the patricii group.
            default_policy: deny
            rules:
              - policy: two_factor
                subject: "group:patricii"
        clients:
          - client_name: Kubernetes
            client_id: kubernasty-controlplane
            client_secret: {{ secret "/secrets/OIDIC_CLIENT_SECRET_KUBERNASTY" }}
            redirect_uris:
              # This is required to work with `kubectl oidc-login` from <https://github.com/int128/kubelogin>
              - http://localhost:8000
            scopes:
              - openid
              - email
              - profile
              - groups
              - offline_access
            authorization_policy: patricii
```

kubelogin adds a `kubectl oidc-login` subcommand to `kubectl`.
Once kubelogin is installed per its instructions, run a command like:

```sh
kubectl oidc-login setup \
    --oidc-issuer-url=https://auth.micahrl.me \
    --oidc-client-id=kubernasty-controlplane \
    --oidc-client-secret=REDACTED \
    --oidc-extra-scope="groups email" \
    --v=10
```

This command is intended as a user-friendly guide for setting up OIDC for the first time.
This opens a browser to `http://localhost:8000`, which is temporarily served by kubelogin.
This immediately redirects to the issuer URL you passed,
which prompts you to log in and authorize the action.
Once it does, it verifies that it has the permissions it needs,
and gives a list of instructions for modifying your `~/.kube/config` file.

When troubleshooting, pay attention to the claims in the JWT,
which are printed to the terminal with `--v=10`.
They should look like this:

```text
I0630 10:23:14.636151    7391 get_token.go:104] you got a token: {
  "amr": [
    "pwd",
    "pop",
    "swk",
    "user",
    "pin",
    "mfa"
  ],
  "at_hash": "1234...",
  "aud": [
    "kubernasty-controlplane"
  ],
  "auth_time": 1719760856,
  "azp": "kubernasty-controlplane",
  "client_id": "kubernasty-controlplane",
  "email": "mrladmin@micahrl.me",
  "email_verified": true,
  "exp": 1719764549,
  "groups": [
    "patricii",
    "totalgits"
  ],
  "iat": 1719760949,
  "iss": "https://auth.micahrl.me",
  "jti": "qwer...",
  "nonce": "asdf...",
  "sub": "zxcv..."
}
```

Specifically the `email` and `groups` claims --
if those are not present or not correct,
authorization will fail.

To use this, configure the Kubernetes servers with extra arguments:

```yaml
    extraArgs:
      oidc-issuer-url: https://auth.micahrl.me
      oidc-client-id: kubernasty-controlplane
      oidc-username-claim: email
      oidc-groups-claim: groups
```

Note that the server doesn't need the client secret.
