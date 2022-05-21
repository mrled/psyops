# Nyx

Nyx is the name of an imaginary ghost.

This is a test ghost site for Fly.io.

Idk I'm in a Mood.

## Setup instructions

```sh
# Make a fly.io account
flyctl auth login

mkdir nyx
cd nyx

# Creates fly.toml
flyctl launch --image=ghost:4-alpine --no-deploy -n nyxmicahrl

# Make a 1GB volume
flyctl volumes create data -a nyxmicahrl -s 1

# Edit fly.toml
# ...
# [env]
#   url = "https://nyxmicahrl.fly.dev"
# ...
# [[services]]
#   http_checks = []
#   internal_port = 2368
# ...
# [mounts]
#   source="data"
#   destination="/var/lib/ghost/content"

# Deploy
flyctl deploy

# Set CNAME for nyx.micahrl.com to nyxmicahrl.fly.dev

flyctl certs add nyx.micahrl.com

# Change url in fly.toml to `https://nyx.micahrl.com` and redeploy
flyctl deploy
```

Then go to <https://nyx.micahrl.com/ghost> and register the admin account
