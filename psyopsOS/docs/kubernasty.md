# Kubernasty

This is my home k3s cluster

You have to do initial cluster setup manually.

## Before cluster configuration: kube-vip (manual)

Official documentation: <https://kube-vip.chipzoller.dev/docs/usage/k3s/>

We use kube-vip to float an IP address between the nodes.
(Technically, between control plane servers; in our cluster all servers do double duty as both control plane and worker.)
For this to work, we have to set it up before creating the cluster.

**This is only necessary to do on the first server. Do not repeat this on subsequent nodes.**

```sh
## Set for your environment
# The interface that will have the VIP added to it
# This must be the same on all nodes for kube-vip!
# Which is one reason we rename the primary NIC to psy0 earlier in the boot process.
interface=psy0
# The VIP address
address=192.168.1.200

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
    --address $address \
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

## Initial cluster configuration (manual)

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
K3S_TOKEN="SECRET_TOKEN_VALUE" k3s server --server https://$FIRST_MACHINE_IP:6443
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

## Traffic in to the cluster

We use Traefik, which comes with k3s by default.
We want to pair it with our HA stuff from kube-vip.

- <https://blog.crafteo.io/2021/11/26/traefik-high-availability-on-kubernetes-with-lets-encrypt-cert-manager-and-aws-route53/>
- <https://github.com/pacroy/whoami>

```sh
kubectl create ns cert-manager

# make cert-manager-aws-secret.yml
cat >cert-manager-aws-secret.yml <<EOF
kind: Secret
apiVersion: v1
type: Opaque
metadata:
  name: cert-manager-aws-secret
  # IMPORTANT: secret must be in same namespace as Cert Manager deployment
  namespace: cert-manager
stringData:
  # AWS Secret Access Key generated for our user
  secret-access-key: xxx
  # No need to specify Access Key ID here
  # It'll be specified on Cert Manager Issuer resource
EOF
kubectl apply -f cert-manager-aws-secret.yml -n cert-manager


cat >cert-manager-issuer.yml <<EOF
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: cert-manager-acme-issuer
  # Important: use the same namespace as Cert Manager deployment
  # Otherwise Cert Manager won't be able to find related elements
  namespace: cert-manager
spec:
  acme:
    # Email on which you'll receive notification for our certificates (expiration and such)
    email: pierre@crafteo.io
    # Name of the secret under which to store the secret key used by acme
    # This secret is managed by ClusterIssuer resource, you don't have to create it yourself
    privateKeySecretRef:
      name: cert-manager-acme-private-key
    # ACME server to use
    # Specify https://acme-v02.api.letsencrypt.org/directory for production
    # Staging server issues staging certificate which won't be trusted by most external parties but can be used for development purposes
    server: https://acme-staging-v02.api.letsencrypt.org/directory
    # Solvers define how to validate you're the owner of the domain for which to issue certificate
    # We use DNS-01 challenge with Route53 by providing related AWS credentials (access key and secret key) for an IAM user with proper rights to manage Route53 records
    solvers:
    - dns01:
        route53:
          # AWS Access Key ID for our Secret Key
          accessKeyID: AKIAXXXX
          # AWS region to use
          region: eu-west-3
          # Reference our secret with Secret Key
          secretAccessKeySecretRef:
            key: secret-access-key
            name: cert-manager-aws-secret
          # Optionally specify Hosted Zone
          # As per doc:
          # If set, the provider will manage only this zone in Route53 and will not do an lookup using the route53:ListHostedZonesByName api call.
          # hostedZoneID: xxx
EOF
```
