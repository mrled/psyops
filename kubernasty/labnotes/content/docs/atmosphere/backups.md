---
title: Backups
---

Backing up the cluster entails a few different sub-tasks:

1. Backing up the Flux repository
2. Backing up PVs
3. Backing up etcd (optional)
4. Backing up applications (optional if you want to live on the edge)

## General backup considerations

### Backing up the Flux repository

Backing up the Flux repo should be easy;
it can be mirrored to GitHub
and will also be on your laptop.

### Backing up PVs

This is harder and more expensive.

When backing up live,
it also carries a risk of inconsistent backups,
e.g. backing up a PV underlying an active database
and storing different parts of the data before and after a change.

### Backing up etcd

This is not strictly necessary if you are backing up the Flux repo and PVs,
but it is recommended:

- Anything that is deployed outside of Flux is covered, especially secrets
- In particular, Secret resources that back Certificate resources from Let's Encrypt via Cert Manager
  must be re-requested from Let's Encrypt if they are not backed up.
  Let's Encrypt rate limts clients and domains,
  so if you are using LE this may be a significant concern.
  You might have built your production cluster slowly,
  a few certs a week,
  but requesting new ones all at once might cause LE to rate limit you for days or weeks.

### Backing up applications

You can also back up at the application level, e.g.:

- Gitea backups
- Postgres backups
- OpenSearch backups
- Rook Ceph backups
- etc etc

You can probably assume these backups will be consistent,
but you'll then have to restore them application by application.

The simplest form of this is to stop the application entirely
and back up the underlying PVs.
For online backups,
you'll need to look at application-specific methods like `pg_dump` etc.

## TODO: implement cluster backups

- [ ] Flux backups
- [ ] PV backups
- [ ] etcd backups
- [ ] Application backups
  (enumerate all relevant apps here)

### Velero

[Velero](https://velero.io) is an open source Kubernetes backup system.

* It offers snapshot-based backups by default,
  where it takes snapshots of PVCs and backs them up.
* It also offers [File System Backup (FSB)](https://velero.io/docs/v1.15/file-system-backup/),
  where it connects to the mounted volume
  and backs it up via the filesystem.
  This allows it to work with volume types that don't support snapshots,
  but is beta quality and less consistent.
  I think we do not need this, as Ceph PVCs support snapshots.

### Keeping track of backups

If some things are best handled as PVC backups,
and other things are best handled as application backups,
how do we keep track of all the persistent data that needs backing up
to make sure we haven't missed anything?

- Store backup method in an annotation on each PV / PVC?
- Custom tooling that compares `kubectl get pvc -A`
  with a list showing how things should be backed up,
  and verifies that the backups exist somehow?
  Can we reliably do that declaratively?
- Prometheus alerts for PVCs / PVs that are not marked as backed up?
- Grafana dashboard that shows red/green?

### Most data is actually application backups

- Postgres
- 389 Directory Server
- OpenSearch
- Prometheus
- Gitea

All of these can be handled by application leevl backups.

### Back up to local object storage

Backing up _to_ local object storage is already pretty easy.
The CNPG operator can do it out of the box.

### Then backup the local object storage elsewhere

#### Ceph object storage permissions

As far as I can tell, there is no way to give a user read access to all current and future buckets in Ceph object storage.
(????)

Instead, we have to create our backup user and then manually apply a policy to each bucket that gives it access.
