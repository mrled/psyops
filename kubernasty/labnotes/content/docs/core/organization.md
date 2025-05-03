---
title: Organization
weight: 60
---

The configuration stored in the repo are organized according to the
[internal structure of Earth](https://en.wikipedia.org/wiki/Internal_structure_of_Earth):

* **Core**:
  configuring the machines that will host the cluster,
  and other prerequisites like DNS.
* **Mantle**:
  configuration that we install by running `kubectl apply -f example.yaml`
  or other direct commands.
  Basically this includes anything we do not install via our CI/CD tool.
  This includes items we install this way in order to learn about Kubernetes,
  and things that cannot by installed by CI/CD like the CI/CD tool itself.
* **Crust**:
  configuration that we install via our CI/CD tool,
  including low-level applications like
  storage systems, DNS management, identity providers, and so forth.
  Nothing in this section is interesting to an end-user,
  but end-user apps rely on what we do in this layer.
* **Atmosphere**:
  apps we want to install for users
  (even if the only users are ourselves).
