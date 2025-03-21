---
title: PgBouncer Ingress
---

We use PgBouncer to listen with TLS and pass through to a cluster Postgres server listening without TLS.
This ensures that connections from the outside world into the cluster are encrypted.

(We don't worry about internal cluster connections for now.
In the future, we should use cluster networking that does e2ee for us.)

## No SNI

Traefik `IngressRoute` understands HTTPS well enough to do "Server Name Indication" (SNI).
It can route the request to different apps depending on the domain name.
E.g. it can tell the difference between `radarr.example.com` and `sonarr.example.com`,
and route requests to those two domains to different apps.

TCP connections do not have an SNI feature,
so for SSH ports for git or Postgres ports for database connections,
you cannot differentiate based on the hostname like this.

To deal with this, you can either assign a dedicated LoadBalancer IP address to each PgBouncer,
or just use separate ports.

### Future work

TODO: can PgBouncer be configured as a kind of generic Postgres frontend to any database?

I think this is possible via the `PGBOUNCER_DSN_*` environment variables in the
[bitnami container](https://github.com/bitnami/containers/blob/main/bitnami/pgbouncer/README.md).
If this really works:

1. Use a generic DNS name like `pgbouncer.micahrl.me`
2. Move the bouncer to the `ingress` namespace
3. Show examples for connecting to other databases

## PgBouncer and superuser access

You can**not** connect through PgBouncer as a Postgres superuser.
If you need this,
spin up a pod to run the psql client instead, like:

```sh
PGPASSWORD="$(k get secret -n datadump datadumppg-superuser -ojson | jq -r '.data.password | @base64d')"
k run -n datadump psql-client --rm --env=PGPASSWORD="$PGPASSWORD" -it --image=postgres -- psql -h datadumppg-rw -U postgres datadump
```

## PgBouncer requirements

See the datadump cluster for a full example.

In short:

Run these statements against the db
(here they are run during `initdb` in the CloudNative-PG Cluster resource).
They set up a pgbouncer_auth role,
and allow it to authenticate other users.

```yaml
        # Create a role for pgbouncer that allows it to authenticate users
        - CREATE ROLE pgbouncer_auth;
        - CREATE SCHEMA pgbouncer AUTHORIZATION pgbouncer_auth;
        - GRANT CONNECT ON DATABASE datadump TO pgbouncer_auth;
        - GRANT SELECT ON pg_shadow TO pgbouncer_auth;
        - |+
          CREATE FUNCTION pgbouncer.get_auth(username TEXT)
          RETURNS TABLE(username TEXT, password TEXT) AS
          $$
          SELECT usename::TEXT, passwd::TEXT FROM pg_shadow WHERE usename = username;
          $$
          LANGUAGE sql SECURITY DEFINER;
        # - CREATE VIEW pgbouncer.auth AS SELECT * FROM pgbouncer.get_auth('');
        - GRANT SELECT ON pgbouncer.auth TO pgbouncer_auth;
```

Add a `pgbouncer` managed role.
This allows setting a password which automatically creates a kubernetes Secret,
and gives it inherited access to the role created above with the permissions.
(Postgres roles often work like user accounts and can be assigned a password directly. Idk.)

```yaml
      - name: pgbouncer
        login: true
        passwordSecret:
          name: pg-user-pgbouncer
        inherit: true
        inRoles:
          - pgbouncer_auth
```

Then deploy PgBouncer configured to authenticate as `pgbouncer`,
see the related Deployment and Service.
