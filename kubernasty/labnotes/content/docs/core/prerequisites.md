---
title: Prerequisites
weight: 10
---

I am using psyopsOS for my cluster.
psyopsOS is an operating system I build based on Alpine Linux;
see {{< repolink "psyopsOS" >}}.

## When creating the cluster for the first time

Make sure that k3s is not set to start on boot.
Set `start_k3s` to `False` for all of the nodes in the cluster in progfiguration.

Once the cluster is up, re-enable k3s auto start on boot.
