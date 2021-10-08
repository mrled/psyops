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

List certs that certbot has with `certbot certificates`.

If you add a new domain to `http_root_micahrl_com_domain_list`, it should get a cert automatically.

## Notes

### Debian - always serving default site

This is easy to notice if redirects are not happening (which are defined in my custom site), and the request is showing up in the default site logs.

Note that in the 000-default.conf vhost, ServerName is not set. Apache then uses the server's hostname as the ServerName, and if you make a request against the server's hostname, it'll match there no matter what.
When migrating to new servers, this is annoying. I haven't switched over all the CNAMEs yet, but I am trying to test apache config using the real hostname - and it is going to the default site. When it's in production this is fine, as the default site is the hostname and the server is intended only to be used through service CNAMES.
So it's useful to have a `hostname2.example.com` pointed to the server to for initial testing.

See also

* https://www.perfacilis.com/blog/systeembeheer/linux/how-to-not-brick-apache2-when-using-lets-encrypt.html

### Migrating to a new webserver

Move the domains over in batches.
First set up HTTPS certs for the new hostname `newwebserver.micahrl.com`, and add a `newwebserver2.micahrl.com` as well (see above) for testing.
Once that's working, then move over subdomains of low importance, like `toys.micahrl.com` and `www.micahrl.com`.

Wait for more critical domains until everything else is working.
E.g. moving over the $ORIGIN domain `micahrl.com` will impact Matrix server if it isn't done correctly, so don't do that one until the others are moved over and working, and you've tested the `/.well-known/matrix` path against the other subdomains.
(To test that, note that we are using Apache, but the `/.well-known/matrix` path is reverse-proxied to the Matrix server which is using nginx - you should be able to tell the difference in the `Server` header that gets returned. If you get a `403 Forbidden` by that path with an `nginx` Server header, it's working.)

You can modify the `http_root_micahrl_com_certbot_domain_list` to just be a subset of the the complete `http_root_micahrl_com_domain_list` - that means that certbot will only request certs for the subset, but Apache will be configured for the full set of domains (even if they are not yet pointing to the new server), so you can examine the Apache config for errors without breaking the old webserver.
