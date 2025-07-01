# Chinese Room

A role for a locked down virtual machine to let agents run wild.

- Restrict the agent user from talking on the network
    - Exceptions: localhost, Anthropic API ranges
- Get Let's Encrypt certificates for a domain and all subdomains to dedicate to the Chinese Room
    - Get the certs as root, and copy them to nginx config
    - Don't give the agent DNS API keys
- Configure nginx to proxy HTTPS to local code
    - Use nginx as a reverse proxy to agent-controlled code
    - Allow the agent UID to define a map of subdomains to ports
    - So let the agent run a server on `localhost:8080`,
      and define a mapping of `test 8080`,
      and get real HTTPS certificates from your desktop to <https://test.chineseroom.example.com/>
- Create bare repos in `~/repos/` as the agent user
    - Create a `chineseroom` remote pointing to these bare repos
    - Check out and run code on your regular workstation as normal
    - Push to the `chineseroom` remote and let the agent clone and push to there
    - More sandboxed than a Docker container with the repo mounted as a volume,
      because it prevents the agent from adding scripts to git hooks or smudge filters that could obscure diffs
    - Pull code from the `chineseroom` remote safely, review it on your workstation as normal,
      and run it when satisfied

## Steps to do in advance

- Install Fedora 42
  - During the install, set up a user for yourself that will have sudo;
    do not set up the agent user in the installer
- Configure passwordless ssh keys for Ansible to log in to

## Features

- Network restrictions using nftables to limit outbound connections
- HTTPS setup with Let's Encrypt certificates using DNS validation
- Nginx configuration for domain and subdomain proxying
- User-controlled subdomain mapping

## Requirements

- RHEL/CentOS/Fedora-based system (uses dnf and firewalld)
- AWS credentials configured at `/root/.aws/credentials` with Route53 permissions
- A domain with Route53 DNS hosting

## Role Variables

See `defaults/main.yml` for all available variables. Key variables:

- `chineseroom_restricted_user`: User to apply network restrictions to (default: callista)
- `chineseroom_domain`: Main domain for the service (default: chineseroom.micahrl.com)
- `chineseroom_whitelist_ips`: IP addresses the restricted user can connect to

## Example Playbook

```yaml
- hosts: servers
  roles:
    - role: chineseroom
      vars:
        chineseroom_domain: example.com
        chineseroom_restricted_user: myuser
```

## Tags

- `chineseroom`: Run all tasks
- `chineseroom-restrictnet`: Only apply network restrictions
- `chineseroom-https`: Only setup HTTPS configuration

## User Domain Mapping

The restricted user can create subdomain mappings by editing `~/domainmap.txt`:

```
subdomain1 8080
subdomain2 3000
```

Then run: `sudo /usr/local/bin/regen-nginx-mappings.sh`