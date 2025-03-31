---
title: Backups
---

Backing up the cluster entails a few different sub-tasks:

1. Backing up the Flux repository
2. Backing up PVs
3. Backing up etcd (optional)
4. Backing up applications (optional if you want to live on the edge)

## TODO: implement cluster backups

- [ ] Flux backups
- [ ] PV backups
- [ ] etcd backups
- [ ] Application backups
  (enumerate all relevant apps here)

## Backing up the Flux repository

Backing up the Flux repo should be easy;
it can be mirrored to GitHub
and will also be on your laptop.

## Backing up PVs

This is harder and more expensive.

When backing up live,
it also carries a risk of inconsistent backups,
e.g. backing up a PV underlying an active database
and storing different parts of the data before and after a change.

## Backing up etcd

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

## Backing up applications

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
