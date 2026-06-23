# Restore PVCs

Use `restore-pvc.sh` to restore a single restic repository into a fresh test PVC
without touching the live PVC.

Example:

```sh
./docs/restore-pvc.sh -n tortuga -s heimdall-config-pvc
```

That creates:

- a target PVC named `heimdall-config-pvc-restore-test`
- a restore Job in the source namespace
- a copied restore Secret in the source namespace
- labels on the restore Job, its pod, the restore Secret, and the target PVC for cleanup

You can also choose the target PVC name:

```sh
./docs/restore-pvc.sh \
  -n tortuga \
  -s heimdall-config-pvc \
  -t heimdall-restore-test-pvc
```

By default, the script reads the source PVC's storage class and size, and reads
`RESTIC_REPOSITORY_BASE` from the `restic-backup/restic-backup-config`
ConfigMap. Override those when needed:

```sh
./docs/restore-pvc.sh \
  -n tortuga \
  -s heimdall-config-pvc \
  -t heimdall-restore-test-pvc \
  -S 1Gi \
  -c seedbox-slow-mirror \
  -r s3:https://s3.us-central-1.wasabisys.com/micahrl-seedboxk8s-krvb/restic
```

Watch the restore:

```sh
kubectl -n tortuga logs -f job/restic-restore-heimdall-restore-test-pvc
```

Inspect the restored PVC using the command printed by the script. It will look
like this:

```sh
kubectl -n tortuga run heimdall-restore-test-pvc-shell --rm -it --restart=Never \
  --image=alpine:3.22 \
  --overrides='{"spec":{"containers":[{"name":"heimdall-restore-test-pvc-shell","image":"alpine:3.22","stdin":true,"tty":true,"command":["/bin/sh"],"volumeMounts":[{"name":"target","mountPath":"/target"}]}],"volumes":[{"name":"target","persistentVolumeClaim":{"claimName":"heimdall-restore-test-pvc"}}]}}'
```

Clean up restore test resources with the label printed by the script:

```sh
kubectl -n tortuga delete job,pod,pvc,secret -l kvrb.seedboxk8s.micahrl.com/restore-test=heimdall-config-pvc
```

## Restore Details

Backups are created from a backup Job that mounts the source PVC at `/source`,
so `restic restore --target /restore` recreates files under `/restore/source`.
The restore script copies `/restore/source/.` into the mounted target PVC root.

Kubernetes restore Jobs may not be allowed to set SELinux extended attributes
from the snapshot, so the restore script uses:

```sh
restic restore latest --target /restore --exclude-xattr security.*
```

Without that option, restic can restore files under `/restore/source` but exit
nonzero before the copy into the target PVC runs.
