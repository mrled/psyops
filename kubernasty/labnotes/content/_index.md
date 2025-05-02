---
title: Home
---

# Kubernasty Labnotes

Kubernasty is my home k3s cluster.

These labnotes describe how I configured it.
They're written mostly for myself,
but may be useful as an example for others.

{{< hint warning >}}
This is my home lab I built for learning Kubernetes,
not a production deployment that has been hardened by experts.
Use your best judgement,
do your own research,
your mileage may vary,
offer not valid in any states except "disarray".
{{< /hint >}}

## Git repository

This is intended as a guide to the Git repository;
it doesn't stand alone, and won't make sense without referring to the repo.
The repository is called [psyops]({{< repourl >}}),
and it is the main repo controlling all of my infrastructure.
Kubernasty has [its own directory in the repo]({{< repourl path="kubernasty" >}})
which contains the cluster configuration.
Some aspects of configuration touch shared resources, like DNS,
and those may reference other resources inside psyops but outside of the kubernasty subdir.

Links to the psyops repository are preceded with a `{{< psyops-symbol >}}` symbol,
for instance, this web page is generated from markdown at:
{{< repolink "kubernasty/labnotes/content/_index.md" >}}

## Organization

These labnotes are organized according to the
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
