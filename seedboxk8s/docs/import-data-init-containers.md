# Importing data via init containers

In the single node Docker Swarm cluster, we used local volumes,
which were just mounted from the filesystem.

In the single node Kubernetes cluster, we are using LVM volumes
to keep application configuration.
These can be automatically provisioned with TopoLVM.
However, we had to build a process for initially importing the data,
since they're managed entirely inside of Kubernetes.

For an example of this, see the sabnzbd deployment.
Many others use it as well.

The import-data initContainer waits until the config volume contains a file called import-data-complete.
Add data to it with a simple function like this:

```sh
doimport() {
    applabel="$1"
    namespace="$2"
    tarball="$3"
    container="$(kubectl get pods -n "$namespace" -l app="$applabel" -o jsonpath='{.items[*].metadata.name}')"
    if test -z "$container"; then
        echo "Could not find any containers in namespace '$namespace' with app label '$applabel'"
        return 1
    elif test "${container}" != "${container% *}"; then
        echo "Multiple containers in namespace '$namespace' match the app label '$applabel' (maybe an old deployment?): $container"
        return 1
    else
        echo "Copying '$tarball' to '$container'..."
        kubectl cp -n "$namespace" "$tarball" $container:/import/import.tar.gz -c import-data
        echo "Done copying, telling '$container' to start..."
        kubectl exec -n "$namespace" $container -c import-data -- touch /import/import-data-ready
    fi
}
```

Copy that into an interactive shell and run it like this:

```sh
doimport sabnzbd sabnzbd /path/to/sabnzbd.tar.gz
```

You can also use a script like this to reset import state (just deleting the import-data-complete file):

```sh
resetimport() {
    applabel="$1"
    namespace="$1"
    container="$(kubectl get pods -n "$namespace" -l app="$applabel" -o jsonpath='{.items[*].metadata.name}')"
    for c in $container; do
        kubectl exec -n "$namespace" $c -c import-data -- rm -f /import/import-data-complete
    done
}
```

After that, you'll need to delete the pod to force the initContainer to run again.
You may wish to just delete the entire deployment, wait a second, and reapply the deployment manifest.
