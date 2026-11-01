# Move monitoring to SSD

Destination: `seedbox-bootdisk-fast-single` (`/dev/sde`, not NVMe).
Copy Grafana's 10 GiB PVC; start Prometheus/OpenSearch empty on 50 GiB PVCs.
OpenSearch's saved objects and security index also reset.
Retain the old HDD volumes for rollback.

**Complete step 1 before pushing these manifests.**
Use admin `kubectl` and `flux`, from the repo root, in the same shell.
Stop on errors. Expect monitoring downtime and possible lost buffered logs.
Do not combine this migration with chart upgrades.
Do not rely on Flux to undo temporary patches or automatically resume after a failure.

## 1. Pause automation and protect the old volumes

Confirm all three HelmReleases are Ready with no upgrade in progress.
Suspend backups, then wait for every active backup job to finish:

```sh
set -eu
umask 077
recovery_dir="$PWD/tmp/seedbox-ssd-recovery-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$recovery_dir"
prometheus_pvc=prometheus-kube-prometheus-stack-prometheus-db-prometheus-kube-prometheus-stack-prometheus-0
opensearch_pvc=opensearch-cluster-master-opensearch-cluster-master-0

kubectl -n prometheus get helmrelease kube-prometheus-stack
kubectl -n opensearch get helmrelease opensearch opensearch-dashboards
backup_was_suspended="$(kubectl -n restic-backup get cronjob restic-backup -o jsonpath='{.spec.suspend}')"
printf 'prometheus_pvc=%s\nopensearch_pvc=%s\nbackup_was_suspended=%s\n' "$prometheus_pvc" "$opensearch_pvc" "$backup_was_suspended" > "$recovery_dir/state.env"
kubectl -n restic-backup get cronjob restic-backup -o json > "$recovery_dir/backup-cronjob.json"
kubectl -n restic-backup patch cronjob restic-backup --type=merge -p '{"spec":{"suspend":true}}'
kubectl get jobs -A -l app.kubernetes.io/name=kvrb
```

Once backups are idle, record the starting state before any further patches.
These files capture suspension flags, replicas, Prometheus pause/storage settings,
and Helm configuration; they are references, not manifests to blindly reapply.
This procedure assumes the following resources are unsuspended/unpaused,
with the five affected workloads each at one replica. Stop and adapt if not.

```sh
kubectl -n flux-system get kustomization prometheus opensearch -o json > "$recovery_dir/kustomizations.json"
kubectl -n prometheus get helmrelease kube-prometheus-stack -o json > "$recovery_dir/monitoring-helmrelease.json"
kubectl -n opensearch get helmrelease opensearch opensearch-dashboards -o json > "$recovery_dir/opensearch-helmreleases.json"
kubectl -n prometheus get deployment/kube-prometheus-stack-operator deployment/kube-prometheus-stack-grafana statefulset/prometheus-kube-prometheus-stack-prometheus -o json > "$recovery_dir/monitoring-workloads.json"
kubectl -n opensearch get deployment/opensearch-dashboards statefulset/opensearch-cluster-master -o json > "$recovery_dir/opensearch-workloads.json"
kubectl -n prometheus get prometheus kube-prometheus-stack-prometheus -o json > "$recovery_dir/prometheus-cr.json"
kubectl -n prometheus get configmap kube-prometheus-stack-values -o yaml > "$recovery_dir/monitoring-values.yaml"
kubectl -n opensearch get configmap opensearch-values -o yaml > "$recovery_dir/opensearch-values.yaml"

for name in prometheus opensearch; do
    flux suspend kustomization "$name" -n flux-system
done
flux suspend helmrelease kube-prometheus-stack -n prometheus
flux suspend helmrelease opensearch -n opensearch
flux suspend helmrelease opensearch-dashboards -n opensearch

old_grafana_pv="$(kubectl -n prometheus get pvc kube-prometheus-stack-grafana -o jsonpath='{.spec.volumeName}')"
old_prometheus_pv="$(kubectl -n prometheus get pvc "$prometheus_pvc" -o jsonpath='{.spec.volumeName}')"
old_opensearch_pv="$(kubectl -n opensearch get pvc "$opensearch_pvc" -o jsonpath='{.spec.volumeName}')"
test -n "$old_grafana_pv"
test -n "$old_prometheus_pv"
test -n "$old_opensearch_pv"
printf 'old_grafana_pv=%s\nold_prometheus_pv=%s\nold_opensearch_pv=%s\n' "$old_grafana_pv" "$old_prometheus_pv" "$old_opensearch_pv" >> "$recovery_dir/state.env"
kubectl -n prometheus get pvc kube-prometheus-stack-grafana "$prometheus_pvc" -o yaml > "$recovery_dir/prometheus-pvcs.yaml"
kubectl -n opensearch get pvc "$opensearch_pvc" -o yaml > "$recovery_dir/opensearch-pvc.yaml"
kubectl get pv "$old_grafana_pv" "$old_prometheus_pv" "$old_opensearch_pv" -o yaml > "$recovery_dir/old-pvs.yaml"

for pv in "$old_grafana_pv" "$old_prometheus_pv" "$old_opensearch_pv"; do
    kubectl patch pv "$pv" --type=merge -p '{"spec":{"persistentVolumeReclaimPolicy":"Retain"}}'
    test "$(kubectl get pv "$pv" -o jsonpath='{.spec.persistentVolumeReclaimPolicy}')" = Retain
done
printf 'Recovery metadata: %s\n' "$recovery_dir"
```

