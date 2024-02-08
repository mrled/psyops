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
neuralupgrade show os --latest
# Show specific version on deaddrop
neuralupgrade show os --version $SOME_VERSION
# Show a/b/efisys partition information, versions, etc
neuralupgrade show booted
# Show version of some downloaded update
neuralupgrade show --minisig /path/to/some/psyopsOS.grubusb.os.tar.minisig

# Download
#
# Download an update to local disk
neuralupgrade download --type os /tmp/psyopsOS/os.tar
neuralupgrade download --type efisys /tmp/psyopsOS/efisys.tar
# Download a specific version to local disk
neuralupgrade download --type os /tmp/psyopsOS/os-SOME_VERSION.tar --version $SOME_VERSION
# Download both to a folder, using the name in the repo
neuralupgrade download /tmp/UPDATES/ --type os efisys --version $SOME_VERSION

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

## Packaging and installing

`neuralupgrade` can be used as a pip package, an Alpine APK package, or a zipapp.
The Alpine package is built in `psyopsOS/abuild/psyopsOS/neuralupgrade` from repo root.

```sh
# Install as editable for local development, from this directory
pip install -e .

# Make a zipapp via tk, from anywhere
tk buildpkg neuralupgrade-pyz

# Make an apk via tk, from anywhere
tk buildpkg neuralupgrade-apk

# Make a zipapp by hand, from the root of the psyops repo
python3 -m zipapp --main neuralupgrade.cmd:main --output artifacts/neuralupgrade.pyz --python "/usr/bin/env python3" psyopsOS/neuralupgrade/src

# Copy the zipapp to some remote node, from the root of the psyops repo
scp artifacts/neuralupgrade.pyz root@NODE:/tmp/
```

## Full command help


<!--[[[cog
#
# This section is generated with cog
# Run `cog -r readme.md` and it will overwrite the help output below with the latest.
# Or, run `tk cog` and it will run `cog` on this file and any others it knows about.
#

import cog
from neuralupgrade.cmd import get_argparse_help_string, getparser
cog.outl(get_argparse_help_string("neuralupgrade", getparser(prog="neuralupgrade")))
]]]-->
> neuralupgrade --help
usage: neuralupgrade [-h] [--debug] [--verbose]
                     {show,download,apply,set-default} ...

Update psyopsOS boot media

positional arguments:
  {show,download,apply,set-default}
                        Subcommand to run
    show                Show information about boot media
    download            Download updates
    apply               Apply psyopsOS or EFI system partition updates
    set-default         Set the default boot label in the grubusb config

options:
  -h, --help            show this help message and exit
  --debug, -d           Drop into pdb on exception
  --verbose, -v         Verbose logging

________________________________________________________________________

> neuralupgrade show --help
usage: neuralupgrade show [-h] [--efisys-dev EFISYS_DEV]
                          [--efisys-mountpoint EFISYS_MOUNTPOINT]
                          [--efisys-label EFISYS_LABEL] [--a-dev A_DEV]
                          [--a-mountpoint A_MOUNTPOINT] [--a-label A_LABEL]
                          [--b-dev B_DEV] [--b-mountpoint B_MOUNTPOINT]
                          [--b-label B_LABEL] [--minisig MINISIG]

options:
  -h, --help            show this help message and exit
  --efisys-dev EFISYS_DEV
                        Override device for EFI system partition (found by label
                        by default)
  --efisys-mountpoint EFISYS_MOUNTPOINT
                        Override mountpoint for EFI system partition (found by
                        label in fstab by default)
  --efisys-label EFISYS_LABEL
                        Override label for EFI system partition, default:
                        PSYOPSOSEFI
  --a-dev A_DEV         Override device for A side (found by label by default)
  --a-mountpoint A_MOUNTPOINT
                        Override mountpoint for A side (found by label in fstab
                        by default)
  --a-label A_LABEL     Override label for A side, default: psyopsOS-A
  --b-dev B_DEV         Override device for B side (found by label by default)
  --b-mountpoint B_MOUNTPOINT
                        Override mountpoint for B side (found by label in fstab
                        by default)
  --b-label B_LABEL     Override label for B side, default: psyopsOS-B
  --minisig MINISIG     Show information from the minisig file of a specific
                        ostar tarball

________________________________________________________________________

> neuralupgrade download --help
usage: neuralupgrade download [-h] [--efisys-dev EFISYS_DEV]
                              [--efisys-mountpoint EFISYS_MOUNTPOINT]
                              [--efisys-label EFISYS_LABEL] [--a-dev A_DEV]
                              [--a-mountpoint A_MOUNTPOINT] [--a-label A_LABEL]
                              [--b-dev B_DEV] [--b-mountpoint B_MOUNTPOINT]
                              [--b-label B_LABEL] [--repository REPOSITORY]
                              [--psyopsOS-filename-format PSYOPSOS_FILENAME_FORMAT]
                              [--psyopsESP-filename-format PSYOPSESP_FILENAME_FORMAT]
                              [--no-verify] [--pubkey PUBKEY]
                              [--version VERSION]
                              [--type {psyopsOS,psyopsESP} [{psyopsOS,psyopsESP} ...]]
                              output

positional arguments:
  output                Where to download update(s). If it ends in a slash,
                        treated as a directory and download the default filename
                        of the update. If multiple types are passed, this must
                        be a directory.

