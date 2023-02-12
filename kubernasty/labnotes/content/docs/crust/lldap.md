---
title: LLDAP
weight: 40
---

We use LDAP for a single source of truth for users and service accounts,
via [nitnelave/lldap](https://github.com/nitnelave/lldap)

We will use this for:

* Keycloak, including Traefik forward authentication.
  This will let us put any Kubernasty service behind a login prompt.
* Some services which can talk to LDAP directly, like Gitea.

## About this deployment

Specifics of LDAP vary widely.

The mostly widely used LDAP deployment type is Active Directory;
keep in mind you may need to do some translation of other docs to make use of them.

## Prerequisite TLS certificate

We will generate a self-signed certificate for the LLDAP server

* LDAP connections are unencrypted by default
* The LDAP server contains passwords, which are pretty important to keep secure
* Kubernetes does not encrypt traffic between nodes by default
* You can use a certificate authority to generate certs for the LDAP server
* But then you have to maintain a certificate authority
* The benefit of a certificate authority is that the CA can sign new certs,
  which clients will accept the same as the original cert
* In our cluster, if we need to change the cert,
  we will just reference the new copy in new deployments
* We won't let outside clients connect directly to the LDAP server
  (it'll just be accessible inside the cluster),
  so we don't need a CA.
* This is upgradeable to a real CA in the future
  with the same level of effort as just deploying a new self-signed cert
* It means we don't have to learn about and configure encrypted Kubernetes network fabric now


{{< hint danger >}}
You cannot use ECDSA keys for LDAP --
they must be RSA.

The server may work with them, but clients like `ldapwhoami` don't.

Not sure if clients we care about, like Keycloak and Gitea, would work or not.

Just using RSA to be safe.
{{< /hint >}}

```sh
# Some tunable options
# 7300 days is 20 years, ur cluster won't last 20 weeks u piece of shit
validdays=7300
# The simple hostname for the container in your cluster
svchostname=lldap
# The namespace the container will be running in
svcnamespace=lldap
# I am not sure if there are constraints on the subject; something like this is typical:
certsubj="/C=US/ST=TX/O=Kubernasty LDAP Service/CN=$svchostname.$svcnamespace"

# Generate an RSA key
# ECDSA does NOT work!
openssl req -newkey rsa:4096 -x509 -nodes \
    -out lldap.crt.pem \
    -keyout lldap.key.pem \
    -days "$validdays" \
    -subj "$certsubj" \
    -addext "subjectAltName = DNS:$svchostname,DNS:$svchostname.$svcnamespace,DNS:$svchostname.$svcnamespace.svc.cluster.local"

# Verify that the common name and subject alt names are as intended
openssl x509 -noout -text -in lldap.crt.pem | less

cat lldap.key.pem lldap.crt.pem > lldap.combined.pem
gopass insert -m kubernasty/lldap.crt.pem < lldap.crt.pem
gopass insert -m kubernasty/lldap.key.pem < lldap.key.pem
gopass insert -m kubernasty/lldap.combined.pem < lldap.combined.pem
```

## Deploying lldap

Create the various manifest files under
{{< repolink "kubernasty/manifests/crust/lldap" >}}.

### Create `lldap-credentials.secret.yaml`

The admin username will be `0p3r4t0r`, and the password we generate below.

```sh
lldapJwtSecret="$(pwgen 64)"

gopass generate kubernasty/lldap-0p3r4t0r-pw
lldapLdapUserPass="$(gopass cat kubernasty/lldap-0p3r4t0r-pw)"

cat > kubernasty/manifests/crust/lldap/secrets/lldap-credentials.secret.yaml <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: lldap-credentials
  namespace: lldap
type: generic
stringData:
  lldapJwtSecret: $lldapJwtSecret
  lldapLdapUserPass: $lldapLdapUserPass
EOF

sops --encrypt --in-place manifests/crust/lldap/secrets/lldap-credentials.secret.yaml
```

### Create `lldap-tls.secret.yaml` and `lldap-cert.configmap.yaml`

```sh
key="$(gopass -n kubernasty/lldap.key.pem | base64 -w 0)"
certificate="$(gopass -n kubernasty/lldap.crt.pem | base64 -w 0)"

cat > manifests/crust/lldap/secrets/lldap-tls.secret.yaml <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: lldap-tls
  namespace: lldap
type: generic
data:
  key: $key
  certificate: $certificate
EOF

sops --encrypt --in-place manifests/crust/lldap/secrets/lldap-tls.secret.yaml

cat > manifests/crust/lldap/configmaps/lldap-cert.configmap.yaml <<EOF
apiVersion: v1
kind: ConfigMap
metadata:
  name: lldap-cert
  namespace: lldap
binaryData:
  certificate: $certificate
EOF
```

### Create the other manifests

* Note that what's there in {{< repolink "kubernasty/manifests/crust/lldap" >}}
  has some hardcoded values like my DNS and x509 names.
* The container users unprivileged ports 3890/6360 for LDAP/LDAPS by default,
  rather than the well-known but privileged values of 389/636.
  It also uses 17170 for its web UI port.
  However, we can make the _Kubernetes service_ listen in the well-known ports.

### Deploy

Commit and push, and Flux will deploy OpenLDAP automatically.

## Log in

How can we log in to it?
The LDAP service isn't exposed to the network.

### Log in on the command line from an ephemeral container

One way is to create an ephemeral container and install LDAP clients in it.
From your kubectl client machine:

```sh
kubectl get pods -n lldap
# Returning e.g.:
# NAME                        READY   STATUS    RESTARTS   AGE
# lldap-56f79f9b57-8mrw7   1/1     Running   0          12m

kubectl debug -it lldap-56f79f9b57-8mrw7 --image=alpine:latest --target=lldap --namespace=lldap
# Now you will be in a shell in a new ephemeral container
```

From that shell we can:

```sh
apk add openldap-clients

nslookup lldap
# Server:		10.43.0.10
# Address:	10.43.0.10:53
# Name:	lldap.lldap.svc.cluster.local
# Address: 10.43.96.231
# ...

# Try to query the LDAP server anonymously - this should fail
ldapwhoami -x -H ldap://lldap:389

# Authenticate and query the ldap server as the admin user
admindn="cn=0p3r4t0r,ou=people,dc=kubernasty,dc=micahrl,dc=com"
adminpw="adminp@ssw0rd"
ldapsearch -x -H ldap://lldap:389 -D "$admindn" -w "$adminpw" -b ou=people,dc=kubernasty,dc=micahrl,dc=com -s sub '(objectClass=*)' 'givenName=username*'
# ... should list the admin user

# To test connecting over TLS, you have to copy the certificate to the ephemeral container
# You catn just cat >/cert.pem and paste it into your terminal.
# Once that's done:
export LDAPTLS_CACERT=/cert.pem
ldapsearch -x -H ldaps://lldap:636 -D "$admindn" -w "$adminpw" -b ou=people,dc=kubernasty,dc=micahrl,dc=com -s sub '(objectClass=*)' 'givenName=username*'
# ... should list the admin user again
```

## Troubleshooting

* Older LDAP commands like `ldapsearch` will give a generic error like
  `ldap_sasl_bind(SIMPLE): Can't contact LDAP server (-1)`
  if they can't authenticate the TLS certificate for `ldaps://`.
  Differentiate between no network connectivity to the lldap service and an untrusted CA cert
  by `exec`ing into a container and running a command like
  `openssl s_client -connect lldap:636`.
  If it shows your certificate, the host has network access.
  (We use this method because ping is blocked(?)
  and you can't talk to the TLS service directly over netcat.)
