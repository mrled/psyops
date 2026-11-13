# Jellyfin

Independent Jellyfin server in `tortuga`; existing Plex resources are unchanged.
Clients use Jellyfin's native accounts at `https://jellyfin.${productionClusterFqdn}`
through the existing Tailscale Traefik HTTPS entry point and wildcard certificate.
There is no Authelia middleware, NodePort, host port, or discovery service.
The existing `tortuga` policy allows Traefik ingress;
this directory adds only operator-namespace access to TCP 8096.
That namespace must remain dedicated to trusted operator workloads.

## Storage and identity

The official image reuses `${plexUid}` / `${plexGid}` for its UID/GID
and `${plexGid}` for its filesystem group,
the same identity that owns the shared media for Plex.
No root init container, host device mount, or service-account token is needed.

The entire `seedboxmedia-nfs-pvc` share is mounted read-write at `/media`,
matching Plex. The declared libraries select these directories:

| Share directory | Container path | Library/type |
| --- | --- | --- |
| `Movies` | `/media/Movies` | Movies / movies |
| `TV` | `/media/TV` | TV / tvshows |
| `KidsClips` | `/media/KidsClips` | KidsClips / homevideos |
| `Clips` | `/media/Clips` | Clips / homevideos |
| `Fitness` | `/media/Fitness` | Fitness / homevideos |
| `MST3K` | `/media/MST3K` | MST3K / movies |
| `MST3K-TV` | `/media/MST3K-TV` | MST3K-TV / tvshows |
| `NonfictionVideo` | `/media/NonfictionVideo` | NonfictionVideo / homevideos |
| `Shorts` | `/media/Shorts` | Shorts / homevideos |

These directories must already exist.
The library list is not a filesystem access boundary:
Jellyfin can access other directories on the share, including configuration and downloads,
and can write wherever the shared UID/GID has permission.
The operator matches libraries by name and reconciles their folders;
it does not remove undeclared libraries or change existing library types.

`jellyfin-config-pvc` is a separate 15Gi `seedbox-slow-mirror` volume,
with the existing backup-controller annotations.
The official image keeps its database, configuration, metadata, and logs under `/config`.
Both `/cache` and the default transcoding directory `/cache/transcodes`
are disk-backed `emptyDir` volumes; they are lost on pod replacement and not backed up.
Do not set a persistent custom transcoding path in the UI.
Monitor local ephemeral-disk usage during long or concurrent transcodes.
NFS real-time monitoring and trickplay generation are disabled;
the libraries request daily metadata refreshes, and manual/scheduled library scans remain available.

## Operator and credentials

