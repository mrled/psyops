# urestic

Scheduled personal-data backups to S3-compatible storage using restic user services.
Requires Linux, systemd 256+ with TPM2 support, restic 0.17+, and a usable TPM2 device.
The role installs prerequisites, enables the credential broker and user lingering
(for runs without a login). The account and S3 bucket must already exist.
Apply with `become: true` and gathered facts.

## Configuration

Keep secrets in Ansible Vault:

```yaml
urestic_user: alice
urestic_jobs:
  - name: job1
    oncalendar: '*-*-* 02:00:00'
    repository: s3:https://s3.example.com/my-bucket/alice/job1
    password: '{{ vault_restic_password }}'
    aws_access_key_id: '{{ vault_s3_access_key_id }}'
    aws_secret_access_key: '{{ vault_s3_secret_access_key }}'
    paths:
      /home/alice/Documents:
      /mnt/private-data:
        mountpoint: true
    excludes: ['*.bak', .DS_Store]
```

Job names must be unique and contain letters, numbers, underscores, or hyphens
(not starting with a hyphen). Paths must be absolute. Every `mountpoint: true`
path adds a `ConditionPathIsMountPoint=`; if any is unmounted, that backup is skipped.
Backups use `--exclude-caches` to honor valid `CACHEDIR.TAG` markers.
Timers catch up after downtime and default to a randomized delay of 15 minutes.
See [defaults/main.yml](defaults/main.yml) for overrides.

Per-job files live in `~/.config/psyops/backup/JOB/`: `restic.paths`,
`restic.excludes`, and `restic.repository`. Ansible overwrites local edits on reapply.
Units live in `~/.config/systemd/user/`, named `urestic@JOB.service` and `.timer`.
As the backup user:

```sh
systemctl --user list-timers --all 'urestic@*'
systemctl --user status urestic@job1.service
systemctl --user start urestic@job1.service
journalctl --user -u urestic@job1.service
```

## Repository access

Backups initialize missing repositories automatically, only when restic reports
exit code 10. Wrong passwords, access errors, and other failures stop the backup
without attempting initialization. The S3 bucket must already exist.

Browse and restore with plain restic on any machine—no systemd or original TPM
required. Use the original credentials from Vault or your password manager, not
the sealed files. Replace the placeholders below; avoid saving real secrets in
shell history. Choose either restore example; neither overwrites the original files.

```sh
export RESTIC_REPOSITORY='s3:https://s3.us-central-1.wasabisys.com/YOUR_BUCKET/YOUR_PREFIX'
export AWS_ACCESS_KEY_ID='YOUR_WASABI_ACCESS_KEY_ID'
export AWS_SECRET_ACCESS_KEY='YOUR_WASABI_SECRET_ACCESS_KEY'
export RESTIC_PASSWORD='YOUR_RESTIC_REPOSITORY_PASSWORD'

# List snapshots, then inspect files in the latest (or substitute a snapshot ID).
restic snapshots
snapshot=latest
restic ls "$snapshot"

# Restore the entire snapshot and verify the restored contents.
restic restore "$snapshot" --target "$HOME/restored-full" --verify

# Restore just Documents; use its original snapshot path, even on another machine.
restic restore "$snapshot" --target "$HOME/restored-partial" \
  --include '/home/mrl/Documents' --verify

unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY RESTIC_PASSWORD RESTIC_REPOSITORY
```

Use your bucket's Wasabi region and exact repository prefix. Restored paths retain
their directory hierarchy beneath the target.

## Important limits

- Secrets are user-scoped and sealed with `host+tpm2` under each job's `credentials/`,
  using PCR 7 by default. **Keep independent recovery copies**: TPM, OS host-key,
  account, or Secure Boot changes can prevent decryption. Undecryptable credentials
  fail deployment; there is no non-TPM fallback.
- Changing the inventory password does **not** change the repository password.
  Changing PCR settings alone does not reseal unchanged credentials.
- No automatic retention, pruning, integrity checks, or failure notifications.
  Monitor backups and test restores.
- Removing a job from inventory does not disable it. Stop/disable its timer and
  remove its units explicitly.

## Checks

```sh
cd ansible
uv sync --locked
make check-urestic  # Ruff, ty, Ansible lint, unit tests, and rendering smoke tests
```

Real TPM operations and backup/restore still need target-host testing.
