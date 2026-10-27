# psyops AGENTS.md

This repo contains the infrastructure for running services.

See README.md for directory map

## Ansible

- In a sandbox with a different checkout path, set `UV_PROJECT_ENVIRONMENT` outside the checkout (e.g. `/tmp/psyops-ansible-checks`).
  Never sync the shared `ansible/.venv`: this rewrites its console-script shebangs with sandbox-only paths.

- Be conscious of roundtrips in Ansible tasks
  - Suggest writing script blocks when task files get long and the Ansible modules do not provide much useful abstraction
  - Suggest writing Ansible plugins when task files get long and script blocks are too long, or are hard to read
