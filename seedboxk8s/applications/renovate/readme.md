# Renovate

## Automerge policy

We allow safe automerges

- Minor/patch updates for most things
- Some sensitive things no auto updates at all
- Some safe things allow any update

See `ConfigMap.renovate-config.yaml`.

## Manual run

The CronJob runs on its configured schedule.
To trigger Renovate immediately:

```sh
job="renovate-manual-$(date +%Y%m%d%H%M%S)"

# Start
kubectl -n renovate create job --from=cronjob/renovate "$job"

# Inspect
kubectl -n renovate logs -f "job/$job"
kubectl -n renovate get jobs,pods
kubectl -n renovate describe job "$job"
```

## Private Tor image

The renderer resolves `${productionClusterFqdn}` in the Tor image name
using the reflected `seedboxk8s-config` Secret.
A regex manager preserves the literal Flux substitution in the manifest
while looking up the concrete private-registry image.
Tor image digest pins and updates are eligible for automerge.

The job mounts the reflected `registry-k8s-dockerconfigjson` pull Secret read-only
and converts its credentials into a Docker `hostRules` entry at runtime.
The generated `/tmp/renovate-config.json` contains those credentials;
do not print or publish it.
No additional Kubernetes API permissions are needed.

See `../tor/readme.md` for the daily image-build schedule.

## GitHub App credentials

`Secret.renovate-env.yaml` contains encrypted GitHub App credentials.
To update it, edit the decrypted values, then encrypt the file with SOPS before committing:

```sh
sops --encrypt --in-place seedboxk8s/applications/renovate/Secret.renovate-env.yaml
```

Create the GitHub App:

- Go to GitHub -> Settings -> Developer settings -> GitHub Apps -> New GitHub App.
- App name: `psyops-renovate`, or another unique name.
- Homepage URL: `https://github.com/mrled/psyops`, or another valid URL.
- Disable webhooks.
- Installable by: only this account, unless broader installation is intentional.
- After creation, record the App ID.
- Generate and download a private key, then use the full PEM as `GITHUB_APP_PRIVATE_KEY`.
- Install the App on only the `mrled/psyops` repository.
- The CronJob discovers the installation ID from the `mrled/psyops` repository at runtime.

If the manual job logs `GitHub App JWT validation failed`,
check that `GITHUB_APP_ID` is the App ID, not the Client ID,
and that `GITHUB_APP_PRIVATE_KEY` is a private key generated for that same App.
If it logs `GitHub App installation lookup failed`,
check that the App is installed on `mrled/psyops`.

GitHub App repository permissions:

- Metadata: Read-only; GitHub grants this automatically.
- Contents: Read and write; required to create Renovate branches and commits.
- Pull requests: Read and write; required to open and update PRs.
- Issues: Read and write; required for the Dependency Dashboard issue.
- Commit statuses: Read and write; useful for Renovate status updates.
- Checks: Read and write; recommended by Renovate for GitHub App setups.
- Workflows: Read and write; needed if Renovate updates files under `.github/workflows`.
- Administration: Read-only; recommended by Renovate for GitHub App setups.
- Dependabot alerts: Read-only; optional.

GitHub App organization permissions, if available or relevant:

- Members: Read-only.

`Contents: Read and write` lets the App push commits and branches.
Protect `master` or `main` with GitHub branch protection or rulesets,
and do not allow this App to bypass those protections,
so Renovate can push `renovate/*` branches but cannot commit directly to the protected branch.

Renovate OSS expects `RENOVATE_TOKEN` to be a short-lived GitHub App installation token,
not these App credentials directly.
The Renovate CronJob uses the script mounted at `/etc/renovate/github-app-token.js`
to exchange the GitHub App credentials for `RENOVATE_TOKEN`
immediately before running Renovate.
