# psybuildboot

A Python package responsible for:
building psyopsOS kernel, initramfs, squashfs, etc;
creating a bootable disk image that can be written to a USB disk;
updating the non-booted A/B partition of a running system;
and updating the EFI system partition containing GRUB etc of a running system (dangerous).

Various pieces of this pacakge must be runnable in different contexts.
Building the binaries and creating a bootable disk image has to work inside the builder container running Alpine;
updating A/B/EFI partitions has to work from a running psyopsOS node.
In the build container we install the script as editable,
which is fast as it doesn't copy any files,
and on psyopsOS nodes it runs the `__main__.py` file inside a zipapp.
In neither case do we care about the pip package version.

## Command sketch

TODO: replace this with real help once implemented

```sh
# Build a generic boot disk image, with an empty secrets partition
psybuildboot build

# Build a boot disk image for just one host, with a secrets partition containing the contents of a tarball
psybuildboot build --secrettarball example.tar

# Show
#
# Show latest version on deaddrop
psybuildboot show os
psybuildboot show efisys
# Show specific version on deaddrop
psybuildboot show os --version $SOME_VERSION
# Show version of some downloaded update
psybuildboot show os --path /path/to/some/version/manifest.json

# Download
#
# Download an update to local disk
psybuildboot download os /tmp/psyopsOS/os
psybuidlboot download efisys /tmp/psyopsOS/efisys
# Download a specific version to local disk
psybuildboot download os /tmp/psyopsOS/os-SOME_VERSION --version $SOME_VERSION

# Check
#
# Return true if psyopsOS-A partition is at latest remote version
psybuildboot check os a
# Return true if psyopsOS-B partition is some specific version
psybuildboot check os b --version $SOME_VERSION
# Return true if PSYOPSOSEFI partition is the same as a locally downloaded updated
psybuildboot check efisys --path /path/to/some/version/manifest.json

# Apply
#
# Apply latest version to non-booted A/B partition
psybuildboot apply os
# Apply specific version to efisys partition
psybuildboot apply efisys --version $SOME_VERSION
# Re-apply latest version to non-booted A/B partition even if it's already present
psybuildboot apply os --force
# Apply some downloaded update to non-booted A/B partition
psybuildboot apply os --path /path/to/some/version/manifest.json
```
