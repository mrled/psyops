# certbot_apache_manager

Shared infrastructure role for managing Let's Encrypt certificates via certbot with Apache and HTTP-01 validation.

- Other roles should declare this as a dependency in their `meta/main.yml`
- `/etc/letsencrypt/renewal-hooks/deploy/`: other roles can install hooks here to copy certs out etc when they get renewed
- `/etc/letsencrypt/` - Main certbot configuration directory
- `/var/www/letsencrypt/.well-known/acme-challenge/` - Webroot for ACME challenges
- `certbot.timer` systemd unit runs twice daily and **only renews** certificates within 30d of expiry (initial creation of certs is **not handled** by this role)
- Certbot logs in `/var/log/letsencrypt/letsencrypt.log`
- Recommend roles that use this create a wrapper script that will create-or-renew certs to handle initial cert provisioning and to be runnable over ssh where necessary

