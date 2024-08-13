# Disagreements

Disagreements is my blog comment server.

## Notes

* container user is `app`
* You need to set a site ID as `SITE` in `fly.toml`, and have it match the `site_id` in the `remark_config` you set in your client.
* database path is always `/srv/var/SITE.db`. Many docs assume the filename is `remark.db`, but that's only true if that's what you set for your `SITE`.
* container will fail if `/srv/var` is not mounted as a volume
* Set `ADMIN_SHARED_ID` in `fly.toml`. You have to log in via one of your auth providers first, then you can click on your logged in name to see the ID, per <https://github.com/umputun/remark42/discussions/926>
* remark42 uses boltdb, not sqlite. This is too bad because it means we can't use litestream. Instead we make the Dockerfile upload the remark42 automatic backup directory every day.

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
flyctl secrets set \
    AWS_ACCESS_KEY_ID=XXX \
    AWS_SECRET_ACCESS_KEY=YYY \
    SECRET=ZZZ \
    AUTH_GITHUB_CID=QWER \
    AUTH_GITHUB_CSEC=ASDF \
    SMTP_PASSWORD=ZXCV

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