`JellyfinConfig.yaml` uses the real `media-operator.dev/v1alpha1` schema from
[kyleseneker/media-operator v0.41.0](https://github.com/kyleseneker/media-operator/blob/v0.41.0/config/crd/bases/media-operator.dev_jellyfinconfigs.yaml).
It manages library paths, selected server/network settings, and encoding settings.
Kubernetes/Flux still owns the workload, storage, Service, and ingress.
Deleting the CR leaves application configuration in place (`deletionPolicy: orphan`).

Before enabling this Flux Kustomization:

1. The separate `media-operator` Flux Kustomization installs the upstream
   media-server Helm chart and its CRDs in namespace `media-operator`, watching `tortuga`.
   The chart enables Jellyfin and Plex controllers, but only this JellyfinConfig
   is declared; no other applications are adopted or configured.
   See `../media-operator/README.md` for chart RBAC and Secret-access scope.
2. `Secret.jellyfin-admin.yaml` supplies **`tortuga/jellyfin-admin`** through SOPS,
   with an initial `admin` username and a randomly generated password.
   Decrypt it locally with `sops decrypt` to retrieve the login;
   never commit plaintext credentials. The operator resolves both references in the CR's namespace;
   they are not mounted into the server.
3. Ensure the existing wildcard certificate and Jellyfin hostname/DNS are usable.

The operator completes the initial setup wizard and authenticates with those credentials.
On an already initialized volume they must match an existing administrator;
changing the Secret is not a guaranteed password-rotation mechanism.
Do not manually complete the wizard with different credentials.
The separate `jellyfin-ingress` Flux Kustomization waits for initialized,
successfully synced configuration before creating the HTTPS route on first bootstrap.
A missing Secret therefore blocks initial HTTPS exposure instead of exposing the wizard.
This gate does not retract an existing route if configuration later fails;
remove/suspend ingress before resetting the configuration volume to an empty state.
Cluster-internal traffic and administrator port-forwards remain trusted access paths.

## Readiness and rollout

Flux depends on `media-operator`, `fluxcfg`, `topolvm`, `tortuga`, and `intel-gpu-plugin`.
The `media-operator` Kustomization must exist separately or this rollout will stay blocked.
Flux waits for the StatefulSet and for the JellyfinConfig to be initialized and
`Synced=True` at the current observed generation.
The startup/readiness/liveness probes use `/health`.
Neither application configuration nor HTTP health proves successful hardware transcoding;
verify that separately after rollout.

## Intel QSV and sharing

The existing Intel device plugin advertises two shared `gpu.intel.com/i915` allocations.
Plex uses one; Jellyfin requests the other through its GPU limit.
These are shares of the same hardware, not performance or memory isolation.
A third consumer can leave Jellyfin Pending, and concurrent transcodes can contend.
No Plex restart or change is part of this deployment.

The plugin injects the DRM devices and runtime authorization.
`supplementalGroups: [992]` uses the render-device GID recorded for `tagasaw`
in `../plex/README.md`; unlike Plex's s6 startup, the official Jellyfin image
runs directly as the numeric user and preserves Kubernetes supplementary groups.
Check **both direct and by-path** device ownership and access on the deployed node.
GID 992 is host-specific, not a portable Linux `render` group number.
If the device owner is different, adjust the group list after checking it;
do not fix access by running privileged or chmod-ing host devices.

QSV decoding is enabled for H.264, HEVC (including Main10), MPEG-2,
VP8, and VP9 (including 10-bit), matching the host's reported decoding profiles.
VC-1 is not advertised by the host driver and remains disabled.
H.264 and HEVC output are allowed; AV1 encoding, range-extension decoding,
and Intel low-power encoder options remain disabled.
The host's iHD 25.2.3 `vainfo` advertises H.264 encoding only through
`VAEntrypointEncSliceLP`, and does not advertise HEVC encoding.
HEVC output permission is not proof that hardware encoding works:
check the container's bundled driver capabilities and test both output codecs.
Missing entrypoints may require investigating driver build/package or firmware support.
Intel VPP HDR-to-SDR tone mapping is enabled; the separate OpenCL tone mapper is disabled.
VPP uses fixed-function hardware with lower power consumption and fewer tuning options.
OpenCL offers more tuning and Dolby Vision P5 support, but adds a compute-runtime dependency.
The official image includes that runtime; leaving OpenCL disabled is an initial policy choice,
not a claim that this GPU cannot use it.
This avoids assuming AV1 capability or HuC firmware/low-power support.
Actual QSV/VPP support still requires validation on this host and driver stack.
Subtitle burn-in, Dolby Vision, unusual profiles, and fallback paths need separate tests.

## Image pin and offline checks

GitHub's latest stable release was **v12.4** when checked on 2026-11-12.
Docker Hub's official `jellyfin/jellyfin:12.4` tag (amd64/arm64)
and `latest` both resolved to the pinned multi-platform SHA256 in `StatefulSet.yaml`.
Sources: [GitHub release](https://github.com/jellyfin/jellyfin/releases/tag/v12.4),
[registry tag API](https://hub.docker.com/v2/repositories/jellyfin/jellyfin/tags/12.4).
The CR schema is validated against v0.41.0, but live operator compatibility with
this Jellyfin release is not established by schema validation alone.

From the repository root:

```bash
# Extract the schema from the same published chart used by Flux.
helm show crds \
  oci://ghcr.io/kyleseneker/media-operator/media-operator-mediaservers \
  --version 0.41.0 > /tmp/media-operator-crds.yaml
uv run --no-project --with pyyaml --with jsonschema python -c \
  'import yaml; docs=yaml.safe_load_all(open("/tmp/media-operator-crds.yaml")); print(yaml.safe_dump(next(d for d in docs if d and d["metadata"]["name"] == "jellyfinconfigs.media-operator.dev")))' \
  > /tmp/jellyfin-crd.yaml
uv run --no-project --with pyyaml --with jsonschema \
  python seedboxk8s/applications/jellyfin/test_manifests.py /tmp/jellyfin-crd.yaml
kubectl kustomize seedboxk8s/applications/jellyfin
flux build kustomization jellyfin --dry-run \
  --path ./seedboxk8s/applications/jellyfin \
  --kustomization-file ./seedboxk8s/fluxroot/kustomizations/jellyfin.yaml
```

The tests reject unknown CR spec fields as well as schema/type errors,
and check mount isolation, identity, credentials, ingress, network policy, and dependencies.
Flux dry-run skips Secret/ConfigMap substitutions; it does not verify cluster readiness.

## Live acceptance tests (not run by the offline checks)

```bash
kubectl -n tortuga rollout status statefulset/jellyfin
kubectl -n tortuga get jellyfinconfig jellyfin -o yaml
kubectl -n tortuga logs jellyfin-0
kubectl -n tortuga exec jellyfin-0 -- id
kubectl -n tortuga exec jellyfin-0 -- ls -l /dev/dri /dev/dri/by-path
kubectl -n tortuga exec jellyfin-0 -- sh -c \
  'exec 3<>/dev/dri/renderD128 && echo render-device-open-ok'
# Confirm the full share and representative library directories are readable.
kubectl -n tortuga exec jellyfin-0 -- ls -la /media /media/Movies /media/TV /media/KidsClips
```

Log in through the HTTPS hostname with the native admin account.
Verify the nine declared managed libraries and scan representative files.
Use a non-admin account for ordinary playback.
Force a controlled HEVC Main10 HDR-to-H.264 SDR transcode without subtitle burn-in;
confirm `hevc_qsv`, `h264_qsv`, and VPP tone mapping in Jellyfin's FFmpeg log,
not merely successful playback or a green health probe.
Check GPU activity and verify Plex playback still works, including a concurrent test.
The media share is writable; never modify or delete existing media as a permission test.
Review config-volume backup/restore separately before relying on this deployment.
