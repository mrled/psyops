---
title: Helm and local deployments
weight: 60
---

Flux supports deploying Helm charts,
and requires the `values.yaml` be either inlined into the `HelmRelease` resource
or in a separate `ConfigMap`.

We also want to allow local Helm deployments so that we can iterate in development without having to push to the repo.
To do that we need a small script:

```sh
#!/bin/sh
set -eu

# Deploy this Helm release from the command line
# See /kubernasty/labnotes/content/docs/mantle/helm.md

scriptdir="$(dirname "$0")"
hr="$scriptdir"/HelmRelease.yaml
chartname=$(yq .spec.chart.spec.chart "$hr")
namespace=$(yq .metadata.namespace "$hr")
version=$(yq .spec.chart.spec.version "$hr")
reponame=$(yq .spec.chart.spec.sourceRef.name "$hr")
repopath="$reponame"/"$chartname"
yq '.data.values' "$scriptdir"/HelmRelease.yaml > "$scriptdir"/values.yaml
helm upgrade --install $chartname --namespace $namespace --version $version $repopath --values "$scriptdir"/values.yaml
rm "$scriptdir"/values.yaml
```

A note for shell and POSIX enthusiasts:
POSIX doesn't provide a very robust way to determine the path to a script,
particularly when the script will be installed to `$PATH`,
but that's OK for this script,
which will only ever be called from a relative path like `./crust/whatever/helmdeploy.sh`.
