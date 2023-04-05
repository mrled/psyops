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

First, create the psynet nebula key and certificate.
This must be done from within the psyops container after running `psecrets unlock`.

```sh
# The name you want to use for this node
nodename=millenium-falcon
# The IP address to use for this node on psynet
# Add this address to `ansible/cloudformation/PsynetZone.cfn.yml` and deploy it
# Make sure this is unique!
psynetip=10.10.10.x/22

# This command has to be run from the nebula CA directory, see ./psynet.md for more information.
cd /secrets/psyops-secrets/psynet
nebula-cert sign -name $nodename -ip "$psynetip" -groups psyopsOS

# Add the new cert to gopass
gopass insert -m "psynet/$nodename.key" < "$nodename.key"
gopass insert -m "psynet/$nodename.crt" < "$nodename.crt"

# Now copy it to the host
# For it to be configured correctly on boot,
# it must be called psynet.host.(key|crt) in the secrets filesystem that we are about to create in the next step.
mkdir /psyops/tmp
cp millenium-falcon.key millenium-falcon.crt /psyops/tmp
```

Next, create the psyops-secret volume on a USB key or similar device.
psyopsOS finds this volume by looking for its label,
so any filesystem on any device that `mount` can find with the correct label will work.
Creating the filesystem and label requires running this on a Linux host, however;
I tend to use an Alpine Linux VM on my macOS laptop,
using USB passthrough to attach a physical USB drive.

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

# Copy the psynet key and certificate created in the previous step
cp /path/to/psyops/tmp/millenium-falcon.key "$mountpath"/psynet.host.key
cp /path/to/psyops/tmp/millenium-falcon.crt "$mountpath"/psynet.host.crt
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
