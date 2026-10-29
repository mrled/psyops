# urestic

Scheduled personal-data backups to S3-compatible storage using restic user services.
Requires Linux, restic 0.17+, and a Secret Service-compatible desktop wallet.
Apply with `become: true` and gathered facts while the backup user is logged in
and their wallet is available. The account and S3 bucket must already exist.
The role installs packages and enables user lingering; job setup runs as the user.

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

Jobs need unique names and absolute source paths. Every `mountpoint: true` path
adds a mountpoint condition; if any is unmounted, that backup is skipped.
Backups honor `CACHEDIR.TAG` via `--exclude-caches`. Timers catch up after downtime
and default to a randomized delay of 15 minutes. Missing repositories are initialized
automatically only on restic exit code 10; other errors stop the backup.

Job files live under `~/.config/psyops/backup/JOB/`; Ansible overwrites local edits.
Units live in `~/.config/systemd/user/`, named `urestic@JOB.service` and `.timer`.
Commands are installed in `~/.local/bin/`.

## Unlocking and status

Deployment stores credentials in the desktop wallet and fills each job's runtime
cache. After reboot, log in and unlock again. Backups read only that cache and fail
promptly if it is unavailable; they never prompt for wallet access.

```sh
~/.local/bin/uresticcache unlock job1  # Use home on nullyork; may prompt for the wallet.
~/.local/bin/uresticcache status job1
systemctl --user list-timers --all 'urestic@*'
systemctl --user start urestic@job1.service
journalctl --user -u urestic@job1.service
~/.local/bin/uresticcache lock job1    # Clear this job's cached credentials.
```

Cache files are plaintext under `$XDG_RUNTIME_DIR/urestic/JOB/`, with directories
`0700` and files `0600`. Lingering keeps them available through screen lock and
logout; reboot clears them. Locking the wallet does not clear the cache, and
clearing the cache does not stop an already-running backup. Protect swap and
hibernation storage, and keep independent recovery copies of the credentials.

## Browse and restore without the role

Use the original credentials from Vault or your password manager on any machine.
Replace the placeholders; avoid saving real secrets in shell history. Choose either
restore example; neither overwrites the original files.

```sh
export RESTIC_REPOSITORY='s3:https://s3.us-central-1.wasabisys.com/YOUR_BUCKET/YOUR_PREFIX'
export AWS_ACCESS_KEY_ID='YOUR_WASABI_ACCESS_KEY_ID'
export AWS_SECRET_ACCESS_KEY='YOUR_WASABI_SECRET_ACCESS_KEY'
export RESTIC_PASSWORD='YOUR_RESTIC_REPOSITORY_PASSWORD'

restic snapshots
snapshot=latest  # Or a snapshot ID from the listing.
restic ls "$snapshot"

# Full restore, retaining the original directory hierarchy beneath the target.
restic restore "$snapshot" --target "$HOME/restored-full" --verify

# Partial restore: use an original snapshot path from ls, not a new machine's path.
restic restore "$snapshot" --target "$HOME/restored-partial" \
  --include '/home/mrl/Documents' --verify

unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY RESTIC_PASSWORD RESTIC_REPOSITORY
```

## Limits and checks

- Changing the inventory password does not change the repository password.
- No automatic retention, pruning, integrity checks, or failure notifications.
  Monitor backups and test restores.
- Removing a job from inventory does not disable its timer or remove wallet entries.
  Stop/disable its timer and remove its units explicitly.

```sh
cd ansible
uv sync --locked
make check-urestic
```

Tests use a fake wallet; desktop wallet access and backup/restore need target-host testing.
