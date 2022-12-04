# Storage - Longhorn

**This is a disorganized mess that needs to be rewritten.**

Among other things, it doesn't yet support HTTPS certificates properly.
It also includes a bunch of cert-manager stuff that has already been refactored into [Ingress and certificates](./ingress-and-certificates.md).

## Installing

* Follow their install instructions <https://longhorn.io/docs/1.3.2/deploy/install/install-with-helm/>

```sh
helm repo add longhorn https://charts.longhorn.io
helm repo update
helm install longhorn longhorn/longhorn --namespace longhorn-system --create-namespace
```

### nginx HTTP ingress

This starts Longhorn, but you can't talk to it without configuring an ingress controller.
I configure mine to listen on port 7780 because it's just temporary.
Later, we probably want a more permanent solution with HTTPS etc.
For now, I create a user called `beefadmin` (I dunno).

You can do that like this:

```sh
USER=foo
PASSWORD=bar
# The 'auth' filename is apparently mandatory
echo "${USER}:$(echo "${PASSWORD}" | openssl passwd -stdin -apr1)" >> auth
cat auth
# foo:$apr1$FnyKCYKb$6IP2C45fZxMcoLwkOwf7k0

kubectl -n longhorn-system create secret generic basic-auth --from-file=auth
# secret/basic-auth created
kubectl -n longhorn-system get secret basic-auth -o yaml
# apiVersion: v1
# data:
#   auth: Zm9vOiRhcHIxJEZueUtDWUtiJDZJUDJDNDVmWnhNY29Md2tPd2Y3azAK
# kind: Secret
# metadata:
#   creationTimestamp: "2020-05-29T10:10:16Z"
#   name: basic-auth
#   namespace: longhorn-system
#   resourceVersion: "2168509"
#   selfLink: /api/v1/namespaces/longhorn-system/secrets/basic-auth
#   uid: 9f66233f-b12f-4204-9c9d-5bcaca794bb7
# type: Opaque

kubectl apply -f longhorn/longhorn.yml
```

DO NOT USE:

```sh

echo "
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: longhorn-ingress
  namespace: longhorn-system
  annotations:
    # type of authentication
    nginx.ingress.kubernetes.io/auth-type: basic
    # prevent the controller from redirecting (308) to HTTPS
    nginx.ingress.kubernetes.io/ssl-redirect: 'false'
    # name of the secret that contains the user/password definitions
    nginx.ingress.kubernetes.io/auth-secret: basic-auth
    # message to display with an appropriate context why the authentication is required
    nginx.ingress.kubernetes.io/auth-realm: 'Authentication Required '
spec:
  rules:
  - http:
      paths:
      - pathType: Prefix
        path: "/"
        backend:
          service:
            name: longhorn-frontend
            port:
              number: 7780
" | kubectl -n longhorn-system create -f -
# ingress.networking.k8s.io/longhorn-ingress created

kubectl -n longhorn-system get ingress
# NAME               CLASS    HOSTS   ADDRESS                                     PORTS   AGE
# longhorn-ingress   <none>   *       192.168.1.133,192.168.1.148,192.168.1.153   7780    4s
```

