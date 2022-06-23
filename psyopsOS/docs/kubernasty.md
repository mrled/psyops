# Kubernasty

This is my home k3s cluster

## Initial cluster creation

You have to do this manually - the progfiguration won't do it for you.

- Set `start_k3s` to `False` on all nodes
- Boot the first node
- Run some commands

```sh
# This is required or it won't be able to find binaries it requires for networking
# You can see that /etc/conf.d/k3s also does this
export PATH="/usr/libexec/cni/:$PATH"

# Start the server and tell it that it is initializing a new cluster
k3s server --cluster-init --token SECRET_TOKEN_VALUE
# Wait until it looks like that finished, and then ctrl-c

rc-service k3s start
```

Then on the next node

```sh
export PATH="/usr/libexec/cni/:$PATH"
K3S_TOKEN="raspi_cluster_token_1234" k3s server --server https://$FIRST_MACHINE_IP:6443
```

And do that again for all other nodes.

You can see whether nodes are joining successfully with something like this (after joining one other node to the cluster).

```
zalas:~# kubectl --kubeconfig /etc/rancher/k3s/k3s.yaml get nodes
NAME      STATUS   ROLES                       AGE   VERSION
kenasus   Ready    control-plane,etcd,master   58m   v1.23.6-k3s1
zalas     Ready    control-plane,etcd,master   75m   v1.23.6-k3s1
```

After that, make sure to set `start_k3s` to `True` on all nodes.
