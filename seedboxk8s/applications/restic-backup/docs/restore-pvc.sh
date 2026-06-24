#!/bin/sh
set -eu

usage() {
    cat <<'EOF'
Usage:
  restore-pvc.sh -n NAMESPACE -s SOURCE_PVC [-t TARGET_PVC] [-S SIZE] [-c STORAGE_CLASS] [-r RESTIC_REPOSITORY_BASE]

Restore the latest restic backup for SOURCE_PVC into a fresh test PVC.

Required:
  -n NAMESPACE       Namespace containing the source and target PVCs.
  -s SOURCE_PVC      PVC name used by the backup repository.

Optional:
  -t TARGET_PVC      Restore target PVC name. Defaults to SOURCE_PVC-restore-test.
  -S SIZE            Target PVC size. Defaults to source PVC request size.
  -c STORAGE_CLASS   Target PVC storageClassName. Defaults to source PVC storageClassName.
  -r REPO_BASE       Restic repository base. Defaults to restic-backup-config.

Examples:
  restore-pvc.sh -n tortuga -s heimdall-config-pvc
  restore-pvc.sh -n tortuga -s heimdall-config-pvc -t heimdall-restore-test-pvc
EOF
}

namespace=
source_pvc=
target_pvc=
size=
storage_class=
repo_base=
aws_region=

while getopts "hn:s:t:S:c:r:" opt; do
    case "$opt" in
        h)
            usage
            exit 0
            ;;
        n) namespace=$OPTARG ;;
        s) source_pvc=$OPTARG ;;
        t) target_pvc=$OPTARG ;;
        S) size=$OPTARG ;;
        c) storage_class=$OPTARG ;;
        r) repo_base=$OPTARG ;;
        *)
            usage >&2
            exit 2
            ;;
    esac
done

if test -z "$namespace" || test -z "$source_pvc"; then
    usage >&2
    exit 2
fi

target_pvc=${target_pvc:-${source_pvc}-restore-test}
restore_id=$(printf '%s' "$source_pvc" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9_.-]/-/g' | cut -c1-63)
job_name=$(printf 'restic-restore-%s' "$target_pvc" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9-]/-/g' | cut -c1-63 | sed 's/-$//')

if test -z "$size"; then
    size=$(kubectl -n "$namespace" get pvc "$source_pvc" -o jsonpath='{.spec.resources.requests.storage}')
fi

if test -z "$storage_class"; then
    storage_class=$(kubectl -n "$namespace" get pvc "$source_pvc" -o jsonpath='{.spec.storageClassName}')
fi

if test -z "$repo_base"; then
    repo_base=$(kubectl -n restic-backup get configmap restic-backup-config -o jsonpath='{.data.RESTIC_REPOSITORY_BASE}')
fi
aws_region=$(kubectl -n restic-backup get configmap restic-backup-config -o jsonpath='{.data.AWS_DEFAULT_REGION}')

repository="${repo_base%/}/${namespace}/${source_pvc}"

echo "Creating restore target PVC ${namespace}/${target_pvc}"
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: ${target_pvc}
  namespace: ${namespace}
  labels:
    app.kubernetes.io/name: kvrb
    app.kubernetes.io/component: restore-test
    kvrb.seedboxk8s.micahrl.com/restore-test: ${restore_id}
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: ${storage_class}
  resources:
    requests:
      storage: ${size}
EOF

echo "Copying restic secret into ${namespace}"
kubectl -n restic-backup get secret restic-backup-env -o json \
  | jq \
      --arg name restic-restore-env \
      --arg namespace "$namespace" \
      --arg restore_id "$restore_id" \
      'del(.metadata.uid,.metadata.resourceVersion,.metadata.creationTimestamp,.metadata.annotations,.metadata.managedFields) |
       .metadata.name=$name |
       .metadata.namespace=$namespace |
       .metadata.labels["app.kubernetes.io/name"]="kvrb" |
       .metadata.labels["app.kubernetes.io/component"]="restore-test" |
       .metadata.labels["kvrb.seedboxk8s.micahrl.com/restore-test"]=$restore_id' \
  | kubectl apply -f -

echo "Creating restore job ${namespace}/${job_name}"
cat <<EOF | kubectl apply -f -
apiVersion: batch/v1
kind: Job
metadata:
  name: ${job_name}
  namespace: ${namespace}
  labels:
    app.kubernetes.io/name: kvrb
    app.kubernetes.io/component: restore-test
    kvrb.seedboxk8s.micahrl.com/restore-test: ${restore_id}
spec:
  backoffLimit: 0
  template:
    metadata:
      labels:
        app.kubernetes.io/name: kvrb
        app.kubernetes.io/component: restore-test
        kvrb.seedboxk8s.micahrl.com/restore-test: ${restore_id}
    spec:
      restartPolicy: Never
      containers:
        - name: restore
          image: alpine:3.22
          envFrom:
            - secretRef:
                name: restic-restore-env
          env:
            - name: AWS_DEFAULT_REGION
              value: ${aws_region}
            - name: RESTIC_REPOSITORY
              value: ${repository}
          command: ["/bin/sh", "-ceu"]
          args:
            - |
              apk add --no-cache ca-certificates restic
              restic snapshots
              # Exclude security.* xattrs bc we may not have permission to set SELinux labels
              restic restore latest --target /restore --exclude-xattr security.*
              cp -a /restore/source/. /target/
              rm -rf /restore/source
          volumeMounts:
            - name: target
              mountPath: /target
            - name: restore-work
              mountPath: /restore
      volumes:
        - name: target
          persistentVolumeClaim:
            claimName: ${target_pvc}
        - name: restore-work
          emptyDir: {}
EOF

cat <<EOF

Restore job created.

Watch logs:
  kubectl -n ${namespace} logs -f job/${job_name}

Inspect restored PVC:
  kubectl -n ${namespace} run ${target_pvc}-shell --rm -it --restart=Never --image=alpine:3.22 --labels=app.kubernetes.io/name=kvrb,app.kubernetes.io/component=restore-test,kvrb.seedboxk8s.micahrl.com/restore-test=${restore_id} --overrides='{"spec":{"containers":[{"name":"'${target_pvc}'-shell","image":"alpine:3.22","stdin":true,"tty":true,"command":["/bin/sh"],"volumeMounts":[{"name":"target","mountPath":"/target"}]}],"volumes":[{"name":"target","persistentVolumeClaim":{"claimName":"'${target_pvc}'"}}]}}'

Clean up restore test resources:
  kubectl -n ${namespace} delete job,pod -l kvrb.seedboxk8s.micahrl.com/restore-test=${restore_id} --ignore-not-found
  kubectl -n ${namespace} wait --for=delete pod -l kvrb.seedboxk8s.micahrl.com/restore-test=${restore_id} --timeout=120s
  kubectl -n ${namespace} delete pvc,secret -l kvrb.seedboxk8s.micahrl.com/restore-test=${restore_id} --ignore-not-found
EOF
