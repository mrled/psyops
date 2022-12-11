# Storage - Longhorn

Longhorn is a distributed storage system.

Kubernetes assumes all its pods/services/etc are stateless,
but many apps you might want to run will require state.

Longhorn will consume storage from individual nodes in your cluster
and present it to containers as a regular POSIX filesystem.
It can provide fault tolerance by ensuring two or more copies of certain data exists in the pool.

## Installing

Get the manifest from upstream and save it here.
Then apply it.
This installs the Longhorn containers and other resources,
but it doesn't install any Ingress resources,
so we can't talk to the admin UI yet.
(See the latest version listed on the [Longhorm homepage](https://longhorn.io/),
and adjust the URI below accordingly.)

```sh
curl -o longhorn/longhorn.yml https://raw.githubusercontent.com/longhorn/longhorn/v1.3.2/deploy/longhorn.yaml
kubectl apply -f longhorn/longhorn.yml

# Monitor the deployment with this command, and don't proceed until all pods are READY
kubectl get pods -n longhorn-system
```

Now we can create Ingress resources to allow traffic to hit the Longhorn UI.
Note that the Longhorn manifest we downloaded previously installs all its resources into the `longhorn-system` namespace,
so the manifest we use below must reference that namespace too.
This manifest contains:

* An HTTPS certificate
* An HTTP Ingress that redirects to HTTPS
* An HTTPS Ingress protected by the HTTP Basic Auth middlware with the clusteradmin we created in the [previous step](./traefik-dashboard.md)

```sh
kubectl apply -f longhorn/ingresses/longhorn-in.yml
```

Since this creates a certificate, make sure to wait until `kubectl get certs -n longhorn-system` markes the new certificate as READY.
Once that's done, browse to the admin UI at <https://longhorn.kubernasty.micahrl.com/>,
and log in with the `clusteradmin` user.

## Configuring Longhorn

* Change the data path as appropriate
* TODO: can you set a default data path without having to change it for each node?
  On my psyopsOS nodes I want it to always be `/psyopsos-data/roles/k3s/longhorn/data`.

### Backups

TODO: configure Longhorn backups
TODO: test Longhorn restores
