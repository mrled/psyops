---
title: Gitea
---

We started with the Gitea Helm chart,
but the default deploys dozens of resources in four thousand lines of unmaintainble YAML.

We whittled it down to 2 secrets, a deployment, and a service in just a few hundred lines by:

* Removing Redis, which we expect we don't need
* Skipping the Postgres deployment, in favor of using the CNPG operator instead

TODO: Expand Gitea instructions, place earlier so that other apps can use it
