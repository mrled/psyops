---
title: Container registry
---

I would like a simple registry.

* Insecure is fine, as we trust the Kubernetes network.
* We don't want to have to deal with public certs.
    * But we would like to be able to enable them later.
* We can have just a few manually created service accounts that can push images to it,
  but we want to prevent unauthenticated clients from pushing.

## HTTPS is enforced by all the clients

If you want to use an unencrypted HTTP or untrusted HTTPS server,
each client has a different way to configure this,
sometimes changing from version to version,
and sometimes not well implemented.

## Troubleshooting

```sh
k run tmpalpine -it --image=alpine:latest -- /bin/sh
```

And then

```sh
apk add curl mount cri-tools podman buildah vim fuse-overlayfs
```

You need fuse-overlayfs or you'll get errors running `buildah` and `podman` like
`'overlay' is not supported over overlayfs`.

## Insecure registries

In a normal system,
like the troubleshooting container above, add the following to
`/etc/containers/registries.conf`.
If you want to use insecure registries for containers running on a k0s cluster,
k0s has special support for configuration snippets,
so you can drop the following inside a new file under
`/etc/k0s/containerd.d/ANYTHING.conf`.

```toml
[[registry]]
# This looks for a service called "registry" inside a namespace called "registry" in the local cluster
location = "registry.registry.svc.cluster.local"
insecure = true
```

Then try

```sh
# Unauthenticated
buildah --debug --tls-verify=false pull registry.registry.svc.cluster.local/clustergit:latest

# Authenticated
buildah --debug --tls-verify=false pull --creds=USERNAME:PASSWORD registry.registry.svc.cluster.local/clustergit:latest
```

**VERY DUMB ISSUE**: It tries `https` first even though it's allowed to do `http`.
It waits for fucking https to time out!!!! Killing me.
Even though we've already allowed HTTP pulls in `registries.conf`,
and even though we're passing `--tls-verify=false`.

<https://github.com/containers/buildah/issues/5531>

(Actually, `--tls-verify=false` doesn't help here,
because `insecure = true` in `registries.conf`.
We can omit it.)

You can also use an environment variable instead of modifying the registries.conf file:

```sh
export BUILD_REGISTRY_SOURCES="{\"insecureRegistries\": [\"registry.registry.svc.cluster.local\"], \"blockedRegistries\": [], \"allowedRegistries\": []}"
```

## Internal CAs

`buildah` (and I think `podman` too)
looks for certificate information under
`/etc/containers/certs.d/REGISTRY/ca.crt`.
For instance,
`/etc/containers/certs.d/registry.registry.svc.cluster.local/ca.crt`.

For k0s, you can save this on the node and pass it as `extraArgs` to the controllers and workers in `k0s.yaml`.

```yaml
apiVersion: k0s.k0sproject.io/v1beta1
kind: ClusterConfig
metadata:
  name: k0s
spec:
  api:
    address: 192.168.0.1
    sans:
      - 192.168.0.1
  controllerManager:
    extraArgs:
      - --root-ca-file=/var/lib/k0s/pki/internal-ca.crt
  controllerProfiles:
    default:
      extraArgs:
        - --root-ca-file=/var/lib/k0s/pki/internal-ca.crt
  workerProfiles:
    default:
      extraArgs:
        - --root-ca-file=/var/lib/k0s/pki/internal-ca.crt
```

You should be able to use `ClusterConfig` manifests for this,
[like this](https://docs.k0sproject.io/head/configuration/),
but I haven't tried that yet.
