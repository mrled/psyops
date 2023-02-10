---
title: OpenLDAP (INCOMPLETE)
weight: 80
---

We install OpenLDAP for a single source of truth for users and service accounts.

We will use this for:

* Keycloak, including Traefik forward authentication.
  This will let us put any Kubernasty service behind a login prompt.
* Some services which can talk to OpenLDAP directly, like Gitea.

## About this deployment

Specifics of LDAP vary widely.

The mostly widely used LDAP deployment type is Active Directory;
keep in mind you may need to do some translation of other docs to make use of them.

## Prerequisite TLS certificate

We will generate a self-signed certificate for the OpenLDAP server

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
You cannot use ECDSA keys for OpenLDAP --
they must be RSA.

.. maybe?
{{< /hint >}}

```sh
# Some tunable options
# 7300 days is 20 years, ur cluster won't last 20 weeks u piece of shit
validdays=7300
# The simple hostname for the container in your cluster
svchostname=openldap
# The namespace the container will be running in
svcnamespace=openldap
# I am not sure if there are constraints on the subject; something like this is typical:
certsubj="/C=US/ST=TX/O=Kubernasty LDAP Service/CN=$svchostname.$svcnamespace"

# Generate an RSA key
# ECDSA does NOT work!
openssl req -newkey rsa:4096 -x509 -nodes \
    -out slapd.crt.pem \
    -keyout slapd.key.pem \
    -days "$validdays" \
    -subj "$certsubj" \
    -addext "subjectAltName = DNS:$svchostname,DNS:$svchostname.$svcnamespace,DNS:$svchostname.$svcnamespace.svc.cluster.local"

# # Actually scratch that, let's see if we can use an ECDSA key
# # Note, this requires OpenSSL 1.1.1
# # <https://security.stackexchange.com/questions/74345/provide-subjectaltname-to-openssl-directly-on-the-command-line>
# openssl ecparam -name secp521r1 -genkey -param_enc explicit -out slapd.key.pem
# openssl req -new -x509 \
#     -key slapd.key.pem \
#     -out slapd.crt.pem \
#     -days "$validdays" \
#     -subj "$certsubj" \
#     -addext "subjectAltName = DNS:$svchostname,DNS:$svchostname.$svcnamespace"

# Verify that the common name and subject alt names are as intended
openssl x509 -noout -text -in slapd.crt.pem | less

cat slapd.key.pem slapd.crt.pem > slapd.combined.pem
gopass insert -m kubernasty/slapd.crt.pem < slapd.crt.pem
gopass insert -m kubernasty/slapd.key.pem < slapd.key.pem
gopass insert -m kubernasty/slapd.combined.pem < slapd.combined.pem
```

## Deploying OpenLDAP

First, I created the various manifest files under `openldap/...`.

### Create `openldap-users.secret.yaml`

To make the openldap-secret.yaml, copy
{{< repolink "kubernasty/manifests/crust/openldap/secrets/openldap-secret.UNENCRYPTED.yaml.txt" >}}
to `openldap-users.secret.yaml`.
Include an `adminpassword`, which is the password for the admin LDAP user;
a list of `users` separated by commas, which will be created on the first startup;
and a list of `passwords` separated by commas for those users.

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: openldap-users
  namespace: openldap
type: generic
stringData:
  adminpassword: p@ssw0rd
  users: testuser,testotheruser
  passwords: user1p@ssw0rd,user2p@ssw0rd
```

{{< hint warning >}}
You must provide at least one user and password, aside from the administrator password.
If you don't set these, or pass an empty string,
default users with dictionary passwords will be created.
{{< /hint >}}

Then do the normal `sops --encrypt --in-place manifests/crust/openldap/secrets/openldap-users.secret.yaml`.

### Create `openldap-tls.secret.yaml` and `openldap-cert.configmap.yaml`

```sh
key="$(gopass -n kubernasty/slapd.key.pem | base64 -w 0)"
certificate="$(gopass -n kubernasty/slapd.crt.pem | base64 -w 0)"

cat > manifests/crust/openldap/secrets/openldap-tls.secret.yaml <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: openldap-tls
  namespace: openldap
type: generic
data:
  key: $key
  certificate: $certificate
EOF

