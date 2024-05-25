# An internal cluster registry

In order for the cluster to pull images from this,
you really should just get a real cert from Let's Encrypt.

* You can theoretically allow unencrypted HTTP to registries,
  but each client, including builders in the cluster and all the Kubernetes node host operating systems
  will have to be configured to support this.
  Also, buildah and podman (at least) will still wait for an HTTPS timeout (30s) before trying unencrypted HTTP
  no matter what you do.
* You could create your own CA, but then all clients
  including builders in the cluster and all the Kubernetes node host OSes
  must be configured with the CA,
  and sometimes (specifics unclear) their host CA cert list must include it.
* Instead, use a real domain name and get a Let's Encrypt cert.
  Use DNS challenges as this will work even for private IP addresses.
