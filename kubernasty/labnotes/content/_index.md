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
  configuration and applications that are installed in a particular order,
  as other apps depend on them.
  Includes things like our CI/CD tool,
  cluster storage,
  etc.
* **Crust**:
  applications that can be installed on top of the base layer.

## Status

This documentation is in the middle of a rewrite.

* **Core**: Complete
* **Mantle**: In progress
* **Crust**: To do