sops --encrypt --in-place manifests/crust/openldap/secrets/openldap-tls.secret.yaml

cat > manifests/crust/openldap/configmaps/openldap-cert.configmap.yaml <<EOF
apiVersion: v1
kind: ConfigMap
metadata:
  name: openldap-cert
binaryData:
  certificate: $certificate
EOF
```

### Create the other manifests

* Note that what's there in {{< repolink "kubernasty/manifests/crust/openldap" >}}
  has some hardcoded values like my DNS and x509 names.
* Per [the readme](https://github.com/bitnami/containers/tree/main/bitnami/openldap),
  the container users unprivileged ports 1389/1636 for LDAP/LDAPS by default,
  rather than the well-known but privileged values of 389/636.
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
kubectl get pods -n openldap
# Returning e.g.:
# NAME                        READY   STATUS    RESTARTS   AGE
# openldap-56f79f9b57-8mrw7   1/1     Running   0          12m

kubectl debug -it openldap-56f79f9b57-8mrw7 --image=alpine:latest --target=openldap --namespace=openldap
# Now you will be in a shell in a new ephemeral container
```

From that shell we can:

```sh
apk add openldap-clients

nslookup openldap
# Server:		10.43.0.10
# Address:	10.43.0.10:53
# Name:	openldap.openldap.svc.cluster.local
# Address: 10.43.96.231
# ...

# Anonymously query the LDAP server
ldapwhoami -x -H ldap://openldap:389
# Should return: anonymous
ldapsearch -x -H ldap://openldap:389 -b dc=kubernasty,dc=micahrl,dc=com
# ... should list the users you created

# AUthenticate and query the ldap server as the admin user
admindn="cn=admin,dc=kubernasty,dc=micahrl,dc=com"
adminpw="adminp@ssw0rd"
ldapwhoami -x -H ldap://openldap:389 -D "$admindn" -w "$adminpw"
# Should return: dn:cn=admin,dc=kubernasty,dc=micahrl,dc=com
ldapsearch -x -H ldap://openldap:389 -D "$admindn" -w "$adminpw" -b ou=users,dc=kubernasty,dc=micahrl,dc=com -s sub '(objectClass=*)' 'givenName=username*'
# ... should list the users you created

# Authenticate and query the ldap server as the test user
userdn="cn=testuser,ou=users,dc=kubernasty,dc=micahrl,dc=com"
userpw="user1p@ssw0rd"
ldapwhoami -x -H ldap://openldap:389 -D "$userdn" -w "$userpw"
# Should return: dn:cn=testuser,ou=users,dc=kubernasty,dc=micahrl,dc=com
ldapsearch -x -H ldap://openldap:389 -D "$userdn" -w "$userpw" -b ou=users,dc=kubernasty,dc=micahrl,dc=com -s sub '(objectClass=*)' 'givenName=username*'
# ... should list the users you created
```

However, connecting over TLS will require the certificate,
which is mounted from a configmap.
I'm not sure if that's possible on ephemeral containers?
But you can use the phphldapadmin container once it is running.

```sh
apt-get update && apt-get install ldap-utils
admindn="cn=admin,dc=kubernasty,dc=micahrl,dc=com"
adminpw="adminp@ssw0rd"
ldapwhoami -x -H ldaps://openldap:636 -D "$admindn" -w "$adminpw"
```

### Log in from phpLDAPAdmin

Flux has also deployed phpLDAPAdmin.

<https://phpldapadmin.kubernasty.micahrl.com/>

You log in with a **DN**, not just the username.
For instance, the `testuser` we created in the openldap users secret has a DN of
`cn=testuser,ou=users,dc=kubernasty,dc=micahrl,dc=com`.
The admin user has a DN of
`cn=admin,dc=kubernasty,dc=micahrl,dc=com`.

## Remaining work

* TODO: should we disable anonymous binds?
* TODO: schema????????

## Troubleshooting

* Use the simplest query for binding anonymously
* Check connectivity to the server over SSL by `exec`ing into a container and running a command like
  `openssl s_client -connect openldap:636`.
  If it shows your certificate, the host has network access.
  (This is kind of tricky because ping is blocked(?)
  and you can't talk to the TLS service directly over netcat.)
