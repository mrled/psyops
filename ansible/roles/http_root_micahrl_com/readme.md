# http_root_micahrl_com

This role handles a tiny little server in AWS that owns http and https ://micahrl.com. (Deploying that server is done manually in Digital Ocean.)

Purposes:

* To serve `/.well-known/matrix` as a reverse proxy to the actual Matrix server, a hard requirement if your Matrix server is not running on the HTTP server for the root domain
* To serve HTTP 302 permanent redirect responses. E.g. moving biblemunger <http://toys.micahrl.com/biblemunger> to <https://biblemunger.micahrl.com>
* To handle the server side code for IndieAuth (work in progress)

## Certbot

It uses Certbot to get HTTPS certs for all the domains it manages, using an HTTP challenge. This means DNS has to already be set up.

The easiest way to run certbot on the commandline is to run the wrapper script this role installs at `/usr/local/bin/certbot_micahrl.com_root.sh`.
You can pass arguments to that script; to run against the staging server, try passing `--dry-run`
