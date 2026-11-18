# ssh_authorized_keys

Fully manage the default `~/.ssh/authorized_keys` file for existing accounts.

- Requires root to manage other users
- Prototype batch module: one remote invocation for all configured users,
  with a managed header and Python-side validation before writing any files.
- Accepts plain RSA, Ed25519, and NIST ECDSA public keys with optional comments,
  including OpenSSH Ed25519 and ECDSA security-key types.
  Key options and certificates are not supported.
  Validation checks encoding and key-type consistency, not cryptographic validity.
- Supports check mode, content and ownership/permission diffs with `--diff`,
  and atomic replacement of each file, but not batch rollback.
  Symlinked SSH directories or authorized-key files are rejected.
- Prototype trust boundary: managed accounts must be trusted as root.
  Path checks do not protect against a user concurrently swapping directories or symlinks.

Set `ssh_authorized_keys_header` to customize the header text without comment markers.
It defaults to `ansible_managed` when defined, otherwise `Ansible managed`.
Each line is prefixed with `# `; use an empty string to omit the header.
Unlike the template module, this role does not expand template-specific managed-header macros.

```yaml
ssh_authorized_keys_users:

  # Set a comment header in the authorized_keys file (optioknal)
  header: "{{ ansible_managed | default('Ansible managed') }}"

  # Set root's keys
  root:
    - qwerasdfzxcfv...

  # Set another user's keys
  micahrl: "{{ global_personal_ssh_keys }}"

  # If a user isn't present, it is not managed.
  # Removing a user from this list stops managing its keys (without deleting anything).
  # unmanaged_user: []

  # If a user's list is empty, all its keys are DELETED
  other_user: []
```
