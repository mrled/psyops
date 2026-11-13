# psyops AGENTS.md

This repo contains the infrastructure for running services.

See README.md for directory map

## Documentation and comments

- Don't add documentation that ages like milk: "this is the latest version of the package" etc
- Be careful about strongly coupled documentation. Sometimes it is appropriate like "this MUST match the string that is over in ../other/file.txt", but if this kind of thing can be avoided, all the better. Consider carefully whether coupled documentation should be 1) avoided altogether, 2) have just one side reference another, or 3) have both sides reference each other.

## Ansible

- In a sandbox with a different checkout path, set `UV_PROJECT_ENVIRONMENT` outside the checkout (e.g. `/tmp/psyops-ansible-checks`).
  Never sync the shared `ansible/.venv`: this rewrites its console-script shebangs with sandbox-only paths.

- Be conscious of roundtrips in Ansible tasks
  - Suggest writing script blocks when task files get long and the Ansible modules do not provide much useful abstraction
  - Suggest writing Ansible plugins when task files get long and script blocks are too long, or are hard to read
