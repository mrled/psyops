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
