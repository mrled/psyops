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

Interact with it:

```sh
# Watch the restore
kubectl -n tortuga logs -f job/restic-restore-heimdall-restore-test-pvc

# Start a container to inspect the restored PVC
kubectl -n tortuga run heimdall-restore-test-pvc-shell --rm -it --restart=Never \
  --image=alpine:3.22 \
  --labels=app.kubernetes.io/name=kvrb,app.kubernetes.io/component=restore-test,kvrb.seedboxk8s.micahrl.com/restore-test=heimdall-config-pvc \
  --overrides='{"spec":{"containers":[{"name":"heimdall-restore-test-pvc-shell","image":"alpine:3.22","stdin":true,"tty":true,"command":["/bin/sh"],"volumeMounts":[{"name":"target","mountPath":"/target"}]}],"volumes":[{"name":"target","persistentVolumeClaim":{"claimName":"heimdall-restore-test-pvc"}}]}}'

# Clean up restore test resources whehn finished.
# Delete Pods and Jobs before the PVC so that the PVC's protection finalizer is released.
kubectl -n tortuga delete job,pod -l kvrb.seedboxk8s.micahrl.com/restore-test=heimdall-config-pvc --ignore-not-found
kubectl -n tortuga wait --for=delete pod -l kvrb.seedboxk8s.micahrl.com/restore-test=heimdall-config-pvc --timeout=120s
kubectl -n tortuga delete pvc,secret -l kvrb.seedboxk8s.micahrl.com/restore-test=heimdall-config-pvc --ignore-not-found

# If the PVC is stuck in Terminating, find all pods still mounting it.
kubectl -n tortuga get pod -o json | jq -r '.items[] | select(any(.spec.volumes[]?; .persistentVolumeClaim.claimName == "heimdall-restore-test-pvc")) | .metadata.name'
```
