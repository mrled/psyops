"""Service preparations

Modules for configuring services via API,
such as AWS, a Kubernetes cluster, DNS, etc.

Node-specific configuration belongs in the nodes package;
svcpreps are for configuration that doesn't apply to a single node.

In particular, you might use progfiguration nodes to configure individual hosts and create a compute cluster,
then use progfiguration svcpreps to call the compute cluster APIs.

TODO: it seems like there ought to be a better name for this, but I'm not sure what it would be.
"""