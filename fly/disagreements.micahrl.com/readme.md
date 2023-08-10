# Disagreements

Disagreements is my blog comment server.

## Notes:

* container user is `app`
* database path is `/srv/var/remark.db`
* container will fail if `/srv/var` is not mounted as a volume
* Set `ADMIN_SHARED_ID` in `fly.toml`. You have to log in via one of your auth providers first, then you can click on your logged in name to see the ID, per <https://github.com/umputun/remark42/discussions/926>

## Setup instructions

```sh
# Make a fly.io account
flyctl auth login

# Creates fly.toml
flyctl launch --no-deploy --name com-micahrl-disagreements

# Make a 1GB volume
flyctl volumes create data --app com-micahrl-disagreements --size 1

# Set secrets
# SECRET is a JWT secret, create with eg `openssl rand -base64 32`
# various AUTH secrets require creating apps with oauth providers,
# https://remark42.com/docs/configuration/authorization/.
# ADMIN_PASSWD it says not to run with this enabled unless you do manual backups,
# ok we are using litestream.
flyctl secrets set \
    LITESTREAM_ACCESS_KEY_ID=XXX \
    LITESTREAM_SECRET_ACCESS_KEY=YYY \
    SECRET=ZZZ \
    AUTH_GITHUB_CID= \
    AUTH_GITHUB_CSEC= \
    ADMIN_PASSWD=

# Edit fly.toml as appropriate
# At least set the URL to something like com-micahrl-disagreements.fly.dev
vim fly.toml

# Deploy
flyctl deploy

# Set CNAME for disagreements.micahrl.com to whatever you set in fly.toml (com-micahrl-disagreements.fly.dev), and then:
flyctl certs add disagreements.micahrl.com

# Change url in fly.toml to `https://disagreements.micahrl.com` and redeploy
flyctl deploy
```

Then go to <https://disagreements.micahrl.com> and register the admin account
