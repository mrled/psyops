---
title: cluster.sh
---

I recommend keeping a `cluster.sh` script with useful environment variables and aliases,
for instance: {{< repolink "kubernasty/cluster.sh" >}}.

Specific suggestions:

```sh
# Set the SOPS AGE recipients so that `sops -e ...` always works
export SOPS_AGE_RECIPIENTS=age1869u6cnxhf7a6u6wqju46f2yas85273cev2u6hyhedsjdv8v39jssutjw9

# Retrieve the SOPS AGE private key from your password manager
# Only set the key if it's not already set
# (means we only require authentication to 1p the first time we source this file)
if test -z "$SOPS_AGE_KEY"; then
    export SOPS_AGE_KEY="$(op item get o76jbsaf4aj5tdl77tupssi2xu --field=notesPlain --format json | jq -r .value)"
fi

# Aliases and functions for commands that are long and hard to remember,
# perhaps because they must be run inside a container or retrieve a secret.
#
# Example:
# Open a psql client to a cluster that follows our normal conventions
kpsql() {
    local namespace="$1"
    local user="$2"
    local cluster="$3"
    shift 3
    local PGUSER="$(kubectl get secret -n "$namespace" "pg-user-$user" -ojson | jq -r '.data.username | @base64d')"
    local PGPASSWORD="$(kubectl get secret -n "$namespace" "pg-user-$user" -ojson | jq -r '.data.password | @base64d')"
    local PGDATABASE="$(kubectl get cluster -n "$namespace" "$cluster" -ojson | jq -r '.spec.bootstrap.initdb.database')"
    kubectl run -n "$namespace" psql-client --rm --env=PGUSER="$PGUSER" --env=PGPASSWORD="$PGPASSWORD" --env=PGDATABASE="$PGDATABASE" -it --image=postgres -- psql -h "${cluster}-rw" "$@"
}
```
