# Kubernasty

Kubernasty is my home k3s cluster.

Introduction:

* [Conventions](docs/conventions.md) is a brief introduction to how I organize this repo, create secrets, etc.

Deploying the cluster:

* [Initial cluster creation](docs/initial-cluster-creation.md) shows how the bare cluster is created.
* [Ingress and certificates](docs/ingress-and-certificates.md) uses the `whoami` container to show how to allow web traffic into your cluster.
* [Longhorn](docs/longhorn.md) describes configuring the Longhorn persistent volume manager

Appendix:

* [Troubleshooting](docs/troubleshooting.md) is a grab bag of bullshit I ran into and swear words I said when I figured it out.
* [Todo](docs/todo.md) is a list of improvements to make in the future.
