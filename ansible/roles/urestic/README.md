# urestic

Scheduled personal-data backups to S3-compatible storage using restic. System
services run as the selected account, without requiring a login. Requires Linux,
systemd 250+ with TPM2 support, restic 0.17+, and a usable TPM2 device; prerequisites are installed.
The account and S3 bucket must already exist. Apply with `become: true` and gathered facts.

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
Units are named `urestic-USER@JOB.service` and `.timer`:

```sh
sudo systemctl start urestic-alice@job1.service
sudo journalctl -u urestic-alice@job1.service
```

## Repository access

Backups initialize missing repositories automatically, only when restic reports
exit code 10. Wrong passwords, access errors, and other failures stop the backup
without attempting initialization. The S3 bucket must already exist.

To run manual commands using the sealed credentials:

```sh
user=alice job=job1
home=$(getent passwd "$user" | cut -d: -f6)
cred="/etc/credstore.encrypted/urestic/$user/$job"
sudo systemd-run --wait --pipe --collect \
  --property="User=$user" \
  --property="LoadCredentialEncrypted=restic.password:$cred/restic.password" \
  --property="LoadCredentialEncrypted=aws.access-key-id:$cred/aws.access-key-id" \
  --property="LoadCredentialEncrypted=aws.secret-access-key:$cred/aws.secret-access-key" \
  /usr/local/libexec/urestic/uresticjob "$home/.config/psyops/backup/$job" snapshots
```

Replace `snapshots` with `check` or `restore ...` as needed. Use the installed backup
service for backups so mountpoint conditions apply.

## Important limits

- Password and S3 keys are TPM-sealed under `/etc/credstore.encrypted/urestic/USER/JOB/`,
  using PCR 7 by default. **Keep independent recovery copies**: TPM or Secure Boot
  changes can prevent decryption. Undecryptable existing credentials fail deployment.
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
