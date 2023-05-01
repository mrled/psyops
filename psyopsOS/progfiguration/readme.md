# progfiguration

A PROGrammatic conFIGURATION for psyopsOS.
I'm tired of writing YAML when what I want to write is Python.
This is the base package I use to write Python to configure psyopsOS nodes.

## Alpine package (apk)

This is a Python pacakge that is distributed as an Alpine package.
This lets us use existing Alpine package building/downloading/applying/signing infrastructure.

To build, run `invoke progfiguration-abuild` in the parent directory.

To deploy the repo to S3 (so that nodes can download it), run `invoke progfiguration-abuild deploy` in the parent directory.

## Relationship to psyopsOS

psyopsOS is an Alpine-based distribution that uses progfiguration,
but progfiguration might be used to configure non-psyopsOS distributions in the future.
There is a separate package, `psyopsOS-base`, for stuff that should be psyopsOS-specific.

## Commands

progfiguration installs these commands:

- `progfiguration`: Run progfiguration against localhost, and perform some ancillary tasks like per-host encryption

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

if ! grep -q "psyops.micahrl.com" /etc/apk/repositories; then
    echo "https://psyops.micahrl.com/apk/psyopsOS" >> /etc/apk/repositories
fi

apk update
apk add progfiguration
```
