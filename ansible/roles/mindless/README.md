# mindless

Multiagent programming with `herdr`, in a rootless Fedora container.

## Use

As the host account: `podman exec -it --user mindless mindless zsh`
(substitute your container username).
Keep work under `/workspace/home`, the developer-owned subtree of `mindless-workspace`.
`/etc/mindless/config` and `/etc/mindless/secrets` are mounted read-only inside.
Only `config` is used as the image build context.
The secrets mount uses Podman's `:U` to adjust host ownership to container root;
the secrets directory is accessible only to container root, not the developer user.

As the host user:

```sh
# Run systemctl in the container
podman exec --user root mindless systemctl...

# Stop the container first, and then the firewall
podman exec --user root mindless systemctl --user stop mindless-firewall

# Start the firewall, then the container
podman exec --user root mindless systemctl --user start mindless
```

After Tailscale enrollment, connect directly using the container's MagicDNS name:

```sh
hc machine add mindless@nullyork-mindless.banded-goblin.ts.net --name mindless
```

## SSH keys

The `authorized_keys` file is mounted into the container
and read via an `AuthorizedKeysCommand` in the sshd configuration.
This sidesteps file permissions issues in `StrictMode true`,
and allows Ansible to update the authorized keys directly,
without a copy-on-startup step that would entail restarting the container.

## Tailscale

Tailscale runs userspace-only; its private identity persists in the volume.
Enroll one time with:

```sh
podman exec --workdir /tmp --user root mindless tailscale up --ssh=false --hostname=nullyork-mindless --advertise-tags=tag:mindless --accept-dns=false --accept-routes=false
```

Configure the Tailscale JSON at <https://console.tailscale.com/admin/acls/file>.
Define `tagOwners` for that tag, allow operators **to** it, and nothing **from** it.
(Take care to delete any existing allow-all type rule.)

```json
{
  "groups": {"group:mrladmin": ["mrled@github"]}, // or whatever the Tailscale identity for the account is
  "tagOwners": {"tag:mindless": ["group:mrladmin"]},
  "grants": [
    {"src": ["group:mrladmin"], "dst": ["*"], "ip": ["*"]}
  ]
}
```

## Firewall

Host nftables restricts the host user account.
Allow specific ports with `mindless_tcp_ports` and `mindless_udp_ports` vars;
by default allow http, https, and public Tailscale ports.
Access to hosts on the LAN or the Tailnet are prohibited.
