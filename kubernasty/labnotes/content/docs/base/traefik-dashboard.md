---
title: Traefik dashboard
weight: 30
---

Now that we have [ingress and certificates]({{< ref "ingress-and-certificates" >}}) configured,
we can enable the Traefik dashboard.

## How to enable access to the dashboard

To access this over HTTPS, we have to create a Service resource that exposes the dashboard on a specific port,
and then an Ingress resource that maps to it.
We'll configure it here to require HTTPS.
In subsequent steps we'll add authentication and an HTTP-to-HTTPS redirect.

```sh
# Apply the manifest creating the cert and service
kubectl apply -f traefik/deployments/dashboard.yml
# Apply the manifest creating the ingress without authentication
kubectl apply -f traefik/ingresses/dashboard-in-noauth.yml

# Watch for the certificate to get generated
kubectl logs --tail=20 -f cert-manager-<SUFFIX> -n cert-manager &
kubectl get certs -A
```

Once it's finished, you can access the dashboard at <https://traefik.kubernasty.micahrl.com/dashboard/>.
There is nothing at the root domain, and the trailing slash on `dashboard/` is important;
without it, you'll get a 404.

See also:

* <https://k3s.rocks/traefik-dashboard/>

### Aside: the easy thing that doesn't work

We can use a Traefik-specific `IngressRoute` resource to access the dashboard.
However, those don't play well with Cert Manager or the way we've chosen to generate HTTPS certificates.
And there is no way to reference `api@internal` from a native Kubernetes `Ingress` resource,
which is what many guides suggest doing.
The `Service` resource we create is our workaround to using `Ingress` resources with the Traefik dashboard.

See also:

* <https://stackoverflow.com/questions/68565048/how-to-expose-traefik-v2-dashboard-in-k3d-k3s-via-configuration>
* <https://k3s.rocks/traefik-dashboard/>

## How to require authentication for the dashboard

Create a secret containing a username/password to use with HTTP Basic Authentication.
We will create a user called `clusteradmin` that is allowed to log in to the Traefik dashboard
(and later will be allowed to perform other cluster administrative tasks as well).
Copy the example in
{{< repolink "kubernasty/traefik/secrets/clusteradmin-httpba.example.yml" >}}
to `tmp.yml`, set the username and password, and encrypt with `sops`.

```sh
cp traefik/secrets/clusteradmin-httpba.example.yml tmp.yml
vim tmp.yml # set the username/password ...
sops --encrypt tmp.yml > traefik/secrets/clusteradmin-httpba.yml
```

Apply the secret.
Create a middleware that applies HTTP Basic Authentication using the credentials you just saved in the secret.

```sh
sopsandstrip --decrypt traefik/secrets/clusteradmin-httpba.yml |
    kubectl apply -f -
kubectl apply -f traefik/middlewares/traefik-dashboard-auth-mw.yml
```

Now add the new middleware to the dashboard Ingress object we created earlier.
This is a different manifest file (so that you can compare it with the old one),
but it contains the entire old file plus a new annotation that references the middleware.
Critically, it contains an ingress with the same name as the one we created previously,
so differences will just be applied to the already-created ingress resource.
To be clear, we didn't actually have to do this in two steps,
but doing it this way proves that the dashboard is working before attempting to add authentication to it,
and also helps explain it better.

```sh
kubectl apply -f traefik/ingresses/dashboard-in-auth.yml
```

You can test this in the browser by visiting <https://traefik.kubernasty.micahrl.com/dashboard/>.
You can also test it with `curl`:

```txt
> curl https://traefik.kubernasty.micahrl.com/dashboard/
401 Unauthorized
> curl https://username:password@traefik.kubernasty.micahrl.com/dashboard/
<!DOCTYPE html><html><head><title>Traefik</title>... etc
```

See also:

* <https://k3s.rocks/basic-auth/>
* <https://stackoverflow.com/questions/50130797/kubernetes-basic-authentication-with-traefik>

## Redirect HTTP traffic to HTTPS

As created above, accessing <http://traefik.kubernasty.micahrl.com/dashboard/> (with `http`, not `https`)
results in a 404 error.
This is fine, but a bit unergonomic;
it would be nice if it just redirected users to `https` automatically.

First we have to create a middleware that does HTTP-to-HTTPS redirects.

```sh
kubectl apply -f traefik/middlewares/redirect-https-mw.yml
```

To redirect from HTTP to HTTPS, we actually need a separate `Ingress` resource for each scheme.
The HTTPS `Ingress` resource, which we've already annotated with authorization middleware, will not change here.
Instead, we'll add a new HTTP `Ingress` resource which we'll annotated with the HTTP-to-HTTPS redirect middleware.
To be clear, this is a _new_ resource, not an update of the one we created above.

```sh
kubectl apply -f traefik/ingresses/dashboard-in-http.yml
```

You should test this with a real web browser, not curl.
You can do `curl -L http://user:password@traefik.kubernasty.micahrl.com/dashboard/`,
however when it follows the redirect it will strip the `user:password@` portion of the URL,
and just give you a `401 Unauthorized` error.
A web browser will follow the redirect and then prompt you for the username/password,
so it can test both middlewares at once.

Note: here, we only have one middleware applying to each Ingress resource.
In fact, we _can't_ apply more than one middleware via Kubernetes annotations.
Annotations only allow string values; no lists or other data types.
And setting the same annotation twice for the same resource overwrites it.
Instead, we have to make a _third_ middleware that "chains" together multiple other middlewares,
and call that one instead.
See the [Traefik docs on chaining middlewares](https://doc.traefik.io/traefik/middlewares/http/chain/)
for an example (make sure to select the "Kubernetes" tab for the example).
