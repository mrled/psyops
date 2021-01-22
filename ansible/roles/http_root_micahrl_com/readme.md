# http_root_micahrl_com

This role handles a tiny little server in AWS that owns http and https ://micahrl.com. (Deploying that server is handled by CloudFormation elsewhere in ansible.)

This mainly exists because running your own matrix server requires /.well-known/matrix to be reverse-proxied to your actual matrix server, and mine is hosted elsewhere.

It also has become a convenient way to HTTP 302 permanently redirect domain names to new locations. E.g., I'm touching this role today so I can move biblemunger from http://toys.micahrl.com/biblemunger to https://biblemunger.micahrl.com.

## Certbot

It uses Certbot to get HTTPS certs for all the domains it manages, using an HTTP challenge. This means DNS has to already be set up.

Sometimes certbot gets confused and generates a bad config file at `/etc/httpd/conf.d/vhost_http-le-ssl.conf`. You can safely move it out of the way and run certbot again and it'll generate a new one.

The easiest way to run certbot is to run the wrapper script this role installs at `/usr/local/bin/certbot_nullyork_root.sh`.
