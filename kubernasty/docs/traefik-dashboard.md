# Traefik dashboard

Now that we have [ingress and certificates](ingress-and-certificates.md) configured,
we can enable the Traefik dashboard.

## How to enable access to the dashboard

To access this over HTTPS, we have to create a Service resource that exposes the dashboard on a specific port,
and then an Ingress resource that maps to it.
We also need to configure HTTPS encryption and authentication so that only authorized users can access the dashboard.

```sh
# Apply the manifest creating the cert and service
kubectl apply -f traefik/deployments/dashboard.yml
# Apply the manifest creating the ingress without authentication

# Watch for the certificate to get generated
kubectl logs --tail=20 -f cert-manager-<SUFFIX> -n cert-manager &
kubectl get certs -A
```

Once it's finished, you can access the dashboard at <https://traefik.kubernasty.micahrl.com/dashboard/>.
There is nothing at the root domain, and the trailing slash on `dashboard/` is important;
without it, you'll get a 404.

See also:

* <https://k3s.rocks/traefik-dashboard/>

## How to require authentication for the dashboard

Create a secret containing a username/password to use with HTTP Basic Authentication.
Copy the example in `traefik/secrets/traefik-dashboard-httpba.example.yml` to `tmp.yml`
set the username and password, and encrypt with `sops`.

```sh
cp traefik/secrets/traefik-dashboard-httpba.example.yml tmp.yml
vim tmp.yml # set the username/password ...
sops --encrypt tmp.yml > traefik/secrets/traefik-dashboard-httpba.yml
```

Apply the secret.
Create a middleware that applies HTTP Basic Authentication using the credentials you just saved in the secret.

```sh
sopsandstrip --decrypt traefik/secrets/traefik-dashboard-httpba.yml |
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
TODO: redirect HTTP traffic to HTTPS

## Aside: the easy thing that doesn't work

We can use a Traefik-specific `IngressRoute` resource to access the dashboard.
However, those don't play well with Cert Manager or the way we've chosen to generate HTTPS certificates.
And there is no way to reference `api@internal` from a native Kubernetes `Ingress` resource,
which is what many guides suggest doing.

See also:

* <https://stackoverflow.com/questions/68565048/how-to-expose-traefik-v2-dashboard-in-k3d-k3s-via-configuration>
* <https://k3s.rocks/traefik-dashboard/>
