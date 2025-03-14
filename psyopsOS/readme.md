# The psyopsOS

An operating system for powerful management of personal infrastructure.

Status: Very incomplete, it boots tho

## The OS images

The operating system is customizations on top of Alpine Linux.

Goals:

- OS is small and fully in RAM
- OS image is the same for each node
- Nodes have a small USB drive containing its nodename and a secret key (see [System secrets and individuation](./docs/system-secrets-individuation.md))
- Once booted, the nodes use the nodename and secret key to call out to the network and configure themselves in RAM
- Once configuration is finished, k3s cluster starts

### Initial setup

The minisign private key should be generated:

```sh
minisign -G -p ./minisign.pubkey  -s ./minisign.seckey
```

And the password must be GPG-encrypted and the result saved to `.minisign-pass-secret`:

```sh
echo -n '<MINISIGN PASSPHRASE>' | gpg --encrypt --output .minisign-pass-secret --recipient conspirator@PSYOPS
```

## Updating the operating system

There are a few components you can upgrade separately,
or you can upgrade everything all at once and reboot.

### Upgrading psyopsOS packages

Some of psyopsOS exists in an Alpine package called `psyopsOS-base`
and a Python package wrapped in an Alpine package called `progfiguration`.

```sh
apk update
apk upgrade psyopsOS-base progfiguration
```

The `psyopsOS-base` package applies itself automatically.
You may wish to re-run the progfiguration if that has changed since boot:

```sh
. /etc/psyopsOS/psyops-secret.env
progfiguration --syslog-exception apply "$PSYOPSOS_NODENAME"
```

### Upgrading everything at once

The psyopsOS ISO includes `psyopsOS-base` and `progfiguration`,
as well as other scripts that must be baked in to the image before those packages are installed.
Applying the latest ISO will upgrade all of these at once.
Additionally, when the ISO boots, it tries to retrieve the latest `psyopsOS-base` and `progfiguration` packages.

To upgrade the ISO:

- (Optional) update the `psyopsOS-base` package to make sure you have the latest version of `psyopsOS-write-bootmedia`:
  `apk update && apk upgrade psyopsOS-base`.
- Copy the new iso over the network
- Run `psyopsOS-write-bootmedia /tmp/alpine-psyopsOS-0x001-x86_64.iso`
- Reboot

## The psynet backchannel network

There is a backchannel network for _all_ psyopsOS nodes, based on Nebula from defined.net.

- `10.10.8.0/22` (`10.10.8.0`-`10.10.11.255`) is the total network
- `10.10.8.0/24` (`10.10.8.1`-`10.10.8.255`) is reserved for lighthouses
- The remainder is for nodes

See [Psynet](./docs/psynet.md) for how this is bootstrapped.

## The psyops.micahrl.com website

A very simple machine-readable site for configuring psyopsOS and maybe other projects in the future.
Not intended for human audiences at this time.

It's just a little API, but the files it serves are static JSON files.

Currently hosted on S3, see `../terraform/com-micahrl-psyops-http-bucket.tf`.

Pushing binaries to it is handled by `tk deaddrop`.

### Building it

We use a tool called `telekinesis` at the root of this repo, or `tk` for short.
`tk` is basically an overgrown PyInvoke script,
which was an overgrown Makefile.

```sh
# In the root of the repo:
python3 -m venv --upgrade-deps venv
. venv/bin/activate
pip install -e ./telekinesis
tk --help
```

See [the `tk` readme](../telekinesis/readme.md) for detailed helm.

## References

Other custom Alpine distributions:

* <https://github.com/lima-vm/alpine-lima>
