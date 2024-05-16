# An internal cluster registry

TODO: this works fine in cluster, but the cluster can't pull images from it,
because the cluster can't talk to the internal cluster services.

To fix we have to expose externally via Ingress or IngressRoute components,
and if we're doing that,
I guess we might as well get real HTTPS certs?
