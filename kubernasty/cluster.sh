# Kubernasty cluster environment variables and functions for dot-sourcing.

# This is the path in the container
# If this path doesn't exist, maybe we're outside the container, don't set $KUBECONFIG
PSYOPS_KCONF=/secrets/psyops-secrets/kubernasty/kubeconfig.yml
if test -e "$PSYOPS_KCONF"; then
    export KUBECONFIG="$PSYOPS_KCONF"
fi

export SOPS_AGE_RECIPIENTS=age1869u6cnxhf7a6u6wqju46f2yas85273cev2u6hyhedsjdv8v39jssutjw9
# op item get o76jbsaf4aj5tdl77tupssi2xu --field=notesPlain --format json | jq -r .value > flux.agekey
export SOPS_AGE_KEY="$(op item get o76jbsaf4aj5tdl77tupssi2xu --field=notesPlain --format json | jq -r .value)"

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
    certinfo "$1" | grep 'Issuer: '
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

helm_pull_from_flux() {
    # Pull out the Helm repo in name <tab> URL format from the cluster.
    # The HelmRepository CRD is a Flux custom resource;
    # Helm itself just uses a local config file,
    # so we do this to get our Flux configuration locally.
    # This is idempotent and safe to do repeatedly.
    kvpair_path="{range .items[*]}{.metadata.name}{'\t'}{.spec.url}{'\n'}{end}"
    kubectl get HelmRepository -A -o jsonpath="$kvpair_path" |
        while read -r name url; do
            helm repo add "$name" "$url"
        done
    helm repo update
}

# Some convenience aliases for talking to the LDAP server
# Include auth for each command,
# and set some options where appropriate.
alias kldapsearch='kubectl exec -itn directory dirsrv-0 -c configurator -- /bin/ldapsearch -H ldaps://dirsrv:636 -D "cn=Directory Manager" -y /containeripc/topsecret/ds-dm-password -LLL -o ldif-wrap=no'
alias kldapmodify='kubectl exec -itn directory dirsrv-0 -c configurator -- /bin/ldapmodify -H ldaps://dirsrv:636 -D "cn=Directory Manager" -y /containeripc/topsecret/ds-dm-password'
alias kldapadd='kubectl exec -itn directory dirsrv-0 -c configurator -- /bin/ldapadd -H ldaps://dirsrv:636 -D "cn=Directory Manager" -y /containeripc/topsecret/ds-dm-password'
alias kldapdelete='kubectl exec -itn directory dirsrv-0 -c configurator -- /bin/ldapdelete -H ldaps://dirsrv:636 -D "cn=Directory Manager" -y /containeripc/topsecret/ds-dm-password'
alias kldappasswd='kubectl exec -itn directory dirsrv-0 -c configurator -- /bin/ldappasswd -H ldaps://dirsrv:636 -D "cn=Directory Manager" -y /containeripc/topsecret/ds-dm-password'

# Convenience commands for dealing with the LDAP markers (migrations)
kldif_list_markers() {
    kldapsearch -s one -b "ou=ldifMarkers,dc=micahrl,dc=me" "(objectClass=*)" dn |
        grep -v '^\s*$' |
        sort
}
kldif_delete_marker() {
    filename="$1"
    kldapdelete "cn=$filename,ou=ldifMarkers,dc=micahrl,dc=me"
}
alias kldif_list_files='kubectl exec -it -n directory dirsrv-0 -c configurator -- sh -c "ls -a1 /initldifs/*.ldif"'
alias kldif_apply_ldifs='kubectl exec -it -n directory dirsrv-0 -c configurator -- /initsetup/apply_ldifs.sh'
alias kldif_passwd='kubectl exec -it -n directory dirsrv-0 -c configurator -- /initsetup/set_account_passwords.sh'
alias kldif_set_passwords='kubectl exec -it -n directory dirsrv-0 -c configurator -- /initsetup/set_account_passwords.sh'
kldif_cat() {
    filename="$1"
    kubectl exec -it -n directory dirsrv-0 -c configurator -- cat "/initldifs/$filename"
}

# This one is for testing usernames/passwords
alias kldapwhoami='kubectl exec -it -n directory dirsrv-0 -c configurator -- ldapwhoami -H ldaps://dirsrv:636'

# Talk to the object store with credentials from a CephObjectStoreUser
# Requires the AWS CLI (uv tool install awscli)
#
# AWS_REQUEST_CHECKSUM_CALCULATION and AWS_RESPONSE_CHECKSUM_VALIDATION
# must be set to disable some newer AWS S3 validation that Ceph doesn't support.
# <https://github.com/aws/aws-cli/issues/9214>
kaws_cephuser() {
    local namespace="$1"
    local user="$2"
    shift 2
    local objstore=cephalopodobj-nvme-3rep
    local secname="rook-ceph-object-user-$objstore-$user"
    local secret=$(kubectl get secret -n $namespace $secname -o json)
    AWS_ACCESS_KEY_ID="$(echo "$secret" | jq -r '.data.AccessKey | @base64d')" \
        AWS_SECRET_ACCESS_KEY="$(echo "$secret" | jq -r '.data.SecretKey | @base64d')" \
        AWS_ENDPOINT_URL_S3="https://objects.micahrl.me" \
        AWS_REQUEST_CHECKSUM_CALCULATION=when_required \
        AWS_RESPONSE_CHECKSUM_VALIDATION=when_required \
        aws "$@"
}

# Talk to the object store with credentials created by an ObjectBucketClaim
# Requires the AWS CLI (uv tool install awscli)
# Example:
#   ks3api_bucketclaim authelia authelia-pg-backup list-buckets
kaws_bucketclaim() {
    local namespace="$1"
    local claim="$2"
    shift 2
    local secret=$(kubectl get secret -n $namespace $claim -o json)
    AWS_ACCESS_KEY_ID="$(echo "$secret" | jq -r '.data.AWS_ACCESS_KEY_ID | @base64d')" \
        AWS_SECRET_ACCESS_KEY="$(echo "$secret" | jq -r '.data.AWS_SECRET_ACCESS_KEY | @base64d')" \
        AWS_ENDPOINT_URL_S3="https://objects.micahrl.me" \
        AWS_REQUEST_CHECKSUM_CALCULATION=when_required \
        AWS_RESPONSE_CHECKSUM_VALIDATION=when_required \
        aws "$@"
}

kaws_dd_pipeline_cp() {
    local filepath="$1"
    local dest="$2"
    shift
    kaws_bucketclaim datadump datadump-pipeline-manual-input s3 cp "$filepath" s3://datadump-pipeline-manual-input/"$dest"
}

# Open a psql client to a cluster that follows our normal conventions
kpsql() {
    local namespace="$1"
    local user="$2"
    local cluster="$3"
    shift 3
    local PGUSER="$(kubectl get secret -n "$namespace" "user-$user" -ojson | jq -r '.data.username | @base64d')"
    local PGPASSWORD="$(kubectl get secret -n "$namespace" "user-$user" -ojson | jq -r '.data.password | @base64d')"
    local PGDATABASE="$(kubectl get cluster -n "$namespace" "$cluster" -ojson | jq -r '.spec.bootstrap.initdb.database')"
    kubectl run -n "$namespace" psql-client --rm --env=PGUSER="$PGUSER" --env=PGPASSWORD="$PGPASSWORD" --env=PGDATABASE="$PGDATABASE" -it --image=postgres -- psql -h "${cluster}-rw" "$@"
}
