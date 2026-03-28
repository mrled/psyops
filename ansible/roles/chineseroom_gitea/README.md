# chineseroom_gitea

Installs and configures a Gitea instance as a GitHub mirror server.

## What it does

- Installs the Gitea binary and systemd service
- Configures nginx reverse proxy (trusted subdomain, uses chineseroom wildcard cert)
- Creates two automatic service accounts with generated passwords and tokens:
  - `chineseroom-admin` — Ansible API admin; credentials in `$data_dir/chineseroom-admin.{password,token}`
  - `mirrorbot` — authenticates working clone git operations; credentials in `$data_dir/mirrorbot.{password,token}`
- Creates the `mirror` org to own all mirrored repos, with two teams:
  - `trusted` — can push to `protected/*`, approve PRs, and merge. `mirrorbot` is a member.
  - `untrusted` — read/write access, subject to branch protection rules.
- Creates application users from `chineseroom_gitea_users` (passwords vault-backed, SSH keys via API)
- Assigns users to org teams via the `orgs` field (see below)
- Mirrors GitHub repos defined in `chineseroom_gitea_github_mirrors`:
  - Creates Gitea repo `mirror/OWNER--REPO`
  - Applies `protected/*` branch protection (see below)
  - Sets up a working clone at `$mirrors_dir/OWNER--REPO` with two remotes (`origin` = local Gitea, `github` = GitHub SSH)
  - Configures a Gitea push webhook → auto-pushes to GitHub on default branch updates
  - Pull timer syncs from GitHub every 15 minutes
  - Clones to restricted user at `~/repo/github.com/OWNER/REPO` over SSH
  - Adds optional sandbox nginx entries via `domain_map`

## Branch protection on `protected/*`

The `protected/*` branch namespace is intended for branches that will eventually be synced with GitHub. The protection rules enforce a review workflow:

- **Untrusted users** can push branches and open PRs, but cannot merge.
- **Trusted users** (members of the `trusted` team) can push, force-push, approve PRs, and merge.
- 1 approval from the `trusted` team is required before a PR can be merged.

This lets untrusted contributors propose changes via PR while ensuring only trusted users can land them.

## User team assignment

The `orgs` field in `chineseroom_gitea_users` accepts a dict of org name → team list:

```yaml
chineseroom_gitea_users:
  - username: alice
    email: alice@example.com
    password: "{{ vault_alice_password }}"
    orgs:
      mirror: [trusted]
```

## First-run notes

- Service account tokens are generated once and cached on disk; delete the files to rotate.
- The admin token file must be present before SSH keys can be added to users (chicken-and-egg on a blank install — run the playbook twice if needed, or create users first).
- Restricted-user repo clones are skipped gracefully if the Gitea repo is empty (before the first GitHub pull).
