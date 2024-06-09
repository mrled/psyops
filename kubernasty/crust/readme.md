# Cruster manifests

These do not depend on Flux kustomization substitutions --
everything here can be directly applied with `kubectl apply -f ...` for individual manifsts
or `kubectl apply -k ...` for a directory containing a `kustomization.yaml`.

Before doing so, secrets must be decrypted with `sops --decrypt --in-place ./path/to/Secret.yaml`,
and of course re-encrypted before any commits.

Helm repositories must be deployed via the `helm` command when not using Flux.

This is to make development faster.
