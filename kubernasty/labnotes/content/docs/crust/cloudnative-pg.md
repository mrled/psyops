---
name: CloudNativePG
weight: 40
---

We use CloudNativePG for Postgres database deployments.

## Backing up

<https://cloudnative-pg.io/documentation/1.25/backup/>

Backing up requires:
1. A `backup` configuration key in the `Cluster` resource,
  which sets the backup destination in S3
  and starts backing up the WAL.
  ```yaml
    backup:
      retentionPolicy: "7d"
      barmanObjectStore:
        endpointURL: "https://objects.micahrl.me"
        destinationPath: "s3://authelia-pg-backup"
        serverName: "autheliapg"
        s3Credentials:
          # This authelia-pg-backup secret is created automatically by the ObjectBucketClaim
          accessKeyId:
            name: authelia-pg-backup
            key: AWS_ACCESS_KEY_ID
          secretAccessKey:
            name: authelia-pg-backup
            key: AWS_SECRET_ACCESS_KEY
        wal:
          compression: gzip # Compress WAL files
  ```
2. A `ScheduledBackup` resource,
  which defines a schedule for full backups
  which will go to the same S3 destination as defined in the `Cluster`.
  ```yaml
  apiVersion: postgresql.cnpg.io/v1
  kind: ScheduledBackup
  metadata:
    name: autheliapg
    namespace: authelia
  spec:
    # The schedule cron field has seconds first
    # This indicates daily at 2am
    schedule: "0 0 2 * * *"
    backupOwnerReference: self

    # Back up to the same S3 bucket as the WAL archiving (defined in the Cluster)
    method: barmanObjectStore

    # Back up when this ScheduledBackup is first created
    immediate: true

    cluster:
      name: autheliapg
  ```

### Adding backups to an existing database

You can add backups after the fact.

If you use a secret reference for S3 credentials,
the operator will add access to that secret to the `Role` that the Postgres pods run under.

However, the pods have to be restarted in order to pick that up.
If you don't restart them, the pods will log errors like this trying to back up:
`"error":"while getting secret authelia-pg-backup: secrets \"authelia-pg-backup\" is forbidden: User \"system:serviceaccount:authelia:autheliapg\" cannot get resource \"secrets\" in API group \"\" in the namespace \"authelia\""`.
After restarting them, wait several minutes.

### Restoring

There are several ways to restore, definitely worth reading the docs on this.

Restoring must be done on a cluster running the same major version of Postgres.
You can specify this with `imageName: ghcr.io/cloudnative-pg/postgresql:16` in the new cluster,
based on what your old cluster was running.
(Find out with `k get pods -oyaml ...`.)

Here's a simple way to back up a running cluster and restore it into a test cluster.

```yaml
apiVersion: postgresql.cnpg.io/v1
kind: Backup
metadata:
  name: gitea-backup-test
  namespace: gitea
spec:
  method: barmanObjectStore
  cluster:
    name: gitea-pg-cluster
---
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: gitea-test
  namespace: gitea
spec:
  instances: 1
  imageName: ghcr.io/cloudnative-pg/postgresql:16 # must match the old cluster
  storage:
    size: 2Gi
    storageClass: cephalopodblk-nvme-2rep
  bootstrap:
    recovery:
      backup:
        name: gitea-backup-test
```

Connect with a command like

```sh
k run -n gitea -it --rm psql-client --image=ghcr.io/cloudnative-pg/postgresql:16 -- psql -U gitea -h gitea-test-rw
```

### Deleting the old cluster

* Switch the application to point to the new cluster
* Bring up the app and make sure it works
* Delete the old cluster with `k delete cluster -n gitea gitea-pg-cluster --cascade=orphan`,
  which leaves PVCs and pods and all other resources in place.
* Delete the pods associated with the cluster
* If necessary, recreate the cluster (same name etc) and it'll pick up the PVCs
* If the app continues to work with the old cluster deleted, remove the PVCs
  * Reassure yourself that they aren't still attached with `k describe pvc PVC-NAME -n NAMESPACE`,
    look for `Used By: <none>`.
  * Delete with `k delete pvc ...`
  * Delete the underlying PV with `k delete pv ...`
  * Delete Cluster services with `k delete svc -n NAMESPACE CLUSTER-r CLUSTER-ro CLUSTER-rw`

### Test backups reason #1239847

<https://github.com/cloudnative-pg/cloudnative-pg/discussions/2989>

Basically if you back up at the wrong time it might not work.
Lol!
What's a little data loss "in the short term" between friends?

### Upgrading Postgres versions

This is not supported live.

The recommended method is by spinning up a new cluster and importing data directly from the old cluster
<https://cloudnative-pg.io/documentation/current/database_import/>.

The CNPG team will add a more convenient upgrade path in a future version.
