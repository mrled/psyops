# Kubernasty lab notes

Kubernasty is my home k3s cluster.

These lab notes describe how I configured it.
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

This is intended as a guide to the Git repository;
it doesn't stand alone, and won't make sense without referring to the repo.
The repository is called [psyops](https://github.com/mrled/psyops/),
and it is the main repo controlling all of my infrastructure.
Kubernasty has [its own directory in the repo](https://github.com/mrled/psyops/tree/master/kubernasty)
which contains the cluster configuration.
Some aspects of configuration touch shared resources, like DNS,
and those may reference other resources inside psyops but outside of the kubernasty subdir.
