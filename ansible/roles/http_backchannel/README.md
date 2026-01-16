# http_backchannel

Ansible role to configure Traefik as an HTTP backchannel with Let's Encrypt certificates via Route53 DNS challenge.

## Requirements

- macOS with Homebrew installed
- AWS credentials with Route53 permissions for DNS challenge

## Role Variables

Available variables are listed in `defaults/main.yml`:

- `http_backchannel_acme_email`: Email for Let's Encrypt notifications (required)
- `http_backchannel_dnsname`: Domain name for wildcard certificate (required)
- `http_backchannel_aws_access_key_id`: AWS access key for Route53 (required)
- `http_backchannel_aws_secret_access_key`: AWS secret key for Route53 (required)
- `http_backchannel_aws_region`: AWS region for Route53 (default: "us-east-1")
- `http_backchannel_log_level`: Traefik log level (default: "INFO")
- `http_backchannel_traefik_binary`: Path to Traefik binary (default: "/opt/homebrew/bin/traefik")

## Dependencies

None

## Example Playbook

```yaml
- hosts: backchannel_servers
  roles:
    - role: http_backchannel
      vars:
        http_backchannel_acme_email: "admin@example.com"
        http_backchannel_dnsname: "backchannel.example.com"
        http_backchannel_aws_access_key_id: "AKIAIOSFODNN7EXAMPLE"
        http_backchannel_aws_secret_access_key: "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
```

## What This Role Does

1. Installs Traefik via Homebrew
2. Creates `/usr/local/etc/traefik/` with secure permissions (700, owned by root)
3. Creates subdirectories and files:
   - `dynamic/` - for dynamic Traefik configuration
   - `acme.json` - for Let's Encrypt certificate storage
   - `traefik.yml` - main Traefik configuration
   - `awscreds.conf` - AWS credentials for Route53 DNS challenge
   - `awsconfig.conf` - AWS config with region settings
4. Installs a launch daemon that runs Traefik on system boot
5. Configures Traefik to:
   - Listen on ports 80 and 443
   - Automatically redirect HTTP to HTTPS
   - Obtain wildcard certificates via Let's Encrypt using Route53 DNS challenge
   - Request certificates for both the domain and all subdomains (*.domain)
   - Store certificates in `acme.json`

## Post-Installation

After running this role:

1. Add your dynamic routing configuration to `/usr/local/etc/traefik/dynamic/`
2. Traefik will automatically reload when files in the dynamic directory change
3. Check logs at:
   - `/var/log/traefik.log` - main log
   - `/var/log/traefik-access.log` - access log
   - `/var/log/traefik.stdout.log` - stdout
   - `/var/log/traefik.stderr.log` - stderr

## Managing the Service

```bash
# Check status
sudo launchctl list | grep backchannel

# Stop service
sudo launchctl bootout system/com.micahrl.backchannel

# Start service
sudo launchctl bootstrap system /Library/LaunchDaemons/com.micahrl.backchannel.plist

# Restart service
sudo launchctl bootout system/com.micahrl.backchannel && \
sudo launchctl bootstrap system /Library/LaunchDaemons/com.micahrl.backchannel.plist
```

## License

MIT

## Author Information

Created for psyops infrastructure management.
