# psyopsOS-base package

This is an Alpine package for the psyopsOS base system.

## Installed to the ISO directly

This is installed to the ISO filesystem when the ISO image is created,
meaning that its post-install script runs before the image is even booted.

This gives us a good place to configure things that should be up before the system boots at all,
like the root password.

This is the only way I know of to get a script to change the ISO filesystem.
Static files can easily be copied from the genapkovl script,
but modifying a base file, like /etc/shadow, is not possible from genapkovl.

## Does not depend on progfiguration

`progfiguration` is a package used to configure psyopsOS, but also other operating systems.
When installed in psyopsOS,
it maybe installed after this package,
so we do not depend on it here.

## Installing on old or broken psyopsOS systems

To get psyopsOS-base and progfiguration on an older or broken psyopsOS system,
try this.

```sh
mkdir -p /etc/apk/keys /etc/apk/repositories.d

cat > /etc/apk/keys/psyops@micahrl.com-62ca1973.rsa.pub  <<EOF
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

alpine_version="3.16"

if ! grep -q "psyops.micahrl.com" /etc/apk/repositories; then
    echo "https://psyops.micahrl.com/apk/v$alpine_version/psyopsOS" >> /etc/apk/repositories
fi

apk update
apk add psyopsOS-base progfiguration_blacksite
```

This is useful so you can upgrade parts of the old system without rebooting,
and also so you can get the latest version of scripts like `psyopsOS-write-bootmedia`.
