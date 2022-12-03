# Kubernasty cluster environment variables and functions for dot-sourcing.

export KUBECONFIG=/secrets/psyops-secrets/kubernasty/kubeconfig.yml

export SOPS_AGE_RECIPIENTS=age1869u6cnxhf7a6u6wqju46f2yas85273cev2u6hyhedsjdv8v39jssutjw9
export SOPS_AGE_KEY_FILE=/secrets/psyops-secrets/kubernasty/kubernasty-sops.age

sopsandstrip() {
    sops "$@" | sed 's/_unencrypted:$/:/g'
}
