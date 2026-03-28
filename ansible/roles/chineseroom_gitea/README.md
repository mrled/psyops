# chineseroom_gitea

Installs and configures a Gitea instance as a GitHub mirror server.

## What it does

- Installs the Gitea binary and systemd service
- Configures nginx reverse proxy (trusted subdomain, uses chineseroom wildcard cert)
- Creates two automatic service accounts with generated passwords and tokens:
  - `chineseroom-admin` — Ansible API admin; credentials in `$data_dir/chineseroom-admin.{password,token}`
  - `mirrorbot` — authenticates working clone git operations; credentials in `$data_dir/mirrorbot.{password,token}`
- Creates the `mirror` org to own all mirrored repos, with three teams:
  - `administrators` — org admin access; `mirrorbot` is a member. Can manage repos, webhooks, and settings.
  - `readwrite` — write access; for human admin users who can push directly and merge PRs.
  - `readonly` — read access; for restricted users who fork and open cross-repo PRs.
- Creates application users from `chineseroom_gitea_users` (passwords vault-backed, SSH keys via API)
- Assigns users to org teams via the `orgs` field (see below)
- Mirrors GitHub repos defined in `chineseroom_gitea_github_mirrors`:
  - Creates Gitea repo `mirror/github--OWNER--REPO`
  - Sets up a working clone at `$mirrors_dir/github--OWNER--REPO` with two remotes (`origin` = local Gitea HTTP, `github` = GitHub SSH)
  - Configures a Gitea push webhook → pushes branches back to GitHub on any Gitea push
  - Pull timer syncs from GitHub on a schedule (default: every 15 minutes)
  - Clones to restricted user at `~/repo/github.com/OWNER/REPO` over SSH
  - Adds optional sandbox nginx entries via `domain_map`

## GitHub sync

### Pull: GitHub → Gitea (timer-driven)

A systemd timer runs the pull script on a schedule. On each run, it queries the Gitea API to discover all repos in the `mirror` org — so newly added repos are picked up automatically without re-running Ansible.

For each repo the script:

1. Fetches all branches from GitHub verbatim into Gitea:
   - `refs/heads/main` on GitHub → `refs/heads/main` in Gitea
   - Uses `--prune` so branches deleted on GitHub are also removed from Gitea
2. Fetches all tags from GitHub and force-overwrites them in Gitea (so moved tags follow GitHub)
3. Fetches all LFS objects from GitHub and pushes them to Gitea

### Push: Gitea → GitHub (webhook-driven)

When any branch is updated in Gitea, Gitea sends a push webhook to the local receiver service. The receiver:

1. Validates the HMAC-SHA256 signature
2. Checks that the repo has auto-push enabled (`.git/gitea/auto-push` marker file)
3. Fires the push script asynchronously for any `refs/heads/` ref

The push script pushes the branch verbatim to GitHub:
- `refs/heads/main` in Gitea → `refs/heads/main` on GitHub

LFS objects are pushed to GitHub after each branch push.

To disable auto-push for a specific repo, remove the `.git/gitea/auto-push` file from its working clone directory.

## Review workflow

The intended flow for the restricted user to propose changes:

1. The restricted user (in `readonly` team) forks a `mirror` org repo into their own namespace
2. They push changes to their fork and open a cross-repo PR targeting the `mirror` org repo
3. A user in the `readwrite` team reviews and merges the PR
4. The merge triggers the webhook, which pushes the branch to GitHub

## User team assignment

The `orgs` field in `chineseroom_gitea_users` accepts a dict of org name → team list:

```yaml
chineseroom_gitea_users:
  - username: alice
    email: alice@example.com
    password: "{{ vault_alice_password }}"
    orgs:
      mirror: [readwrite]
  - username: bob
    email: bob@example.com
    password: "{{ vault_bob_password }}"
    orgs:
      mirror: [readonly]
```

## First-run notes

- Service account tokens are generated once and cached on disk; delete the files to rotate.
- The admin token file must be present before SSH keys can be added to users (chicken-and-egg on a blank install — run the playbook twice if needed, or create users first).
- Restricted-user repo clones are skipped gracefully if the Gitea repo is empty (before the first GitHub pull).
