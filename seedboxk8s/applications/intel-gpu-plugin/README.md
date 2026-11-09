# Intel GPU device plugin

Deploys Intel's GPU device plugin on the Kubernetes node.
The device-plugin socket directory is `/var/lib/kubelet/device-plugins`
on both the host and in the container.
Kubernetes fixes this path independently of kubelet's root directory;
k0s's `/var/lib/k0s/kubelet` root applies to CSI paths, not this API.
The integrated GPU is exposed as two shared `gpu.intel.com/i915` allocations.
Sharing grants concurrent access, not GPU performance or memory isolation.

The plugin uses `-bypath=all` to mount the DRM by-path directory intact,
preserving symlinks to the allocated device nodes.
The default `single` mode mounts each symlink target separately,
which can retain different ownership from the direct device nodes
and prevent Intel OpenCL from opening the GPU even when VA-API works.
`all` exposes by-path names for every host GPU;
runtime device authorization still applies to the targets.
This is suitable for this single-GPU host;
revisit the discovery/isolation implications if more GPUs are added.

Plex's Flux Kustomization depends on this deployment's DaemonSet health check.
A healthy DaemonSet does not by itself prove GPU discovery succeeded:
verify the node's allocatable resources before diagnosing a Pending Plex pod.

## Verification after Flux deployment

Run with an administrative kubeconfig on tagasaw:

```bash
kubectl -n kube-system rollout status daemonset/intel-gpu-plugin
kubectl -n kube-system logs daemonset/intel-gpu-plugin
kubectl get node tagasaw.home.micahrl.com \
  -o jsonpath='{.status.allocatable.gpu\.intel\.com/i915}{"\n"}'
kubectl -n tortuga rollout status statefulset/plex
```

The node should advertise `2` allocations.
Plex's container requests one through its GPU limit;
Kubernetes defaults the corresponding request to the same value.
Do not add a manual `/dev/dri` mount to Plex:
the device plugin supplies the devices and runtime access permissions.

When changing by-path mounting, wait for the plugin rollout first,
then recreate Plex to obtain a new device allocation and mounts.
Existing pod mounts are not updated by a plugin restart.
Run these administrative commands only when ready to interrupt playback:

```bash
kubectl -n kube-system rollout status daemonset/intel-gpu-plugin
kubectl -n tortuga rollout restart statefulset/plex
kubectl -n tortuga rollout status statefulset/plex
kubectl -n tortuga exec plex-0 -c pms -- ls -l /dev/dri/by-path/
```

The render entry should be a symlink to `../renderD128`, not a character device.

Check access without initiating playback:

```bash
kubectl -n tortuga exec plex-0 -c pms -- \
  su -s /bin/sh plex -c \
  'exec 3<>/dev/dri/renderD128 && exec 4<>/dev/dri/by-path/pci-0000:00:02.0-render && echo render-device-open-ok'
```

Opening the device successfully verifies access, not VA-API initialization.
Confirm hardware acceleration separately in Plex's playback dashboard and logs
with a controlled transcode after the memory limit is deployed.
If the device opens but VA-API still fails,
investigate Plex's userspace drivers rather than broadening pod privileges.

## Upstream

- [Deployment](https://github.com/intel/intel-device-plugins-for-kubernetes/blob/v0.37.1/deployments/gpu_plugin/base/intel-gpu-plugin.yaml)
- [Configuration and sharing](https://github.com/intel/intel-device-plugins-for-kubernetes/blob/v0.37.1/cmd/gpu_plugin/README.md)
