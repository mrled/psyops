# chineseroom_gitea

Installs and configures a Gitea instance as a GitHub mirror server.

## What it does

- Installs the Gitea binary and systemd service
- Configures nginx reverse proxy (trusted subdomain, uses chineseroom wildcard cert)
- Creates two automatic service accounts with generated passwords and tokens:
  - `chineseroom-admin` — Ansible API admin; credentials in `$data_dir/chineseroom-admin.{password,token}`
  - `github` — owns mirror repos and authenticates working clones; credentials in `$data_dir/github-user.{password,token}`
- Creates application users from `chineseroom_gitea_users` (passwords vault-backed, SSH keys via API)
- Mirrors GitHub repos defined in `chineseroom_gitea_github_mirrors`:
  - Creates Gitea repo `github/OWNER--REPO`
  - Sets up a working clone at `$mirrors_dir/OWNER--REPO` with two remotes (`origin` = local Gitea, `github` = GitHub SSH)
  - Configures a Gitea push webhook → auto-pushes to GitHub on default branch updates
  - Pull timer syncs from GitHub every 15 minutes
  - Clones to restricted user at `~/repo/github.com/OWNER/REPO` over SSH
  - Adds optional sandbox nginx entries via `domain_map`

## First-run notes

- Service account tokens are generated once and cached on disk; delete the files to rotate.
- The admin token file must be present before SSH keys can be added to users (chicken-and-egg on a blank install — run the playbook twice if needed, or create users first).
- Restricted-user repo clones are skipped gracefully if the Gitea repo is empty (before the first GitHub pull).
