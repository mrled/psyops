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

### Building it

```sh
python3 -m venv --upgrade-deps venv
. venv/bin/activate
pip install -r requirements.txt
invoke --list
```

#### Doing a clean build

To reset any cache and start over from scratch, do the following.

From your host system:

```sh
invoke clean
```

Then, from the psyops container, run

```sh
invoke progfiguration-abuild
invoke psyopsOS-base-abuild
invoke deploy
```

Finally, from the host system again:

```sh
invoke cleandockervol
invoke build-docker-container --rebuild

invoke mkimage
```

### Errors after updates

#### Rebuild the docker container

If you get errors like the following,
it's an indication that the apk cache on the image has gone stale:

```
Signing: /tmp/update-kernel.KAKJJL/boot/modloop-lts
ERROR: intel-ucode-20220510-r0: No such file or directory
gzip: invalid magic
```

The easiest way to handle this is to rebuild the build container with
`invoke build-docker-container --rebuild`.

#### Check aports

Note that wherever you keep your local `aports` checkout, you'll have to keep that updated as well.
If you get build errors in the mkimage phase, this is probably part of the problem!

Additionally:
The Alpine image build system dot-sources ALL mkimage.*.sh files.
This is intended so you can define functions like `profile_psyopsOS() { ... }`,
but we can also abuse it to override built-in functions that don't have any other hooks.

Compare any overridden functions in that file to the original versions in the `aports` repo and adjust as necessary.

#### How to do a manual build without `tasks.py`

This may be helpful for errors that you can't otherwise resolve.
Run the command `invoke mkimage --whatif` and read the output at the end.
It will show a command to launch the Docker container interactively,
and a command to run once inside the Docker container.

## References

Other custom Alpine distributions:

* <https://github.com/lima-vm/alpine-lima>
