# Restic Backup application

Back up opted-in PVCs with restic.

We have a `kvrb` (Kubernetes Volume Restic Backup) Python package that runs as a CronJob.
It finds annotated PVCs, pauses workloads that use them, runs a temporary backup
Job in the PVC namespace, and restores the workloads afterward.

PVCs opt in with this annotation:

```yaml
backup.seedboxk8s.micahrl.com/enabled: "true"
```

The `restic-backup-config` ConfigMap must set:

- `AWS_DEFAULT_REGION`: S3-compatible bucket region.
- `RESTIC_REPOSITORY_BASE`: base repository URL, such as `s3:.../restic`.

The `restic-backup-env` secret must set:

- `AWS_ACCESS_KEY_ID`: S3-compatible access key.
- `AWS_SECRET_ACCESS_KEY`: S3-compatible secret key.
- `RESTIC_PASSWORD`: restic repository encryption password.

## Locking

The controller uses a `coordination.k8s.io/v1` Lease named `restic-backup` in
the `restic-backup` namespace. This prevents overlapping scheduled or manual
controller Jobs from backing up the same PVCs at the same time.

If a backup is stuck, stop the controller Job and any child restic Jobs:

```sh
kubectl -n restic-backup delete job -l job-name=<controller-job-name>
kubectl -n <pvc-namespace> delete job -l job-name=<restic-job-name>
```

Or delete them by name:

```sh
kubectl -n restic-backup delete job <controller-job-name>
kubectl -n <pvc-namespace> delete job <restic-job-name>
```

If the controller died and left a stale lock, inspect and delete the Lease:

```sh
kubectl -n restic-backup get lease restic-backup -o yaml
kubectl -n restic-backup delete lease restic-backup
```