Then you can go in to the UI and make changes.
(Probably worth setting `defaultDataPath` during install to `/psyopsos-data/roles/k3s/longhorn/data`,
but I didn't realize that when I did this the first time.)

### traefik HTTPS ingress

HTTPS provisioning requires storage for the certs,
which means it's useful to get the nginx configuration first,
so that you can configure your Longhorn storage.

The open source version of Traefik doesn't support running on multiple nodes with HTTPS,
which means it doesn't support our HA cluster.
This means we can't use its built-in Let's Encrypt support;
we have to use cert-manager instead.

Of course, k3s ships with traefik, and we are using it.
So we don't need to deploy traefik at this point, just configure it.

Save this to `/var/lib/rancher/k3s/server/manifests/traefik-config.yml`.

```yaml
apiVersion: helm.cattle.io/v1
kind: HelmChartConfig
metadata:
  name: traefik
  namespace: kube-system
spec:
  valuesContent: |-
    image:
      name: traefik
      tag: v2.9

    rbac:
      enabled: true
    ports:
      web:
        hostPort: 80
        http:
          redirections:
            entryPoint:
              to: websecure
              scheme: https

      websecure:
        hostPort: 443
        tls:
          enabled: true

    providers:
      kubernetesIngress:
        publishedService:
          enabled: true
        allowExternalNameServices: true
      kubernetesCRD:
        allowExternalNameServices: true
    priorityClassName: "system-cluster-critical"

    # Disabling this for now, seems related to forwardedHeaders stuff (see below)
    # proxyProtocol:
    #   enabled: true
    #   trustedIPs:
    #     - 10.0.0.0/8

    # I don't really understand the security implications of X-Forwarded-* headers,
    # but I don't think I need to care about them.
    # https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/X-Forwarded-For
    # > Any security-related use of X-Forwarded-For
    # > (such as for rate limiting or IP-based access control)
    # > must only use IP addresses added by a trusted proxy."
    # ... IP-based access control is dumb and I don't need rate limiting on my home cluster.
    # forwardedHeaders:
    #   enabled: true
    #   trustedIPs:
    #     - 10.0.0.0/8

    ssl:
      enabled: true
      permanentRedirect: true
```

### Configure cert-manager

First, install cert-manager using kubectl with cert-manager’s release file:

```sh
mkdir -p cert-manager/{deployments,secrets,clusterissuers}
curl -L -o cert-manager/deployments/cert-manager.yaml https://github.com/cert-manager/cert-manager/releases/download/v1.9.1/cert-manager.yaml
kubectl apply -f cert-manager/deployments/cert-manager.yaml
```

This will create the `cert-manager` namespace and deploy the resources.

Now create a secret containing the AWS secret key
for cert-manager to use to make Route53 changes for DNS challenges.

```yaml
kind: Secret
apiVersion: v1
type: Opaque
metadata:
  name: cert-manager-aws-secret
  # Must be in same namespace as Cert Manager deployment
  namespace: cert-manager
stringData:
  access-key-id: xxx
  secret-access-key: yyy
```

Treat this like a normal secret, using `sopsandstrip` to en/de-crypt,
storing the encrypted version under `cert-manager/secrets/aws-route53-credential.yml`.
Apply with:

```sh
sopsandstrip --decrypt /psyops/kubernasty/cert-manager/secrets/aws-route53-credential.yml | kubectl apply -f -
```

Create the cert issuer as `cert-manager/clusterisssuers/route53.yml`, and then apply with kubectl:

```yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-issuer
spec:
  acme:
    # Use this email for let's encrypt
    email: psyops@micahrl.com
    # Production - make sure this works in staging before using this!
    # server: https://acme-v02.api.letsencrypt.org/directory
    # Staging:
    server: https://acme-staging-v02.api.letsencrypt.org/directory
    privateKeySecretRef:
      name: letsencrypt-issuer-account-key
    solvers:
      # The _selector_ defines the zones to use this solver for
      # If you only have one solver, then you can use an empty object for a selector like 'selector: {}'.
      # Defining the selector means you can use different solvers for different domains.
      - selector:
          dnsZones:
            # All records inside any zone listed here will use the subsequent solver to obtain certificates
            - home.micahrl.com
        dns01:
          route53:
            # Pick the correct region for your environment
            region: us-east-2
            # AWS Zone ID that matches your zone entered above
            hostedZoneID: Z32HSYI0AGMFV9
            # Reference the secret with the route53 key in it
            accessKeyIDSecretRef:
              name: aws-route53-credential
              key: access-key-id
            secretAccessKeySecretRef:
              name: prod-route53-credentials-secret
              key: secret-access-key
```

---

This far has been done. Not tested.

Following this guide:
<https://www.digitalocean.com/community/tutorials/how-to-secure-your-site-in-kubernetes-with-cert-manager-traefik-and-let-s-encrypt>

Supposedly at thsi point it is not requesting any certs yet.
Need to configure Traefik to use this.
I think I need a different guide for that, because the DO community guide will have me install Traefik next,
but k3s comes with Traefik as the default load balancer, so I just need to learn to configure it.

---

Redirect to https:

```yml
apiVersion: traefik.containo.us/v1alpha1
kind: Middleware
metadata:
  name: redirect-https
spec:
  redirectScheme:
    scheme: https
    permanent: true
```