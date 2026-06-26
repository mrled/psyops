# Restic Backup application

Back up opted-in PVCs with restic.

We have a `kvrb` (Kubernetes Volume Restic Backup) Python package that runs as a CronJob.
It finds annotated PVCs, pauses workloads that use them, runs a temporary backup
Job in the PVC namespace, and restores the workloads afterward.

PVCs opt in with this annotation:

```yaml
backup.seedboxk8s.micahrl.com/enabled: "true"
```

A few useful commands:

```sh
# Find all PVCs where the backup is enabled
kubectl get pvc -A -o jsonpath='{range .items[?(@.metadata.annotations.backup\.seedboxk8s\.micahrl\.com/enabled=="true")]}{.metadata.namespace}{"/"}{.metadata.name}{"\n"}{end}'

# Find all PVCs where the backup is disabled
kubectl get pvc -A -o json | jq -r '.items[] | select(.metadata.annotations["backup.seedboxk8s.micahrl.com/enabled"] != "true") | "\(.metadata.namespace)/\(.metadata.name)"'

# Find all backup jobs
kubectl get jobs -A -l app.kubernetes.io/name=kvrb

# You can find just the controller or just the backup jobs with:
kubectl get jobs -A -l app.kubernetes.io/name=kvrb,app.kubernetes.io/component=controller
kubectl get jobs -A -l app.kubernetes.io/name=kvrb,app.kubernetes.io/component=volume-backup

# Delete all controller and child jobs, and stop their pods
kubectl delete jobs -A -l app.kubernetes.io/name=kvrb

# Run a manual backup
# Works whether the CronJob is enabled or suspended.
job_name=restic-backup-manual-$(date +%Y%m%d%H%M%S)
kubectl -n restic-backup create job "$job_name" --from=cronjob/restic-backup

# Read logs from the controller.
# The controller prints logs from each per-PVC restic Job before deleting it,
# so it includes child Jobs' restic output too.
kubectl -n restic-backup logs -l app.kubernetes.io/name=kvrb,app.kubernetes.io/component=controller
```

## Parallel Backups

Set `BACKUP_PARALLELISM` in the `restic-backup-config` ConfigMap to control how many PVC backup Jobs can run at once.

## Exclusions

Exclude paths with an annotation on the PVC.
Prefix the path with `/source`, which is where it is mounted in the backup pod.

```yaml
backup.seedboxk8s.micahrl.com/exclude: |
  /source/logs
  /source/MediaCover
```

## Retention

The default retention policy is 14 daily snapshots, 8 weekly snapshots, 120
monthly snapshots, and 5 yearly snapshots. Override it per PVC with
annotations:

```yaml
backup.seedboxk8s.micahrl.com/keep-daily: "14"
backup.seedboxk8s.micahrl.com/keep-weekly: "8"
backup.seedboxk8s.micahrl.com/keep-monthly: "120"
backup.seedboxk8s.micahrl.com/keep-yearly: "5"
```

Values must be non-negative integers. The controller renders them into the
child Job's `restic forget --prune` command.

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

If the controller died and left a stale lock, inspect and delete the Lease:

```sh
kubectl -n restic-backup get lease restic-backup -o yaml
kubectl -n restic-backup delete lease restic-backup
```
