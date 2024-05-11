# seedboxk8s cluster

This Kubernetes cluster is deployed by the progfiguration_blacksite role `seedboxk8s`.
It uses Flux for gitops application deployments.
Flux is declarative, so the end state should be the same
whether the cluster is new or has already applied all these manifests.

## Layout

```text
/repository root
    /seedboxk8s             This directory
        /fluxroot           Flux is bootstrapped with --path pointing here
            /flux-system    Flux creates this directory and manages its contets
            /kustomizations Our kustomizations
                /app1.yaml  Points to app1 in the applications directory below
                /app2.yaml  ...
            /helmrepos      Helm repositories to install
                /helm1.yaml ...
            /configmaps     ConfigMaps to apply
                /cm1.yaml   ...
        /applications       Kustomizations in fluxroot point to subdirs of this
            /app1           Contains manifests to deploy app    1
            /app2           ...
            /...            ...
```

Inside `fluxroot`, Flux itself owns the `flux-system` directory.
The other directories contain manifests specific to our cluster.
Flux applies all the manifests in `fluxroot` as soon as they change,
so we define our applications outside of this directory
so that we can control inter-app dependencies.
We do declare some Helm repos in `fluxroot` because they're global
and because more than one app might use a given Helm repo,
and allow for simple ConfigMap delcarations for cluster-wide configuration.
Everything else is placed inside `applications/`
and is referenced by one of the Kustomizations.

## Kustomizations in fluxroot/seedboxk8s repository

Here's an example

```yaml
# Note the fluxcd-specific Kustomization API version
apiVersion: kustomize.toolkit.fluxcd.io/v1beta1
kind: Kustomization
metadata:
  # Other Kustomizations can depend on this one by its name
  name: traefik
  # All of the Kustomizations found in fluxroot will use the flux-system namespace
  namespace: flux-system
spec:
  # Here it depends on a different Kustomization
  dependsOn:
    - name: cert-manager-config
  interval: 15m
  # The path to the files for this Kustomization -- how the app is defined
  path: /seedboxk8s/applications/traefik
  prune: true
  timeout: 2m
  # The Git repository containing the path to the files for this Kustomization.
  # The default Git repo is called flux-system;
  # we will only have one so we just use that.
  sourceRef:
    kind: GitRepository
    name: flux-system
  # The app can use secrets by the sops provider,
  # decrypted by the age key in the sops-age secret
  decryption:
    provider: sops
    secretRef:
      name: sops-age
  validation: server
  # A Kustomize feature that allows writing simple variable transformations.
  # This is where the ConfigMap objects in `fluxroot` come in handy.
  # The configmap will contain key/value pairs like `foo: bar`,
  # and any YAML manifest in the application directory can reference the key like
  # `https://${foo}.example.com` which Kustomize will replace with
  # `https://bar.example.com` transparently.
  postBuild:
    substituteFrom:
      - kind: ConfigMap
        name: example-config-map
```

## Dependencies

Make sure that kustomizations which define CRDs
are dependencies of any kustomization which uses the CRDs.
This means you may need to break up directories into two --
for instance, the first one might install a Helm chart that includes CRDs,
and the second one can make resources from those CRDs.
