# Foundation manifests

These do not depend on Flux kustomization substitutions --
everything here can be directly applied with `kubectl apply -f ...` for individual manifsts
or `kubectl apply -k ...` for a directory containing a `kustomization.yaml`.