## 2. Stop consumers and copy Grafana

Pause Prometheus itself so its operator cannot restart it during migration:

```sh
kubectl -n prometheus patch prometheus kube-prometheus-stack-prometheus --type=merge -p '{"spec":{"paused":true}}'
kubectl -n prometheus scale deployment/kube-prometheus-stack-operator deployment/kube-prometheus-stack-grafana statefulset/prometheus-kube-prometheus-stack-prometheus --replicas=0
kubectl -n opensearch scale deployment/opensearch-dashboards statefulset/opensearch-cluster-master --replicas=0
kubectl -n prometheus wait --for=delete pod -l app.kubernetes.io/name=grafana --timeout=10m
kubectl -n prometheus wait --for=delete pod/prometheus-kube-prometheus-stack-prometheus-0 --timeout=10m
kubectl -n opensearch wait --for=delete pod/opensearch-cluster-master-0 --timeout=10m
kubectl -n prometheus get pods
kubectl -n opensearch get pods
```

Confirm consumers are stopped, then copy the complete Grafana volume:

```sh
kubectl apply -f seedboxk8s/applications/prometheus/PVC.grafana-fast.yaml
kubectl apply -f seedboxk8s/docs/monitoring-ssd-migration/Job.grafana-ssd-copy.yaml
kubectl -n prometheus wait --for=condition=complete job/grafana-ssd-copy --timeout=30m
kubectl -n prometheus logs job/grafana-ssd-copy
kubectl -n prometheus get pvc kube-prometheus-stack-grafana-fast
```

**Proceed only after a successful copy and a Bound SSD target.**
On failure, keep the source untouched and automation paused;
a partial target must be investigated before retrying.
Remove the successful copy job before resuming workloads:

```sh
kubectl -n prometheus delete job grafana-ssd-copy
kubectl -n prometheus wait --for=delete pod -l job-name=grafana-ssd-copy --timeout=10m
```

## 3. Replace Prometheus/OpenSearch claims

These commands delete claim objects, not their retained backing volumes.
Leave Grafana's old claim alone; Helm handles it when switching to `existingClaim`.

```sh
for pv in "$old_grafana_pv" "$old_prometheus_pv" "$old_opensearch_pv"; do
    test "$(kubectl get pv "$pv" -o jsonpath='{.spec.persistentVolumeReclaimPolicy}')" = Retain
done
kubectl -n prometheus delete statefulset prometheus-kube-prometheus-stack-prometheus --cascade=orphan
kubectl -n opensearch delete statefulset opensearch-cluster-master --cascade=orphan
kubectl -n prometheus delete pvc "$prometheus_pvc" --timeout=10m
kubectl -n opensearch delete pvc "$opensearch_pvc" --timeout=10m
kubectl apply -f seedboxk8s/applications/prometheus/PVC.prometheus.yaml
kubectl apply -f seedboxk8s/applications/opensearch/PVC.opensearch.yaml
```

New claims may remain Pending until their first consumer starts.
Their manifests live in the application directories and will be managed by Flux
once reconciliation resumes.

## 4. Push, reconcile values, then restart

Commit/push the migration now. Resume Kustomizations while Helm remains suspended:

```sh
for name in prometheus opensearch; do
    flux resume kustomization "$name" -n flux-system
    flux reconcile kustomization "$name" -n flux-system --with-source
done
kubectl -n prometheus get configmap kube-prometheus-stack-values -o jsonpath='{.data.values\.yaml}'
kubectl -n opensearch get configmap opensearch-values -o jsonpath='{.data.values\.yaml}'
```

**Check live values use the SSD class and Grafana's new claim.**
Confirm all three HelmReleases are still suspended before proceeding:

```sh
kubectl -n prometheus get helmrelease kube-prometheus-stack -o jsonpath='{.spec.suspend}{"\n"}'
kubectl -n opensearch get helmrelease opensearch -o jsonpath='{.spec.suspend}{"\n"}'
kubectl -n opensearch get helmrelease opensearch-dashboards -o jsonpath='{.spec.suspend}{"\n"}'
test "$(kubectl -n prometheus get prometheus kube-prometheus-stack-prometheus -o jsonpath='{.spec.paused}')" = true
kubectl -n prometheus scale deployment kube-prometheus-stack-operator --replicas=1
flux resume helmrelease kube-prometheus-stack -n prometheus
flux reconcile helmrelease kube-prometheus-stack -n prometheus
kubectl -n prometheus scale deployment kube-prometheus-stack-grafana --replicas=1
kubectl -n prometheus rollout status deployment/kube-prometheus-stack-grafana --timeout=10m
kubectl -n prometheus rollout status statefulset/prometheus-kube-prometheus-stack-prometheus --timeout=10m
flux resume helmrelease opensearch -n opensearch
flux reconcile helmrelease opensearch -n opensearch
kubectl -n opensearch rollout status statefulset/opensearch-cluster-master --timeout=10m
```

