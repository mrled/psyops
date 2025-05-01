---
title: "Failure: Configuring OpenSearch via the API"
---

It seems like this is supposed to be possible, but it doesn't work.

Things like index patterns are owned by the Dashboards application,
not the OpenSearch API.
(Technically they _are_ stored in an index called `.kibana`,
but this index is owned by the application, not OpenSearch,
and it may change from version to version.)

In theory you should be able to create the index patterns via the Dashboard application's `/api/...` routes.

* [Create saved objects API](https://www.elastic.co/guide/en/kibana/7.10/saved-objects-api-create.html)

I think that ought to work something like:

```sh
    #!/bin/sh
    set -eu
    curl -sS --fail-with-body -k -u "admin:password" -X POST "http://127.0.0.1:5601/api/saved_objects/_bulk_create?overwrite=true" \
      -H 'Content-Type:application/json' -H 'osd-xsrf: true' \
      -d '    [
      {
        "type": "index-pattern",
        "id":   "kubernasty-container-logs-*",
        "attributes": {
          "title": "kubernasty-container-logs-*",
          "timeFieldName": "@timestamp"
        }
      },
      {
        "type": "index-pattern",
        "id":   "kubernasty-node-logs-*",
        "attributes": {
          "title": "kubernasty-node-logs-*",
          "timeFieldName": "timestamp"
        }
      }
    ]'
```

However, this just doesn't seem to be possible for me.
For one, basic auth doesn't work:

* [[BUG] Basic Auth does not work for some API endpoints.  #5146](https://github.com/opensearch-project/OpenSearch-Dashboards/issues/5146)

But also, I don't have a `_dashboards/auth/login` path
(or one without the `_dashboards/`,
which I think is an artifact of Amazon's managed OpenSearch service).

```text
> ospass=$(k get secret -n logging clusterlogs-admin-password -ojson | jq -r '.data.password | @base64d')
> k exec -itn logging clusterlogs-master-0 -- curl -k -u "clusterlogs-admin:$ospass" -X GET 'http://clusterlogs-dashboards:5601/_dashboards/auth/login'
{"statusCode":401,"error":"Unauthorized","message":"Unauthorized"}
```

At this point, I gave up.
