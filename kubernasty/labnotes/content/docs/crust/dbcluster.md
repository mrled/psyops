---
title: "UNIMPLEMENTED: datadump cluster database"
weight: 91
---

Many things require database servers.

You can easily run one database container for each service that needs it,
but it might be useful to provide a highly available database installation for the entire cluster.

Options:

* Avoid the Crunchy Data operator, see <https://news.ycombinator.com/item?id=31883847>
* Use the Percona Postgres operator
    * Use a solution like this to create users: <https://www.percona.com/blog/manage-mysql-users-with-kubernetes/>
* Use CloudNativePG <https://cloudnative-pg.io/documentation/1.18/>

If I do this, I would call it `datadump`.
