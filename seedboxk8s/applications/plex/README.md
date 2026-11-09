# Plex logs

The `plex-logs` sidecar forwards Plex's active text log files to stdout,
including logs under `PMS Plugin Logs`.
Each JSON record contains a `plex` object with `source` and `message` fields:

```json
{"plex":{"source":"/plex-logs/Plex Media Server.log","message":"Nov 08, 2026 ..."}}
```

The existing cluster Fluent Bit collector parses this JSON specifically for
container `plex-logs`, preserving Kubernetes metadata.
OpenSearch can therefore filter on `plex.source` and search `plex.message`;
other containers' log parsing is unchanged.
Plex's original timestamps remain in `plex.message`.
The event timestamp is still the time the sidecar forwards the line,
not a parsed Plex timestamp.

```bash
# Recent file-log output from all Plex components.
kubectl -n tortuga logs plex-0 -c plex-logs --since=30m

# Follow new records.
kubectl -n tortuga logs -f plex-0 -c plex-logs --tail=100

# Select records by source filename or content.
kubectl -n tortuga logs plex-0 -c plex-logs --since=30m |
  grep -Ei 'Transcode|ERROR|WARN|VAAPI|memory'

# Plex's original container stdout remains separate.
kubectl -n tortuga logs plex-0 -c pms --previous
```

## Behavior and retention

- Existing active `.log` files are read from the beginning on first startup.
  Their historical lines get current container-log timestamps;
  use the timestamps inside the original messages when investigating an incident.
- Newly created log files are discovered every five seconds.
  Renamed files continue to be drained during the rotation grace period.
- Numbered rotations are not separately imported,
  to avoid duplicating lines already forwarded from active files.
  Older rotations predating this deployment still require direct file retrieval.
- Offsets are stored in an `emptyDir` database,
  so restarting the sidecar resumes reading rather than replaying everything.
  Replacing the entire pod resets offsets and replays the active files.
- The sidecar remains running when only the `pms` container crashes or OOMs.
- Kubernetes rotates stdout logs too; `kubectl logs` is not a complete archive.
  Use the cluster's centralized logging for longer retention.
- Lines larger than 1 MiB are skipped to keep forwarding bounded.

The sidecar runs unprivileged as Plex's UID/GID,
with a read-only mount of just the log directory and its own memory limit.
It cannot access the media or other Plex configuration files through that mount.

Plex logs may contain tokens, usernames, client addresses, and media paths.
Forwarding makes these visible to pod-log readers and centralized-log readers;
redact them before sharing outside trusted systems.

## Intel GPU access and tone mapping

The Intel device plugin grants runtime device access.
It uses `-bypath=all` to preserve PCI-path symlinks,
so `/dev/dri/by-path/pci-0000:00:02.0-render` resolves to `/dev/dri/renderD128`.

The plugin's default `single` mode instead mounts each by-path entry separately,
creating a device node that retains host ownership.
On `tagasaw`, the direct render node had GID `0`,
but the separately mounted by-path node had GID `992`.
Plex could use VA-API through the direct node,
while Intel OpenCL received `EACCES` opening the by-path node
and reported `CL_PLATFORM_NOT_FOUND_KHR` (`-1001`).
Preserving symlinks avoids that ownership mismatch.
Plex still needs membership in the allocated devices' groups.

The image's `45-plex-hw-transcode-and-connected-tuner` startup hook
uses `find -type c`, which returned no devices in the observed pod,
even though `stat` and `ls` identified the paths as character devices.
The `plex-gpu-permissions` ConfigMap adds `46-plex-gpu-groups`,
which enumerates direct DRM paths with shell globs and explicitly checks `test -c`.
It reads each device's GID, creates a group if needed,
and adds `plex` to it without changing host device permissions.
This runs before `s6-setuidgid` rebuilds Plex's supplementary groups
from the container's group database;
pod-level `supplementalGroups` alone would not survive that step.

After the plugin rolls out, recreate the Plex pod to receive the new mounts;
restarting only its container is not sufficient to obtain a new allocation.
See `../intel-gpu-plugin/README.md` for rollout and access checks.
After the Plex rollout, check startup-hook output and group membership:

```bash
kubectl -n tortuga logs plex-0 -c pms | grep -E '46-plex-gpu-groups|Granted Plex access'
kubectl -n tortuga exec plex-0 -c pms -- s6-setuidgid plex id
```

On the observed host, the render device has GID `992`;
that group should appear in the `s6-setuidgid` output.
Then test an HDR-to-SDR video conversion without subtitle burn-in.
The transcoder should use `tonemap_opencl` without an OpenCL initialization error
or a fallback to software encoding.
This permission fix does not establish a fix for PGS burn-in memory exhaustion.