options:
  -h, --help            show this help message and exit
  --efisys-dev EFISYS_DEV
                        Override device for EFI system partition (found by label
                        by default)
  --efisys-mountpoint EFISYS_MOUNTPOINT
                        Override mountpoint for EFI system partition (found by
                        label in fstab by default)
  --efisys-label EFISYS_LABEL
                        Override label for EFI system partition, default:
                        PSYOPSOSEFI
  --a-dev A_DEV         Override device for A side (found by label by default)
  --a-mountpoint A_MOUNTPOINT
                        Override mountpoint for A side (found by label in fstab
                        by default)
  --a-label A_LABEL     Override label for A side, default: psyopsOS-A
  --b-dev B_DEV         Override device for B side (found by label by default)
  --b-mountpoint B_MOUNTPOINT
                        Override mountpoint for B side (found by label in fstab
                        by default)
  --b-label B_LABEL     Override label for B side, default: psyopsOS-B
  --repository REPOSITORY
                        URL for the psyopsOS update repository, default:
                        https://psyops.micahrl.com/os
  --psyopsOS-filename-format PSYOPSOS_FILENAME_FORMAT
                        The format string for the versioned grubusb EFI system
                        partition tarfile. Used as the base for the filename in
                        S3, and also of the signature file.
  --psyopsESP-filename-format PSYOPSESP_FILENAME_FORMAT
                        The format string for the versioned grubusb OS tarfile.
                        Used as the base for the filename in S3, and also of the
                        signature file.
  --no-verify           Skip verification of the ostar tarball
  --pubkey PUBKEY       Public key to use for verification (default:
                        /etc/psyopsOS/minisign.pubkey)
  --version VERSION     Version of the update to download, default: latest
  --type {psyopsOS,psyopsESP} [{psyopsOS,psyopsESP} ...]
                        The type of update to download

________________________________________________________________________

> neuralupgrade apply --help
usage: neuralupgrade apply [-h] [--efisys-dev EFISYS_DEV]
                           [--efisys-mountpoint EFISYS_MOUNTPOINT]
                           [--efisys-label EFISYS_LABEL] [--a-dev A_DEV]
                           [--a-mountpoint A_MOUNTPOINT] [--a-label A_LABEL]
                           [--b-dev B_DEV] [--b-mountpoint B_MOUNTPOINT]
                           [--b-label B_LABEL] [--no-verify] [--pubkey PUBKEY]
                           [--default-boot-label DEFAULT_BOOT_LABEL]
                           [--ostar OSTAR] [--no-grubusb] [--esptar ESPTAR]
                           {a,b,nonbooted,efisys} [{a,b,nonbooted,efisys} ...]

positional arguments:
  {a,b,nonbooted,efisys}
                        The type of update to apply

options:
  -h, --help            show this help message and exit
  --efisys-dev EFISYS_DEV
                        Override device for EFI system partition (found by label
                        by default)
  --efisys-mountpoint EFISYS_MOUNTPOINT
                        Override mountpoint for EFI system partition (found by
                        label in fstab by default)
  --efisys-label EFISYS_LABEL
                        Override label for EFI system partition, default:
                        PSYOPSOSEFI
  --a-dev A_DEV         Override device for A side (found by label by default)
  --a-mountpoint A_MOUNTPOINT
                        Override mountpoint for A side (found by label in fstab
                        by default)
  --a-label A_LABEL     Override label for A side, default: psyopsOS-A
  --b-dev B_DEV         Override device for B side (found by label by default)
  --b-mountpoint B_MOUNTPOINT
                        Override mountpoint for B side (found by label in fstab
                        by default)
  --b-label B_LABEL     Override label for B side, default: psyopsOS-B
  --no-verify           Skip verification of the ostar tarball
  --pubkey PUBKEY       Public key to use for verification (default:
                        /etc/psyopsOS/minisign.pubkey)
  --default-boot-label DEFAULT_BOOT_LABEL
                        Default boot label if writing the grub.cfg file
  --ostar OSTAR         The ostar tarball to apply; required for a/b/nonbooted
  --no-grubusb          Skip updating the grubusb config (only applies when type
                        includes nonbooted)
  --esptar ESPTAR       A tarball to apply to the EFI System Partition when type
                        includes efisys

________________________________________________________________________

> neuralupgrade set-default --help
usage: neuralupgrade set-default [-h] [--efisys-dev EFISYS_DEV]
                                 [--efisys-mountpoint EFISYS_MOUNTPOINT]
                                 [--efisys-label EFISYS_LABEL] [--a-dev A_DEV]
                                 [--a-mountpoint A_MOUNTPOINT]
                                 [--a-label A_LABEL] [--b-dev B_DEV]
                                 [--b-mountpoint B_MOUNTPOINT]
                                 [--b-label B_LABEL]
                                 label

positional arguments:
  label                 The label to set as the default boot label

options:
  -h, --help            show this help message and exit
  --efisys-dev EFISYS_DEV
                        Override device for EFI system partition (found by label
                        by default)
  --efisys-mountpoint EFISYS_MOUNTPOINT
                        Override mountpoint for EFI system partition (found by
                        label in fstab by default)
  --efisys-label EFISYS_LABEL
                        Override label for EFI system partition, default:
                        PSYOPSOSEFI
  --a-dev A_DEV         Override device for A side (found by label by default)
  --a-mountpoint A_MOUNTPOINT
                        Override mountpoint for A side (found by label in fstab
                        by default)
  --a-label A_LABEL     Override label for A side, default: psyopsOS-A
  --b-dev B_DEV         Override device for B side (found by label by default)
  --b-mountpoint B_MOUNTPOINT
                        Override mountpoint for B side (found by label in fstab
                        by default)
  --b-label B_LABEL     Override label for B side, default: psyopsOS-B

<!--[[[end]]]-->
