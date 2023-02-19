---
title: Kubernetes dashboard
weight: 70
---

We can install the dashboard with Helm.

* The official docs say to remove the dashboard resource and re-apply when upgrading.
  Doing it this way, you have to be careful with Let's Encrypt secrets.
  However, since we are using a wildcard cert, this should not be a problem for us.

TODO: How can we access the dashboard with just HTTP Basic Authentication and/or oauth,
rather than getting the token from Kubernetes secrets?
