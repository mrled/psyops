# Cluster creation

You have to do initial cluster setup manually.

In this cluster, I have just 3 nodes, which are both manager and worker nodes.

## Make sure k3s is not set to start in progfiguration

Set `start_k3s` to `False` for all of the nodes in the cluster in progfiguration.

## Bring up the first cluster node

Special tasks must be performed one time on the first node only.

### Configure kube-vip

Official documentation: <https://kube-vip.chipzoller.dev/docs/usage/k3s/>

We use kube-vip to float an IP address between the nodes.
(Technically, between control plane servers; in our cluster all servers do double duty as both control plane and worker.)
For this to work, we have to set it up before creating the cluster.

```sh
## Set for your environment
# The interface that will have the VIP added to it
# This must be the same on all nodes for kube-vip!
# Which is one reason we rename the primary NIC to psy0 earlier in the boot process.
interface=psy0
# The VIP address
vipaddress=192.168.1.200

# Get the RBAC manifest, which will be the start of the kube-vip manifest
curl https://kube-vip.io/manifests/rbac.yaml -o kube-vip.yaml

# Set an alias for easier use
kvversion=$(curl -sL https://api.github.com/repos/kube-vip/kube-vip/releases | jq -r ".[0].name")
ctr images pull ghcr.io/kube-vip/kube-vip:$kvversion
alias kube-vip="ctr run --rm --net-host ghcr.io/kube-vip/kube-vip:$kvversion vip /kube-vip"
# Now you can run like 'kube-vip -h' to see help

# Generate the DaemonSet manifest.
# This can be combined with the RBAC manifest by separating them with `\n---\n`,
# the standard YAML document separator.

printf "\n---\n" >> kube-vip.yaml
kube-vip manifest daemonset \
    --interface $interface \
    --address $vipaddress \
    --inCluster \
    --taint \
    --controlplane \
    --services \
    --arp \
    --leaderElection >> kube-vip.yaml

# Copy it to the manifests folder (only needs to happen on the first cluster member)
mkdir -p /var/lib/rancher/k3s/server/manifests
cp kube-vip.yaml /var/lib/rancher/k3s/server/manifests/
```

### Create the cluster

```sh
# This is required or it won't be able to find binaries it requires for networking
# You can see that /etc/conf.d/k3s also does this
export PATH="/usr/libexec/cni/:$PATH"

# Start the server and tell it that it is initializing a new cluster
k3s server --cluster-init --token SECRET_TOKEN_VALUE
# Wait until it looks like that finished, and then ctrl-c

rc-service k3s start
```

When k3s is running, `kube-vip` will automatically configure the VIP address on the interface --
in this case, the `psy0` interface will have `192.168.1.200` added to it.

## Bring up the other cluster nodes

These are much simpler.
Run this on each of the remaining nodes, one at a time --
wait until one node has fully joined the cluster before joining another one.

```sh
vipaddress="192.168.1.200"
export PATH="/usr/libexec/cni/:$PATH"
K3S_TOKEN="SECRET_TOKEN_VALUE" k3s server --server https://$vipaddress:6443
# Wait until it looks like that finished, and then ctrl-c

rc-service k3s start
```

Show the nodes after each one to verify that it is working as expected.

```
zalas:~# kubectl --kubeconfig /etc/rancher/k3s/k3s.yaml get nodes
NAME      STATUS   ROLES                       AGE   VERSION
kenasus   Ready    control-plane,etcd,master   58m   v1.23.6-k3s1
zalas     Ready    control-plane,etcd,master   75m   v1.23.6-k3s1
```

For these other nodes, since `kube-vip` has already configured the VIP on the first node,
it will not move it to the new nodes as they come up.
However, if the first node goes down,
it will move the address to one of the other nodes that is healthy.


## Result

Now you have a Kubernetes cluster!

It does have a load balancer, as k3s ships with traefik.
It isn't running any services and it has no HTTPS certificates.
