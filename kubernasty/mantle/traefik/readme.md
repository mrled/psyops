# Traefik notes

Run two Traefik instances:

* One for Tailscale
* One for local networking

The Tailscale pod sets `TS_DEST_IP` to the Service resource of the Traefik instance dedicated to it.
That Traefik instance is only acceessible over Tailscale,
and it's created as a Deployment to run anywhere in the cluster.
(Currently this cluster is just a single node, so there's only one node it will be running on.)

The local networking Traefik instance is run as a DaemonSet.
Currently it's only used for non-HTTP stuff, like Transmission torrent peer ports --
basically port forwarding to the relevant in-cluster service.
It lets the cluster run a service that requires some HTTP port exposed anywhere it wants
(again, right now this is just a single node, so there's only one node to run on)
and the local network can connect to it however it likes.

This does have some DNS implications:

* For HTTP services, we use a cluster FQDN that resolves to a Tailscale IP address
* For local networking non-HTTP services, we use the node's LAN hostname;
  if we expand to more nodes in the future,
  we would need to add a load balancer like kube-vip or MetalLB and point a hostname to that.

## Dashboards

* Both enable the dashboard by passing `--api.dashboard=true`.
* `traefik-tailscale` uses an IngressRoute to `api@internal`,
  <https://traefik-tailscale.example.com>.
* `traefik-localnet` uses a Service and an IngressRoute that points to that Service,
  <https://traefik-localnet.example.com>.

This way, the dashboard for BOTH instances are only available via `traefik-tailscale` ingress,
and therefore require VPN access.