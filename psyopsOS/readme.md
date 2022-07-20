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

## To do

- Make an update mechanism
    - Service that checks for OS updates once/day or something, maybe via similar method like `psyops.micahrl.com/os-update.json`
    - If there's an update, download it to a temp dir, and overwrite the USB drive that contains the OS with it. I hope u tested it!
    - In a real environment, you'd want an atomic update, but I'm not going to make that here.
    - In a real environment, you'd want the ability to roll back too.
- Private networking
    - Wireguard? This would be really nice. Would require a maintained server :/
    - Tor for management from anywhere. Punch thru NATs or whatever, no worry about a wireguard server. Need to keep a list of all public keys for all nodes, same way I do now for age keys.
    - A Tor for all networking mode. Could implement as a role in progfiguration, but better to do as a different flavor of ISO, so that it is up before anything uses the network at all.
- Misc
    - Use `AuthorizedKeysCommand` as described [in this GH issue](https://github.com/coreos/afterburn/issues/157) to support an `authorized_keys.d` directory (maybe named so as not to conflict with a possible future support of this, like `psyopsos_authorized_keys.d`.) This would make psyopsOS-base's installation of root SSH keys easier and less error prone.
    - Run a daemon to share non-secret info like ISO generation time, installed version of important packages, postboot log.
    - Better host for the apk repos than S3. Swear to god, how do you make something called "amazon web services" with a service that stores files and require a fucking PhD to connect those two over HTTPS.
