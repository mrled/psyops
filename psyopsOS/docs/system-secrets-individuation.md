# System secrets and individuation

Each system has to have a private key so that we can encypt things for it,
like kubernetes cluster initialization tokens and other secrets.

We assume a dedicated USB drive always installed with a label of `psyops-secret`,
which is mounted during the execution of the `psyopsOS-postboot` local script.
It should contain the following:

- `nodename`, a file containing the node's name. This might not be a proper hostname, but it should be unique.
- `age.key`, a file containing an [age](https://age-encryption.org) private key.
- Optionally `TESTONLYNOPROD.env`, which contains some variables that are useful in development but dangerous in production.
- `minisign.pubkey`, used to verify file contents when downloading configuration from the Internet
- Nebula networking configuration for [psynet](./psynet.md), including `psynet.key` and `psynet.crt` generated from `nebula-cert`.

This information will be used to call out to the network and configure the system.

The nodename and the age PUBLIC key (visible in the private key file) should be saved elsewhere so that configs and (especially) secrets can be encrypted separately per node. The private key should reside only on the USB drive.

Make one like this:

```sh
# The mount path
mountpath=/mnt/psyops-secret-new

# The name you want to use for this node
nodename=millenium-falcon

# Its NIC card's MAC address
nodemac="00:00:00:00:00:00"

# The name of the USB device, e.g. 'device=/dev/sdb'
# No need for partitions
device=/dev/xxx

# Make a filesystem
# Add a label that shows up in blkid and can be used in fstab
mkfs.ext4 -L psyops-secret $device

# Mount it
mkdir -p "$mountpath"
mount $device "$mountpath"

# Save the nodename
echo "$nodename" > "$mountpath"/nodename

# Create an age private key
# The public key will be displayed to stdout
age-keygen -o "$mountpath"/age.key

# Copy the minisign public key
cp minisign.pubkey "$mountpath"

# Make an SSH host key
ssh-keygen -q -f "$mountpath"/ssh_host_ed25519_key -N '' -t ed25519
# No need to keep the pubkey around, we regenerate it on boot
rm "$mountpath"/ssh_host_ed25519_key.pub

# Create a mactab file
# This is used to set a unique name for the network interface we use
# It must be the real MAC address of the hardware NIC you want to use, assigned to an interface called 'psy0'
# See networking.md for more info.
echo "psy0 $nodemac" > "$mountpath"/mactab

# Create a network.interfaces file for the psy0 interface
cat >"$mountpath"/network.interfaces <<EOF
auto lo
iface lo inet loopback

auto psy0
iface psy0 inet dhcp
EOF

#
```

## Optional files

Some files on the secret volume are optional.

### network.interfaces

If there is a `network.interfaces` file here, it will be placed in `/etc/network/interfaces`.

If not, `setup-network -a` is run.
`setup-network -a` will prefer a `wlan0` interface if it exists, or `eth0` otherwise.

The best thing to do is something like

```
auto lo
iface lo inet loopback

auto psy0
iface psy0 inet dhcp
```

TODO: Doesn't that just mean I can ALWAYS do that?

### TESTONLYNOPROD.env

This is dot-sourced if it exists.

Set `PSYOPSOS_TESTING_ONLY_NO_PROD_ADD_TOOR_BLANK_PW=yes` in that file if you want to create a `toor` user with a blank password.
Can be useful when testing early boot script so that you can get in easily to a VM or something.

## Future research

- Can I do this in the TPM without a dedicated USB drive?
