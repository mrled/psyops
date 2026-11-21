# github_sshkeys

Exclusively manage the SSH authentication keys on a GitHub account
(the authentication-key section of <https://github.com/settings/keys> ---
signing keys and repository deploy keys are not managed).

**Every authentication key not in the configured list will be deleted.**
An explicit `github_sshkeys_keys: []` removes every authentication key.

```sh
uv run --locked ansible-playbook _github_sshkeys.yml --check --diff
uv run --locked ansible-playbook _github_sshkeys.yml --diff
```

## Configuration

```yaml
github_sshkeys_username: your-github-login
github_sshkeys_token: "{{ vault_github_sshkeys_token }}"
github_sshkeys_keys:
  - "{{ lookup('ansible.builtin.file', '~/.ssh/id_ed25519.pub') }}"
  - "ssh-ed25519 AAAA... laptop"
```

Each entry must be a single public-key line with a nonempty comment,
for example `ssh-ed25519 AAAA... laptop`.
The full comment becomes the GitHub title;
leading and trailing whitespace is stripped, while internal whitespace is preserved.
Commentless keys and the object form (`title`/`key`) are rejected.

Create a fine-grained PAT with the account permission **Git SSH keys: read and write**.

## Tests

```sh
uv run --locked python -m unittest discover -s tests -p 'test_github_sshkeys.py'
```
