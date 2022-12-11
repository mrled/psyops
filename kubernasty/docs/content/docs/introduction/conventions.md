---
title: Conventions and notes
weight: 10
---

These are optional, but good places to start if you're totally unfamiliar with Kubernetes cluster administration.

* Store app/service manifests in git, in subdirectories under this one.
  Inside each service subdirectory, have a sub-subdir for each type of kubernetes object,
  with manifests inside.
  [Similar to this suggestion](https://boxunix.com/2020/05/15/a-better-way-of-organizing-your-kubernetes-manifest-files/).
* Use `sops` to encrypt secrets.
  In my case, I'm using my `psyops` container built from code in this repo to run `kubectl`,
  so I store my `sops` age key in the `psyops-secrets.tar.gz.gpg` file next to other psyops secrets.
  See below subsection for some examples.
  This is particularly well suited to tiny clusters and teams.
  [Based on this suggestion](https://frederic-hemberger.de/notes/kubernetes/manage-secrets-with-sops/).
* Note that Kubernetes stores all of the manifests in its etcd database,
  but you should probably keep your own copy here so you know how the services work.
  There are gitops tools like argocd that can automatically apply them for you,
  but for a tiny home cluster you can also just save them to git and apply them on the command line yourself.
* You can run `kubectl` on any machine with network access to the cluster;
  you don't have to ssh to one of the cluster nodes first.
  (This also means you don't have to keep the git repo checked out on your cluster node(s).)
  See the k3s [Cluster Access page](https://docs.k3s.io/cluster-access) for instructions;
  basically you copy `/etc/rancher/k3s/k3s.yaml` and change the `server` to your server's IP.
  In this cluster, we use `kube-vip` to create a floating VIP on the cluster network,
  so wait to do this step until `kube-vip` is configured,
  and use the VIP (in my case `192.168.1.200`) as the `server` in the kube config.
  Save it to `~/.kube/config` on the machine you'll run `kubectl` from.
  I actually save mine to the normal place for psyops secrets in `/secrets/psyops-secrets/kubernasty/kubeconfig.yml`
  and set `KUBECONFIG=/secrets/psyops-secrets/kubernasty/kubeconfig.yml` instead.

## Initial `sops` configuration

First, I had to create an `age` key for Kubernasty's `sops` encryption.

```sh
age-keygen -o /path/to/somewhere/safe/kubernasty-sops.age
```

Then I can use it in `cluster.sh` below.

## `cluster.sh` script

Dot-source the `cluster.sh` script from within the psyops container.
Here's an annotated example:

```sh
# Set some things for my environment.
# I save this as cluster.sh for dot-sourcing.
#
# I keep my kubeconfig file here
export KUBECONFIG=/secrets/psyops-secrets/kubernasty/kubeconfig.yml
# Exporting this variable means that sops will use this public key for encryption.
# This value comes from the kubernasty-sops.age file created above.
export SOPS_AGE_RECIPIENTS=age1869u6cnxhf7a6u6wqju46f2yas85273cev2u6hyhedsjdv8v39jssutjw9
# Exporting this variable means that sops will find the private key at this path.
export SOPS_AGE_KEY_FILE=/secrets/psyops-secrets/kubernasty/kubernasty-sops.age
# A simple function that strips the '_unencrypted' suffix -- see below for more on that.
sopsandstrip() {
    sops "$@" | sed 's/_unencrypted:$/:/g'
}
```

I can dot-source that script and then use it to easily encrypt secrets and store the encrypted result in this git repo.

```sh
# Source the above script
. cluster.sh

# Create a secrets file... this is just an example.
# Note the '_unencrypted' suffix to 'metadata'.
# This is optional, but it means that you can still see the name and namespace.
# You will need to strip this suffix before applying with kubectl,
# see sops_kubernasty function above.
# Also, note that even comments are encrypted by sops,
# but comments under the 'metadata_unencrypted' section will remain plaintext.
# Remember that it must be created in the same namespace as the service that will use it.
cat > secret.tmp <<EOF
---
kind: Secret
apiVersion: v1
type: Opaque
metadata_unencrypted:
  name: example-credential-name
  namespace: asdfwhatever
stringData:
  secretName: s3cr3tV@lue
EOF

# Use sops to encrypt it
# We save it to the right location for the psyops container, adjust to your own needs if not using psyops.
# We do NOT use `sopsandstrip` for this, because we don't want to strip the '_unencrypted' suffix from keys.
sops --encrypt secret.tmp > /psyops/kubernasty/SERVICENAME/secrets/SECRETNAME.yml
# Then you can delete the tmp secret file
rm secret.tmp

# Use sops to decrypt the encrypted file for viewing.
sopsandstrip --decrypt /psyops/kubernasty/SERVICENAME/secrets/SECRETNAME.yml

# Use sops to decrypt the file to apply with kubectl
sopsandstrip --decrypt /psyops/kubernasty/SERVICENAME/secrets/SECRETNAME.yml |
  kubectl apply -f -
```
