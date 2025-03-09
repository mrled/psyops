---
title: Authentik
weight: 50
---

Authentik replaces 389 Directory Server and Authelia together.

## Users and groups

Groups:

* `patricii`: admin users (basically just me)
* `proletarii`: regular human users (basically just me)
* `servi`: service accounts / bot users
* `barbari`: other human users (other people who I might want to give access to something in the cluster)

Users:

* `mrladmin`: My admin account
* `micahrl`: My regular account

Applications:

* `Rostra`: Allow proletarii as regular users and patricii as administrative users
* `Curia`: Cluster admin apps like Kubernetes are behind this application

## Reverse proxying

We'll create a new Authentik "application" and "provider" for most of our cluster applications.
We can reuse the same app/provider for all applications where
the authentication flow, policies, and allowed redirect URIs are the same.
We can create a new app/provider for appilcations that need special cases.

## The Rostra Application

This is used for regular user type apps in my cluster.

* Allows proletarii regular user access
* Allows patricii administrative access
* Disallow servi/barbari
