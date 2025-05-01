---
title: Run code on a ConfigMap update
---

Kubernetes doesn't support this out of the box because it hates you.

A few options, none of which I've actually tried, lol:

* Use a sidecar container running in a loop.
* Use a CronJob running very often.
* Use stakater/reloader and use a Deployment, with the main container just running in a loop or sleep.
    * Actually I think reloader can now re-deploy jobs when a cm has changed
      ([PR](https://github.com/stakater/Reloader/pull/808)),
      but the docs aren't updated yet.
      **This is probably the best answer for now.**
* Use something like
  [kubernetes-event-exporter](https://github.com/resmoio/kubernetes-event-exporter)
  to send Kubernetes events like ConfigMap updates to a queue like Kafka,
  and then use KEDA to listen to the queue and run a ScaledJob.
