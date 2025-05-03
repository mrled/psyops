---
title: OpenSearch
---

OpenSearch collects logs for the instance.
See {{< repolink "/kubernasty/applications/logging" >}}.

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

TODO: Create this automatically. There is no CRD for it, but maybe use a Job or a CronJob.

## Exploring logs in OpenSearch

Requires that Index Patterns are created first.

The "Discover" feature does real time search and filtering.
<https://clusterlogs.micahrl.me/app/discover>,
or:

* OpenSearch Dashboards web UI
* Left sidebar
* Discover

## Create an auto delete policy

* OpenSearch Dashboards web UI
* Left sidebar
* OpenSearch Plugins section
* Index Management tab
* Index Policies tab
* Create Policy
    * ID: `delete-old`
    * Add state:
        * State name: `delete`
        * Add action: `Delete`
    * Add state
        * State name: `hot`
        * Don't add any action
        * Add transition: destination stage: `delete`; condition: minimum index age: `30d`.
    * Set initial state: `hot`

TODO: Create this via `opensearchismpolicies.opensearch.opster.io` CRD from the operator.
