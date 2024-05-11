# seedboxk8s cluster environment variables and functions for dot-sourcing.

# Examine certificates using openssl
certinfo() {
    hostname="$1"
    port="${2:-443}"
    echo "" |
        openssl s_client -showcerts -servername "$hostname" -connect "$hostname":"$port" 2>/dev/null |
        openssl x509 -inform pem -noout -text
}

# Show the issuing CA for a remote server
# With this you can tell if a cert was issued by:
# - the Traefik default self-signed cert, which returns something like `Issuer: CN=TRAEFIK DEFAULT CERT`
# - the Let's Encrypt staging CA, which returns somethign like `Issuer: C=US, O=(STAGING) Let's Encrypt, CN=(STAGING) Artificial Apricot R3`
# - the LE prod CA, which returns something like `Issuer: C=US, O=Let's Encrypt, CN=R3`
certissuer() {
    certinfo "$@" | grep 'Issuer: '
}

# From <https://fluxcd.io/flux/faq/#what-is-the-behavior-of-kustomize-used-by-flux>
flux_dryrun() {
    dir="$1"
    if ! test "$dir"; then
        echo "Missing directory argument"
        return 1
    fi
    kubectl kustomize --load-restrictor=LoadRestrictionsNone --reorder=legacy "$dir" |
        kubectl apply --server-side --dry-run=server -f-
}

# Tell Flux to reconcile the Git repo immediately
# This keeps you from having to wait 1-5 minutes for it to check the repo on its own
# after pushing a change
flux_gitreconcile() {
    kubectl annotate --field-manager=flux-client-side-apply --overwrite gitrepository/flux-system -n flux-system reconcile.fluxcd.io/requestedAt="$(date +%s)"
}

kube_resources() {
    if test "$1"; then
        namespace="--namespace $1"
        pod_ns_note="(in namespace $1)"
    else
        namespace="--all-namespaces"
        pod_ns_note="(all namespaces)"
    fi
    columns="Name:metadata.name"
    columns="$columns,READY:.status.containerStatuses[*].ready"
    columns="$columns,NAMESPACE:.metadata.namespace"
    columns="$columns,STATUS:.status.phase"
    columns="$columns,NODE:.spec.nodeName"
    columns="$columns,CPU-request:spec.containers[*].resources.requests.cpu"
    columns="$columns,CPU-limit:spec.containers[*].resources.limits.cpu"
    columns="$columns,RAM-request:spec.containers[*].resources.requests.memory"
    columns="$columns,RAM-limit:spec.containers[*].resources.limits.memory"

    echo "Pod resource requests and limits $pod_ns_note:"
    kubectl get pods $namespace -o custom-columns="$columns"

    echo
    echo
    # This is always for all namespaces bc its node-wide
    echo "Node resource requests and limits (all namespaces):"
    kubectl describe nodes | grep -A 3 "Resource .*Requests .*Limits"
    echo
}
