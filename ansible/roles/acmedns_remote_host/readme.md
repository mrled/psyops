# `acmedns_remote_host`

Set up a host so that an `acmedns_*_updater` role (which may run on another host) can copy certs to it.

This will include adding an ssh key to `authorized_keys`, and may include some other setup tasks.

Variables:

- `acmedns_remote_host_user`: The user on this host that will have the keys scp'd to it
- `acmedns_remote_host_ssh_client_pubkey`: The public key to add to `authorized_keys`
- `acmedns_remote_host_fix_homedir_permissions`: Modify homedir of `acmedns_remote_host_user` to not be world/group writable (required for ssh to allow key auth)
- `acmedns_remote_host_allow_passwordless_sudo`: Modify sudoers to allow `acmedns_remote_host_user` to sudo to root without providing a password
