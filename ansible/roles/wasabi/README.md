# Wasabi bucket access

Creates a bucket, users, and bucket-scoped read-only/read-write groups.
Supply administrator credentials through `wasabi_root_access_key`
and `wasabi_root_secret_key` (provided by Ansible Vault in this repository).

```yaml
- role: wasabi
  wasabi_bucket: micahrl-seedboxk8s-krvb
  wasabi_prefix: SeedboxK8sKrvb
  wasabi_ro_users: []
  wasabi_rw_users:
    - SeedboxK8sKrvbBackupUser
```

`wasabi_bucket` and `wasabi_prefix` are required.
User lists default to empty.
The prefix names the `ReadOnly` and `ReadWrite` groups
and their `ReadOnlyAccess` and `ReadWriteAccess` policies.
Group membership matches the supplied lists; omitted users are removed
from these groups, but users and credentials are not deleted.

Optional settings:

- `wasabi_region`: `us-central-1`
- `wasabi_endpoint_url`: `https://s3.{{ wasabi_region }}.wasabisys.com`
- `wasabi_iam_endpoint_url`: `https://iam.wasabisys.com`

## Credentials

To create credentials, pass this once from `ansible/` and record the result.
Secrets cannot be retrieved later. Keep the output out of shared logs.

```sh
ansible-playbook _wasabi.yml \
  -e 'wasabi_create_keys=[SeedboxK8sKrvbBackupUser]'
```

Only listed RO/RW users can receive credentials.
Users with existing keys are refused; no keys are rotated or deleted.
Normal runs and check mode do not create credentials.
