# ssh_authorized_keys

Fully manage the default `~/.ssh/authorized_keys` file for existing accounts.

- Requires root to manage other users

```yaml
ssh_authorized_keys_users:
  root:
    - qwerasdfzxcfv...
  micahrl: "{{ global_personal_ssh_keys }}"

  # If a user isn't present, it is not managed.
  # Removing a user from this list stops managing its keys (without deleting anything).

  # If a user's list is empty, all its keys are DELETED
  other_user: []
```