Check OpenSearch API health before starting Dashboards:
no unassigned primary shards (yellow from unassigned replicas is acceptable).
Investigate security-init failures rather than blindly reapplying security configuration.

```sh
flux resume helmrelease opensearch-dashboards -n opensearch
flux reconcile helmrelease opensearch-dashboards -n opensearch
kubectl -n opensearch scale deployment opensearch-dashboards --replicas=1
kubectl -n opensearch rollout status deployment/opensearch-dashboards --timeout=10m
kubectl -n prometheus get pvc
kubectl -n opensearch get pvc
kubectl get pv "$old_grafana_pv" "$old_prometheus_pv" "$old_opensearch_pv"
```

## 5. Verify and resume backups

Verify SSD bindings, Grafana settings/login/probes, Prometheus targets,
OpenSearch health, Fluent Bit ingestion, and Dashboards login/search.
Then restore scheduled backups and confirm a successful backup of Grafana's new claim:

```sh
if test "$backup_was_suspended" != true; then
    kubectl -n restic-backup patch cronjob restic-backup --type=merge -p '{"spec":{"suspend":false}}'
fi
```

### Cleanup checkpoint

Do not declare success until all of these are checked against the starting-state files:

- [ ] Both Kustomizations and all three HelmReleases are unsuspended and Ready.
- [ ] Prometheus is unpaused, with SSD storage in its spec.
- [ ] All five affected workloads are back at one desired/ready replica.
- [ ] The backup CronJob matches its original suspension state.
- [ ] The copy Job and its pods are gone.
- [ ] All three destination PVCs are Bound on the SSD class.
- [ ] Grafana's new PVC has completed a successful restic backup.

Inspect the temporary settings explicitly; Ready alone does not prove they were reset:

```sh
kubectl -n flux-system get kustomization prometheus opensearch -o 'custom-columns=NAME:.metadata.name,SUSPENDED:.spec.suspend'
kubectl -n prometheus get helmrelease kube-prometheus-stack -o 'custom-columns=NAME:.metadata.name,SUSPENDED:.spec.suspend'
kubectl -n opensearch get helmrelease opensearch opensearch-dashboards -o 'custom-columns=NAME:.metadata.name,SUSPENDED:.spec.suspend'
kubectl -n prometheus get prometheus kube-prometheus-stack-prometheus -o 'custom-columns=NAME:.metadata.name,PAUSED:.spec.paused,CLASS:.spec.storage.volumeClaimTemplate.spec.storageClassName'
kubectl -n prometheus get deployments,statefulsets,helmreleases,pvc
kubectl -n opensearch get deployments,statefulsets,helmreleases,pvc
kubectl -n restic-backup get cronjob restic-backup
kubectl -n prometheus get job grafana-ssd-copy --ignore-not-found
kubectl -n prometheus get pods -l job-name=grafana-ssd-copy
```

### Intentional leftovers

- Old HDD PVs remain `Retain`; Flux will not reset that policy or free their LVs.
- Grafana's original PVC may remain if Helm kept it. Inspect before removing it.
- The new SSD PVCs and Grafana backup annotations are permanent, not cleanup targets.
- Keep `$recovery_dir` until rollback is no longer needed.

**Delete old PVs/LVs only as a separate, deliberate cleanup after verification.**
Retained volumes are not independent backups.

## If interrupted

Keep automation paused until the selected data/claims and Git values agree.
Do not use an unconditional exit trap to resume controllers.
If the shell was lost, recover the variables without re-running step 1:

```sh
set -eu
recovery_dir=/absolute/path/to/the/existing/seedbox-ssd-recovery-directory
. "$recovery_dir/state.env"
```

Use the saved JSON/YAML to identify the starting state and inspect live resources
before continuing at the failed checkpoint. Restore suspension flags, replicas,
and Prometheus's pause state explicitly only when it is safe to restart.
Flux may overwrite some patches later, but cleanup is not guaranteed.

Rollback requires stopping consumers, reverting storage values, and explicitly rebinding
old PVs. Released PVs retain stale claim UIDs: only clear `spec.claimRef` after confirming
no consumers, and select the old PV with `spec.volumeName` and its original class.
Do not blindly apply exported YAML with stale metadata.
Before Helm switches claims, Grafana's original claim remains directly usable.
Afterward, restoring the old copy discards subsequent SSD changes.
