---
title: Prometheus
---

* Use the Prometheus Operator
* Deploy the Node Exporter using examples from [here](https://github.com/prometheus-operator/kube-prometheus/tree/main/manifests)
  * Requires the `prometheus` ServiceAccount to have extra privileges,
    see {{< repolink "kubernasty/crust/prometheus/prometheus/RBAC.prometheus.yaml" >}}.
    ```yaml
    - nonResourceURLs:
      - /metrics
      verbs:
      - get
    ```
    What happens is that Prometheus sends a token with requests to kube-rbac-proxy in the node-exporter DaemonSet.
    That token communicates the ServiceAccount that Prometheus is running under.
    kuibe-rbac-proxy will validate that it has access to this /metrics "nonResourceURL"...
    which is a URL that the Node Exporter DaemonSet is serving itself, I think.

## About

* Prometheus supports only a single instance
* Thanos adds lots of features on top of Prometheus
  * Deploying multiple Prometheus instances and querying across them for HA
    * This requires deduplication, because all the Prometheus instances don't know about each other
    * This means you want your ingress to go to thanos-querier, not prometheus itself
  * Storing data in object storage for good historicals
  * ... lots of other stuff

## Querying

* Go to `prometheus.micahrl.me` and start typing to find metrics
* Node Exporter provides metrics prefixed with `node_`

### Verifying that deduplication is working

To verify this, make sure that the thanos-query Deployment has **not** passed the `--deduplication` flag.
(Just comment it out, restart the Deployment, run this test, then uncomment it and restart the Deployment again.)

I used a query

```promql
up{job="node-exporter"}
```

and toggled the `Use Deduplication` checkbox in the Thanos Query UI.

When dedupe is enabled, I wee one line per node.
When its disabled, I see two lines per node,
which correlates to the two Prometheus instances I am running.

## Alerting

Prometheus alerting with HA is a little hacky because Thanos doesn't dedupe alerts.

TODO: Figure out Prometheus alerting.

## Grafana

You can see graphs at `https://prometheus.micahrl.me/graph`,
but Prometheus documentation [says](https://prometheus.io/docs/visualization/browser/)

> The expression browser is available at `/graph` on the Prometheus server, allowing you to enter any expression and see its result either in a table or graphed over time.
>
> This is primarily useful for ad-hoc queries and debugging. For graphs, use Grafana or Console templates.

Grafana is easier to start with.
Console templates let you define consoles in the hated Go template language and store them in source control.

TODO: Graph Prometheus metrics in Grafana.

TODO: Learn Prometheus [console templateing](https://prometheus.io/docs/visualization/consoles/)
