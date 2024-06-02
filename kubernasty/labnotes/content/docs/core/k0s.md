---
weight: 20
title: k0s
---

I'm using k0s now instead of k3s.

In progfiguration:

* Set `start_kubernasty` to `False` for all nodes.
* Apply the progfigsite to all nodes,
  which installs k0s, and creates the k0s configuration file.

Now run `k0sctl`.
This is a one-time task that bootstraps the cluster.

* `k0sctl apply -c kubernasty/k0sctl.yaml`
* Wait for all the nodes to come up
* Get a kubeconfig with `k0sctl kubeconfig -c kubernasty/k0sctl.yaml`
  and place it into `~/.kube/config` on whatever machine you're using to administer the cluster
  (your laptop, whatever)
* See pods starting with `kubectl get pods -A` etc

Now configure Flux for gitops.
This is a one-time task that deploys Flux to the cluster,
and thereafter Flux will look in the Git repository for configuration.

* Create a new SSH key with `ssh-keygen`, and save it to `./flux_deploy_id`
* Add it to your gitops repository as a deploy key; it requires read/write
* `flux bootstrap git --url=ssh://git@github.com/mrled/psyops --path=kubernasty/fluxroot --branch=master --private-key-file=./flux_deploy_id`
* (Add `--silent` to make it go without manual confirmation)
* Delete the `./flux_deploy_id` file; it's saved to the cluster now
* Create an `age` key with `age-keygen` called `./flux.agekey` --
  note that this filename is important, as the next command uses the filename
  as the name for the secret value,
  and the secret value name must end with `.agekey`
* Add it as a SOPS key for Flux with
  `kubectl create secret generic sops-age --namespace=flux-system --from-file=./flux.agekey`
* You can delete the key from local disk

In progfiguration again

* Set `start_kubernasty` to `True` for all nodes
* Test that reboots come up properly

## Low level stuff handled by Flux

* Assuming `kubernasty/fluxroot` in the GitHub repository is empty and Flux has nothing to deploy,
  the cluster is pretty barebones at this point,
  and lacks many normal features.
    * It has no load balancer
    * It has no ingress
    * There is no single highly available IP address that connects to the cluster's control plane,
    which means that as nodes reboot you will have to change the address for the cluster
    in `~/.kube/config` files etc
* In psyops we have manifests to address these issues with (respectively)
    * MetalLB
    * Traefik
    * Manifests that configure the control plane and the two previous components for high availability
