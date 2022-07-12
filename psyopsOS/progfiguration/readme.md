# progfiguration

A PROGrammatic conFIGURATION for psyopsOS.
I'm tired of writing YAML when what I want to write is Python.
This is the base package I use to write Python to configure psyopsOS nodes.

## Alpine package (apk)

This is a Python pacakge that is distributed as an Alpine package.
This lets us use existing Alpine package building/downloading/applying/signing infrastructure.

To build, run `invoke progfiguration-abuild` in the parent directory.

To deploy the repo to S3 (so that nodes can download it), run `invoke progfiguration-abuild deploy` in the parent directory.

## Commands

progfiguration installs these commands:

- `psyopsOS-progfiguration`: Run progfiguration against localhost, and perform some ancillary tasks like per-host encryption
- `psyopsOS-apply-update`: Write a new version of the ISO image to the boot media

## Adding the psyopsOS repo and installing progfiguration on a host that isn't configured properly

You might have a host that should be psyopsOS but isn't.
Perhaps it's older, or didn't come up far enough to configure itself.
Here's how to get progfiguration.

```sh
cat > /etc/apk/keys/psyops@micahrl.com-62ca1973.rsa.pub <<EOF
-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEApzwpOtJbg8G3JkDI+24H
JeQlMvvPVhlP2AEZjERorXHpMFHgJdfvnGuYOISsznkc0pTfYF1W7aYa8PBoRfBk
Fz2PLKAQjqtpZe5hXm792pdVvW05/0Wsy53qacRxspHcHgkH4M1FqUEvdfzurXvP
dstUSFtIxAwbtrObY/R1X62RzVVOeQ1vM5yrkhkTtF8JTdDX1DX5EZL7KM/VsOkc
tXad6c4HeXLMEDrzCPqPvO8KycBV5HxXIxd6CHbNnY20A5OcqvqWUffEFXrvLaYO
VD+LEhUQfEN4Xaj0nOUeLyDKh7bidgMuOsllATNSbTYpoRMe8fyQQtzfvIfTa0oj
mwIDAQAB
-----END PUBLIC KEY-----
EOF

if ! grep -q "com-micahrl-psyops-http-bucket.s3.us-east-2.amazonaws.com" /etc/apk/repositories; then
    echo "https://com-micahrl-psyops-http-bucket.s3.us-east-2.amazonaws.com/apk/psyopsOS" >> /etc/apk/repositories
fi

apk update
apk add progfiguration
```
