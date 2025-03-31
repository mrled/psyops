---
title: OpenSearch
---

OpenSearch collects logs for the instance.
See {{< repolink "/kubernasty/crust/logging" >}}.

## Create index pattern in OpenSearch

Once the cluster is up, and Fluent Bit is collecting logs,
make index patterns.
<https://clusterlogs.micahrl.me/app/management/opensearch-dashboards/indexPatterns>,
or:

* OpenSearch Dashboards web UI
* Left sidebar
* Management section
* Stack Management tab
* Index Patterns tab

Create index patterns for everything that Fluent Bit is collecting:

* `kubernasty-container-logs-*`
* `kubernasty-node-logs-*`

## Exploring logs in OpenSearch

Requires that Index Patterns are created first.

The "Discover" feature does real time search and filtering.
<https://clusterlogs.micahrl.me/app/discover>,
or:

* OpenSearch Dashboards web UI
* Left sidebar
* Discover
