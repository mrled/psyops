---
title: progfiguration-k3s.sh
weight: 90
---

I deploy Kubernasty on nodes managed by `progfiguration`,
my experimental infrastructure management package.
This package deploys `progfiguration-k3s.sh`,
which partially automates the setup and teardown processes.

* Boot the servers
* Run `progfiguration-k3s.sh init` on the first server,
  and wait until `kubectl get nodes` shows that node as `Ready`
* Run `progfiguration-k3s.sh token` to retrieve the cluster token for subsequent machines
* Run `progfiguration-k3s.sh join <TOKEN>` on subsequent machines, one at a time;
  _make sure each machine is `Ready` before attempting to join the next node_
* Get the kubeconfig with `progfiguration-k3s.sh kubeconfig`,
  copy the output to `/secrets/psyops-secrets/kubernasty/kubeconfig.yaml` in the psyops container,
  and add it to gopass with
  `cat /secrets/psyops-secrets/kubernasty/kubeconfig.yml | gopass insert -m kubernasty/kubeconfig`
