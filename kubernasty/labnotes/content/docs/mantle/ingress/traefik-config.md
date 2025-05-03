---
title: Traefik configuration
weight: 60
---

Manifests: {{< repolink "kubernasty/manifests/crust/traefik" >}}

We'll enable the Traefik dashboard and configure some middlewares.

Now that we have ingress and certificates configured,
we can enable the Traefik dashboard.

## How to access the dashboard

Flux will have deployed the required ingresses, certificiates, secrets, and service
to enable access the dashboard already.
Go to <https://traefik.traefik.micahrl.me/dashboard/>.

**Note that the `/dashboard/` is required, with the trailing slash.**
Without it, the server will return a 404.

You can also test it with `curl`:

```txt
> curl https://traefik.traefik.micahrl.me/dashboard/
401 Unauthorized
> curl https://username:password@traefik.traefik.micahrl.me/dashboard/
<!DOCTYPE html><html><head><title>Traefik</title>... etc
```

### Aside: Kubernetes native `Ingress` vs proprietary Traefik `IngressRoute`

We could have used a Traefik-specific `IngressRoute` resource to access the dashboard.
However, those don't play well with Cert Manager or the way we've chosen to generate HTTPS certificates.
And there is no way to reference `api@internal` from a native Kubernetes `Ingress` resource,
which is what many guides suggest doing with `IngressRoute`.
The `Service` resource we create is our workaround to using `Ingress` resources
with the Traefik dashboard:
{{< repolink "kubernasty/manifests/crust/traefik/services/traefik-dashboard.service.yaml" >}}

See also:

* <https://stackoverflow.com/questions/68565048/how-to-expose-traefik-v2-dashboard-in-k3d-k3s-via-configuration>
* <https://k3s.rocks/traefik-dashboard/>

## Traefik middlewares

### HTTP basic authentication

We protect most services with Keycloak and `traefik-forward-auth`.
However, it's useful to have an HTTP Basic Authentication user for some services,
because it can be configured in Traefik statically and doesn't require a working Keycloak deployment.

Create the basic authentication secret:

```sh
username=clusteradmin
password="p@ssw0rd"

cat >kubernasty/manifests/crust/traefik/secrets/clusteradmin-httpba.yaml <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: clusteradmin-httpba
  namespace: kube-system
type: kubernetes.io/basic-auth
stringData:
  username: $username
  password: $password
EOF

sops --encrypt --in-place kubernasty/manifests/crust/traefik/secrets/clusteradmin-httpba.yaml
```

And note the middleware
{{< repolink "kubernasty/manifests/crust/traefik/middlewares/clusteradmin-auth-mw.yaml" >}}
which can be used to protect any `Ingress`.

### Combining middlewares

You cannot apply more than one middleware to a given `Ingress`,
but you can create a [Chain middleware](https://doc.traefik.io/traefik/middlewares/http/chain/)
that references any number of other middlewares.

See {{< repolink "kubernasty/manifests/crust/traefik/secrets/traefik-dashboard-mw.yaml" >}},
a chain of:

* {{< repolink "kubernasty/manifests/crust/traefik/secrets/clusteradmin-auth-mw.yaml" >}},
  which we created above tohandle HTTP basic auth
* {{< repolink "kubernasty/manifests/crust/traefik/secrets/traefik-dashboard-redirect-mw.yaml" >}},
  which redirects the paths `/` and `/dashboard` (no trailing slash) to `/dashboard/` (trailing slash).
  (Traefik Dashboard requires `/dashboard/`.)

This is basically a Kubernetes-specific workaround, because
annotations only allow string values, not lists or other data types.
Setting the same annotation twice for the same resource overwrites it.

### Redirect HTTP traffic to HTTPS

As created above, accessing <http://traefik.micahrl.me/dashboard/> (with `http`, not `https`)
results in a 404 error.
This is fine, but a bit unergonomic;
it would be nice if it just redirected users to `https` automatically.

(This is less and less necessary with modern browsers,
which try HTTPS first,
so you can probably just skip this whole sub-section.)

See {{< repolink "kubernasty/manifests/crust/traefik/secrets/redirect-https-mw.yaml" >}}.
Note that this requires an `Ingress` for both HTTP and HTTPS, such as
{{< repolink "kubernasty/manifests/crust/traefik/ingresses/traefik-dashboard-http.in.yaml" >}}
and {{< repolink "kubernasty/manifests/crust/traefik/secrets/traefik-dashboard.in.yaml" >}}.
The redirect middleware is placed on the HTTP-only Ingress.

You should test this with a real web browser, not curl.
You can do `curl -L http://user:password@traefik.micahrl.me/dashboard/`,
however when it follows the redirect it will strip the `user:password@` portion of the URL,
and just give you a `401 Unauthorized` error.
A web browser will follow the redirect and then prompt you for the username/password,
so it can test both middlewares at once.
