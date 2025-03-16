---
title: Postgres & LDAP
---

I would like to integrate some Postgres databases with LDAP, but this is inconvenient.

On the one hand, [Postgres supports ldap auth](https://www.postgresql.org/docs/current/auth-ldap.html),
and [CloudNative-PG exposes it](https://cloudnative-pg.io/documentation/1.25/postgresql_conf/#ldap-configuration).
However, this only works for _users that are separately created in Postgres_.
It will use LDAP to check the password of a user added to the database server;
it will not allow a user that exists in LDAP to connect unless it has been added to the database server separately.

An aside, it took me a while to figure out how to do TLS to the LDAP server.
You have to use [projected volumes](https://github.com/cloudnative-pg/cloudnative-pg/discussions/583)
to mount the LDAP's TLS root CA cert
and then set the `LDAPTLS_CACERT` variable to the projected path.

I spent some time trying to make this work with `map` directives in `pg_hba.conf`,
only to discover far too late that it doesn't support these with `ldap`.
It does support them with `gssapi`, that is, Kerberos,
but deploying Kerberos infrastructure in the cluster seems too painful for this purpose,
and has the downside of requiring more state.

Probably the easiest lift is to use [`ldap2pg`](https://ldap2pg.readthedocs.io/en/latest/),
a Go program that creates users in Postgres from LDAP.
In practice this sounds annoying;
either I have to build a trigger system or I have to run it on an interval and wait for it to apply.
