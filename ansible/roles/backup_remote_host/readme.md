# `backup_remote_host`

Set up a host so that an `backup_*` role (which may run on another host) can back it up.

This will include adding an ssh key to `authorized_keys`, and may include some other setup tasks.

Variables:

- `backup_remote_host_user`: The user on this host that will have the keys scp'd to it
- `backup_remote_host_ssh_client_pubkey`: The public key to add to `authorized_keys`
- `backup_remote_host_fix_homedir_permissions`: Modify homedir of `backup_remote_host_user` to not be world/group writable (required for ssh to allow key auth)
- `backup_remote_host_allow_passwordless_sudo`: Modify sudoers to allow `backup_remote_host_user` to sudo to root without providing a password

