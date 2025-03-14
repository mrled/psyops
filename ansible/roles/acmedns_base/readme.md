# acmedns_base

Installs prereqs to update Let's Encrypt certificates via the ACME protocol.


Variables:

- `acmedns_base_privkey`:
  A private key to install for the acme user, useful for copying to remote systems over ssh.
- `acmedns_base_pubkey`:
  A corresponding public key.
- If these are not present, that's ok, this just won't set them up

## To do

### Migrate wraplego.py to shouldrenew.py

Currently, I have shell scripts in the acmedns_*_updater roles that call wraplego.py,
and those call lego.

Migrate to shell scripts which call shouldrenew.py,
and based on that call lego if necessary,
before continuing down.

### sudo to the acmedns user inside the shell script wrapper

I keep finding myself running the shell scripts as root.
I should sudo inside the script to make sure this doesn't screw up permissions.


