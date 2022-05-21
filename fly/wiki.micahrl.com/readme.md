# wiki.micahrl.com

Currently just a testing ground for some things.

## Initial setup

This just needs to be done once,
recorded here so I don't forget how it works.

```sh
# Log in
flyctl auth login

# Create fly.toml
flyctl launch --no-deploy --name com-micahrl-wiki

# Make a 1GB volume
flyctl volumes create data --app com-micahrl-wiki -s 1

flyctl secrets set \
    LITESTREAM_ACCESS_KEY_ID=XXX \
    LITESTREAM_SECRET_ACCESS_KEY=YYY

# Edit fly.toml
# ...
# [env]
#   url = "https://com-micahrl-wiki.fly.dev"
#   DB_TYPE = "sqlite"
#   DB_PATH = "/mrldata/wikijs.sqlite"
# ...
# [[services]]
#   http_checks = []
#   internal_port = 3000
# ...
# [mounts]
#   source = "data"
#   destination = "/mrldata"

# Deploy
flyctl deploy

# Set CNAME for wiki.micahrl.com to com-micahrl-wiki.fly.dev

flyctl certs add wiki.micahrl.com

# Change url in fly.toml to `https://wiki.micahrl.com` and redeploy

flyctl deploy

# Go to https://wiki.micahrl.com and set up the admin account and first settings.
# Do this quickly as it will let you set any password on first run.
```
