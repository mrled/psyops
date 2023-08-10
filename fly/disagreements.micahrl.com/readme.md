# Disagreements

Disagreements is my blog comment server.

## Setup instructions

```sh
# Make a fly.io account
flyctl auth login

# Creates fly.toml
flyctl launch --no-deploy --name com-micahrl-disagreements

# Make a 1GB volume
flyctl volumes create data --app com-micahrl-disagreements --size 1

flyctl secrets set \
    LITESTREAM_ACCESS_KEY_ID=XXX \
    LITESTREAM_SECRET_ACCESS_KEY=YYY \
    ISSO_ADMIN_PASSWORD=ZZZ \
    ISSO_SMTP_PASSWORD=QQQ

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
