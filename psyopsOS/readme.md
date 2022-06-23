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

- Configure more complex stuff after boot.
    - Tailscale
    - The data storage for the system at /data or whatever
    - k3s
- How to configure post boot? TODO: document this in a separate file
    - Should this be Ansible?
    - Maybe it should be simple shell scripts? Ansible is so slow...
    - What kind of server will it need?
    - I'd like this to be a simple object store, so I could put it anywhere on HTTP/S3 and be able to move it wherever I want
    - Maybe something like a `psyops.micahrl.com/postboot.json` page that contains a dict of nodename:instructions paired, built by hand maybe, or with a SSG.
    - Encrypt the instructions per host so that the host can be sure that instructions it gets over the network are trustworthy
    - Instructions could be location of a script to download and run, or a tarball to download/extract/run some specific script from. In either case, it would also be encrypted.
- Make an update mechanism
    - Service that checks for OS updates once/day or something, maybe via similar method like `psyops.micahrl.com/os-update.json`
    - If there's an update, download it to a temp dir, and overwrite the USB drive that contains the OS with it. I hope u tested it!
    - In a real environment, you'd want an atomic update, but I'm not going to make that here.
    - In a real environment, you'd want the ability to roll back too.
- Build apks for scripts that are now in the apkovl
    - This will mean I can install them at ISO build time, but also update them at boot time
    - Also build progfiguration as an apk?
    - If I do that, I might not need minisign at all? I could use apk signing keys instead.
- Misc
    - It regenerates SSH host keys on each boot, which takes a minute; can we avoid this somehow? (Or only generate one pair?)
        - I think the answer is to geneate SSH host keys on the psyops-secret volume.
        - Mount psyops-secret early. Either include it in fstab, or make a service do it very early in boot. Do NOT fail boot if it doesn't exist.
        - Create an openrc service that copies the SSH key to the right location if psyops-secret was mounted. Generate keys if psyops-secret wasn't mounted.
