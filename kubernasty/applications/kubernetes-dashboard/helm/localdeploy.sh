#!/bin/sh
set -eu

# Deploy this Helm release from the command line
# See /kubernasty/labnotes/content/docs/mantle/helm.md

scriptdir="$(dirname "$0")"
hr="$scriptdir"/HelmRelease.yaml
templated="$scriptdir"/localtemplated.yaml
values="$scriptdir"/values.yaml
chartname=$(yq .spec.chart.spec.chart "$hr")
namespace=$(yq .metadata.namespace "$hr")
version=$(yq .spec.chart.spec.version "$hr")
reponame=$(yq .spec.chart.spec.sourceRef.name "$hr")
repopath="$reponame"/"$chartname"
yq '.spec.values' "$hr" > "$values"
helm template $chartname --namespace $namespace --version $version $repopath --values "$scriptdir"/values.yaml > "$templated"
