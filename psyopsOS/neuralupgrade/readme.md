# NEURALUPGRADE

A Python package responsible for
applying psyopsOS grubusb OS / EFI upgrades.
Used by both the `tk` build tool and on psyopsOS nodes.

(My third attempt of this so far.)

## Command sketch

```sh
# Show
# (Not yet implemented)
#
# Show latest version on deaddrop
neuralupgrade show os
neuralupgrade show efisys
# Show specific version on deaddrop
neuralupgrade show os --version $SOME_VERSION
# Show version of some downloaded update
neuralupgrade show os --path /path/to/some/version/manifest.json

# Download
# (Not yet implemented)
#
# Download an update to local disk
neuralupgrade download os /tmp/psyopsOS/os.tar
neuralupgrade download efisys /tmp/psyopsOS/efisys.tar
# Download a specific version to local disk
neuralupgrade download os /tmp/psyopsOS/os-SOME_VERSION.tar --version $SOME_VERSION

# Check
# (Not yet implemented)
#
# Return true if psyopsOS-A partition is at latest remote version
neuralupgrade check os a
# Return true if psyopsOS-B partition is some specific version
neuralupgrade check os b --version $SOME_VERSION
# Return true if PSYOPSOSEFI partition is the same as a locally downloaded updated
neuralupgrade check efisys --path /path/to/some/version/manifest.json

# Apply
#
# Apply latest version to non-booted A/B partition
# Note that OS upgrades imply mounting the efisys partition as well to update the grub config.
neuralupgrade apply nonbooted
# Apply specific version to efisys partition, downloading from deaddrop
neuralupgrade apply efisys --version $SOME_VERSION
# Re-apply latest version to non-booted A/B partition even if it's already present
neuralupgrade apply nonbooted --force
# Apply some downloaded update to non-booted A/B partition
# First reads the minisign signature and fails if the tarfile doesn't verify
neuralupgrade apply nonbooted --ostar /path/to/some/psyopsOS.grubusb.os.tar
# Ignore the signature (perhaps if the image was just built locally)
neuralupgrade apply nonbooted --ostar /path/to/some/psyopsOS.grubusb.os.tar --no-verify
# When writing to a disk image or other unusual scenarios, you may need to pass explicit A/B sides and device names
neuralupgrade apply a --efisys-dev /dev/loop0p1 --a-dev /dev/loop0p3
# Write updates to a a new disk or disk image
neuralupgrade apply a b efisys --efisys-dev /dev/loop0p1 --a-dev /dev/loop0p3 --b-dev /dev/loop0p4 --ostar /path/to/psyopsOS.grubusb.os.tar --efisys-tar /path/to/efisys.tar
# Apply an update being passed over stdin from e.g. a trusted laptop
# This streams the update over the network, without saving a copy in temp storage first
# (Not yet implemented)
cat ./psyopsOS.grubusb.os.tar | ssh root@NODE neuralupgrade apply nonbooted --no-verify
```

## To do

- `tk` will continue to build the actual disk image, write filesystems, etc, in `make-grubusb-img.sh`,
  but I will need to remove the a/b/efisys stuff from that script when this one is ready.
- Finish unimplemented items above
- Bundle with `psyopsOS-base` package
- Revert untested support for updating grubusb bootmedia added to psyopsOS-write-bootmedia in `7c98c2440ff5071d681565ef530e6e6a4c53be9d`
- Put real help in this readme using cogapp
