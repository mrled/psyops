# Restic Backup application

Back up opted-in PVCs with restic.

We have a `kvrb` (Kubernetes Volume Restic Backup) Python package that runs as a CronJob.
It finds annotated PVCs, pauses workloads that use them, runs a temporary backup
Job in the PVC namespace, and restores the workloads afterward.

PVCs opt in with this annotation:

```yaml
backup.seedboxk8s.micahrl.com/enabled: "true"
```

Find all PVCs where backup is enabled:

```sh
kubectl get pvc -A -o jsonpath='{range .items[?(@.metadata.annotations.backup\.seedboxk8s\.micahrl\.com/enabled=="true")]}{.metadata.namespace}{"/"}{.metadata.name}{"\n"}{end}'
```

Find all PVCs where backup is not enabled, including PVCs with the annotation
unset or set to any value other than `"true"`:

```sh
kubectl get pvc -A -o json \
  | jq -r '.items[] | select(.metadata.annotations["backup.seedboxk8s.micahrl.com/enabled"] != "true") | "\(.metadata.namespace)/\(.metadata.name)"'
```

## Exclusions

Some application config PVCs contain caches, generated artwork, or logs that do
not need to be backed up. Exclusions should live on the PVC that opts into
backup, so the backup policy stays next to the volume it applies to.

The annotation is:

```yaml
backup.seedboxk8s.micahrl.com/exclude: |
  /source/logs
  /source/MediaCover
```

The backup Job mounts the PVC at `/source`, so exclusion paths should be written
from that mount point. For example, the old host-level seedbox backup excluded
paths like `/seedboxmedia/seedboxconf/radarr/logs`; in Kubernetes, the Radarr
config PVC is mounted at `/source`, so the equivalent exclusion is
`/source/logs`.

Examples:

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: radarr-config-pvc
  namespace: tortuga
  annotations:
    backup.seedboxk8s.micahrl.com/enabled: "true"
    backup.seedboxk8s.micahrl.com/exclude: |
      /source/logs
      /source/MediaCover
```

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: plex-config-pvc
  namespace: tortuga
  annotations:
    backup.seedboxk8s.micahrl.com/enabled: "true"
    backup.seedboxk8s.micahrl.com/exclude: |
      /source/Library/Application Support/Plex Media Server/Cache
```

The controller writes each non-empty annotation line to a restic exclude file
and passes it to the PVC's backup Job with `--exclude-file`.

The `restic-backup-config` ConfigMap must set:

- `AWS_DEFAULT_REGION`: S3-compatible bucket region.
- `RESTIC_REPOSITORY_BASE`: base repository URL, such as `s3:.../restic`.

The `restic-backup-env` secret must set:

- `AWS_ACCESS_KEY_ID`: S3-compatible access key.
- `AWS_SECRET_ACCESS_KEY`: S3-compatible secret key.
- `RESTIC_PASSWORD`: restic repository encryption password.

## Restore Testing

See [docs/restore.md](docs/restore.md) for single-PVC restore testing. The
helper script creates a fresh PVC, runs a restore Job, and prints inspection and
cleanup commands:

```sh
./docs/restore-pvc.sh -n tortuga -s heimdall-config-pvc
```

## Locking

The controller uses a `coordination.k8s.io/v1` Lease named `restic-backup` in
the `restic-backup` namespace. This prevents overlapping scheduled or manual
controller Jobs from backing up the same PVCs at the same time.

Find backup jobs:

```sh
kubectl get jobs -A -l app.kubernetes.io/name=kvrb

# You can find just the controller or just the backup jobs with:
kubectl get jobs -A -l app.kubernetes.io/name=kvrb,app.kubernetes.io/component=controller
kubectl get jobs -A -l app.kubernetes.io/name=kvrb,app.kubernetes.io/component=volume-backup
```

The controller prints logs from each per-PVC restic Job before deleting it, so
the controller Job logs include the child Job's restic output:

```sh
kubectl -n restic-backup logs -l app.kubernetes.io/name=kvrb,app.kubernetes.io/component=controller
```

If a backup is stuck, stop the controller Job and all its child restic Jobs:

```sh
kubectl delete jobs -A -l app.kubernetes.io/name=kvrb
```

If the controller died and left a stale lock, inspect and delete the Lease:

```sh
kubectl -n restic-backup get lease restic-backup -o yaml
kubectl -n restic-backup delete lease restic-backup
```
