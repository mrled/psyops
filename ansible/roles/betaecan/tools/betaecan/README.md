# betaecan CLI

Inspect jobs and run restic with configuration managed by the betaecan Ansible role.
Run as the backup user, after unlocking the runtime credentials with `betaecancache`.
Listing jobs does not require credentials.
From this directory, run with the locked project environment:

```sh
uv run --locked betaecan jobs
uv run --locked betaecan restic home snapshots
uv run --locked betaecan restic home ls latest
uv run --locked betaecan restic home restore latest --target /mnt/recovery/full --verify
uv run --locked betaecan restic home restore latest --target /mnt/recovery/partial \
  --include '/home/mrl/Documents' --verify
```

Everything after `restic JOB` is passed unchanged to restic.
Configuration defaults to `~/.config/psyops/backup/`;
use `betaecan --config-dir /path/to/jobs ...` to override it.
The CLI is currently run from this source project, not installed by the role.
