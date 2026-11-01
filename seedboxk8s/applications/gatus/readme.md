# Gatus

Gatus runs as a single-replica Deployment in the `gatus` namespace.
It checks the Tor exit through `http://torprivoxy.tor:8118`.

History is stored in SQLite at `/data/gatus.db` on `gatus-data-pvc`,
a 4Gi `seedbox-slow-mirror` volume.
It survives pod replacement and rescheduling, but is deliberately not backed up:
the PVC has no backup opt-in annotations.
Losing or deleting the volume loses monitoring history, not check definitions.
Deployment updates use `Recreate` to avoid concurrent database access,
so monitoring briefly stops during updates.

Check definitions remain in Git in `ConfigMap.gatus.yaml`.
The read-only ConfigMap volume at `/config` supplies `config.yaml`;
it is separate from the persistent history volume.
`/tmp` uses an ephemeral `emptyDir` volume.

The dashboard at `https://gatus.${productionClusterFqdn}` is served by
`traefik-tailscale`, protected by Authelia,
and uses the wildcard TLS secret reflected into this namespace.
Homepage discovers the link from the IngressRoute annotations;
no static Homepage entry is needed.

The NetworkPolicy selects Gatus pods and permits ingress only from the
`traefik` namespace on TCP port 8080.
It does not isolate egress, so DNS and endpoint checks remain available.
Tor already permits proxy connections on port 8118 from any source.
