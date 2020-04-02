# acmedns_base

Installs prereqs to update Let's Encrypt certificates via the ACME protocol.


Variables:

- `acmedns_base_privkey`:
  A private key to install for the acme user, useful for copying to remote systems over ssh.
- `acmedns_base_pubkey`:
  A corresponding public key.
- If these are not present, that's ok, this just won't set them up
