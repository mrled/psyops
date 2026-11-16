# Intel GPU device plugin

Deploys Intel's GPU device plugin on the Kubernetes node.

- Expose the Intel GPU as a consistent path inside containers, with correct permissions.
- Note: The device-plugin socket directory is `/var/lib/kubelet/device-plugins` on the host and container;
  k0s's `/var/lib/k0s/kubelet` root applies to CSI paths, not this API.
- Expose a limited number of slots with `--shared-dev-num`, which dependent pods must request.
- No isolation between pods that use the GPU.
- Use `-bypath=all` to mount the DRM by-path directory intact,
  which preserves symlinks to allocated device nodes.
  (May need to change this if we ever have more than one GPU.)
- Dependent pods depend on this deployment's DaemonSet health check.
- Some apps (Jellyfin, ErsatzTV) use the shared `renderGid` setting for Unix render-device permissions;
  Plex discovers this at startup and changes its own settings with a hook.
- Dependent containers don't need a manual `/dev/dri` mount.
- Existing pod mounts are not updated by a plugin restart,
  so making updates to the plugin requires recreating dependent pods afterwards.

## Verification after Flux deployment

```bash
kubectl -n kube-system rollout status daemonset/intel-gpu-plugin
kubectl -n kube-system logs daemonset/intel-gpu-plugin
kubectl get node tagasaw.home.micahrl.com -o jsonpath='{.status.allocatable.gpu\.intel\.com/i915}{"\n"}'
kubectl -n tortuga rollout status statefulset/plex
# The render entry should be a symlink to `../renderD128`, not a character device.
kubectl -n tortuga exec plex-0 -c pms -- ls -l /dev/dri/by-path/
```

## Upstream

- [Deployment](https://github.com/intel/intel-device-plugins-for-kubernetes/blob/v0.37.1/deployments/gpu_plugin/base/intel-gpu-plugin.yaml)
- [Configuration and sharing](https://github.com/intel/intel-device-plugins-for-kubernetes/blob/v0.37.1/cmd/gpu_plugin/README.md)
