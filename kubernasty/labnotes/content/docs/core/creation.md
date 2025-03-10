---
weight: 20
title: Cluster creation
---

You have to do initial cluster setup manually.

In this cluster, I have just 3 nodes, which are both manager and worker nodes.

See [Conventions]({{< ref "conventions" >}}) for how I do certain specific things,
including secrets management and how I store manifest files.

## Bring up the first cluster node

Special tasks must be performed one time on the first node only.

### Configure kube-vip

Official documentation: <https://kube-vip.io/docs/usage/k3s/>

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
k3s server --cluster-init
```

At this point, you need to wait until it's finished initializing.
How do you know when it's finished?

* Wait for `Reconciliation of snapshot data in k3s-etcd-snapshots ConfigMap complete` to appear in the terminal
* Use another shell and make sure that `kubectl get nodes` looks normal
* Then ctrl-c in the first terminal to stop the k3s init process
* Start k3s via the init scripts: `rc-service k3s start`
* Retrieve the server token to allow joining the other nodes: `cat /var/lib/rancher/k3s/server/node-token`

When k3s is running, `kube-vip` will automatically configure the VIP address on the interface --
in this case, the `psy0` interface will have `192.168.1.200` added to it.

## Bring up a second cluster node

These are much simpler.
Run this on each of the remaining nodes, one at a time --
wait until one node has fully joined the cluster before joining another one.

```sh
export K3S_TOKEN="SECRET_TOKEN_VALUE"
vipaddress="192.168.1.200"
export PATH="/usr/libexec/cni/:$PATH"
k3s server --server https://$vipaddress:6443
```

{{< hint "warning" >}}
**Do you get an error like `failed to get CA certs` after uninstalling and reinstalling k3s?**

```text
kenasus:~# k3s server --server https://$vipaddress:6443
INFO[0000] Starting k3s v1.23.12+k3s1 (AlpineLinux)
FATA[0000] starting kubernetes: preparing server: failed to get CA certs: Get "https://192.168.1.200:6443/cacerts": dial tcp 192.168.1.200:6443: connect: connection refused
```

Make sure that your system isn't holding on to the `$vipaddress`.

```text
kenasus:~# ip addr | grep "$vipaddress"
    inet 192.168.1.200/32 scope global psy0
```

If the above command returns something, delete the address with something like this
(note that my network card is called `psy0`; yours might be `eth0` or similar):

```sh
ip addr del $vipaddress/32 dev psy0
```

{{< /hint >}}

Wait until this node has finished initializing.

* Check with `kubectl get nodes` from the original server says that the new node is `Ready`.
* Then ctrl-c on the new node
* Start k3s via the init script: `rc-service k3s start`

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

## Verify that you can reboot the first node

Reboot the first node you configured.

* It might take 30-60 seconds before the VIP moves over to the second node.
  TODO: improve kubernasty VIP move time
* When the first node finishes booting, make sure it joins the cluster with `kubectl get nodes`
* After the first server reboots, the VIP should _not_ move back to the first server

## Bring up third and later cluster nodes

Follow the steps for bringing up the second node.

Make sure to bring up nodes only one at a time -- they cannot be brought up in parallel.

## Copy the kubeconfig file

Copy `/etc/rancher/k3s/k3s.yaml` to your client machine,
and change the `server` line to the kubevip IP address (`192.168.1.200` for me).
You can do something like `cat /etc/rancher/k3s/k3s.yaml  | sed 's/127.0.0.1/192.168.1.200/g'`.
Generally, you'd copy this to `~/.kube/config`.

To use it in the psyops container,
first start the container and run `psecrets unlock`.
Then save the config file (don't forget to change the `server` line)
to `/secrets/psyops-secrets/kubernasty/kubeconfig.yml`.
Finally, add it to the gopass repo with eg
`cat /secrets/psyops-secrets/kubernasty/kubeconfig.yml | gopass insert -m kubernasty/kubeconfig`.
My `psecrets-postunlock` script automatically saves a copy to that location again
after running `psecrets unlock` inside the psyops container.

WARNING: when retrieving a structured document like the YAML kubeconfig file,
make sure to pass the `-n` argument to `gopass`, like
`gopass -n kubernasty/kubeconfig`.
If you don't do this, `gopass` will try to parse the secret output as key:value pairs,
flattening and alphabetizing all the keys and making a mess of the YAML structure.
The `psecrets-postunlock` script in psyops does this automatically.

See [Conventions]({{< ref "conventions" >}}) for more specifics.

## Reboot all the nodes

It may be worth rebooting all nodes one by one to make sure they come up properly.

## Result

Now you have a Kubernetes cluster!

It does have a load balancer, as k3s ships with traefik.
It isn't running any services and it has no HTTPS certificates.
