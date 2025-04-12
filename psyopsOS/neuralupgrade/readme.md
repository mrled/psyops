# NEURALUPGRADE

A Python package responsible for
applying psyopsOS OS / EFI upgrades.
Used by both the `tk` build tool and on psyopsOS nodes.

(My third attempt of this so far.)

## Command sketch

```sh
# Show
#
# Show latest version on deaddrop
neuralupgrade show os --latest
# Show specific version on deaddrop
neuralupgrade show os --version $SOME_VERSION
# Show a/b/efisys partition information, versions, etc
neuralupgrade show booted
# Show version of some downloaded update
neuralupgrade show --minisig /path/to/some/psyopsOS.tar.minisig

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
neuralupgrade apply nonbooted --ostar /path/to/some/psyopsOS.tar
# Ignore the signature (perhaps if the image was just built locally)
neuralupgrade apply nonbooted --ostar /path/to/some/psyopsOS.tar --no-verify
# When writing to a disk image or other unusual scenarios, you may need to pass explicit A/B sides and device names
neuralupgrade apply a --efisys-dev /dev/loop0p1 --a-dev /dev/loop0p3
# Write updates to a a new disk or disk image
neuralupgrade apply a b efisys --efisys-dev /dev/loop0p1 --a-dev /dev/loop0p3 --b-dev /dev/loop0p4 --os-tar /path/to/psyopsOS.tar --esp-tar /path/to/psyopsESP.tar
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

## `neuralupgrade show` on machines not running psyopsOS

You can see output on machines that are not running psyopsOS by using the `--mock-*` argumenhts.

<!--[[[cog
import io
from contextlib import redirect_stdout
import cog
from neuralupgrade.cmd import main_implementation

command = ["neuralupgrade", "--booted-mock=psyopsOS-A", "--efisys-mock", "--efisys-mountpoint=./tests/data/scenarios/ab_same/efisys", "--a-mock", "--a-mountpoint=./tests/data/scenarios/ab_same/a", "--b-mock", "--b-mountpoint=./tests/data/scenarios/ab_same/b", "show"]
f = io.StringIO()
with redirect_stdout(f):
  main_implementation(command)
promptcmd = "user@host> " + " \\\n    ".join(command)
cmdout = f.getvalue()
cog.out(f"```text\n{promptcmd}\n{cmdout}\n```\n")
]]]-->
```text
user@host> neuralupgrade \
    --booted-mock=psyopsOS-A \
    --efisys-mock \
    --efisys-mountpoint=./tests/data/scenarios/ab_same/efisys \
    --a-mock \
    --a-mountpoint=./tests/data/scenarios/ab_same/a \
    --b-mock \
    --b-mountpoint=./tests/data/scenarios/ab_same/b \
    show
system:
    a:
        fs:
            label: psyopsOS-A
            device: /dev/mock/psyopsOS-A
            mountpoint: ./tests/data/scenarios/ab_same/a
            mockmount: True
        metadata:
            running: False
            next_boot: False
            type: psyopsOS
            filename: psyopsOS.x86_64.20240705-173840.tar
            version: 20240705-173840
            kernel: 6.6.36-0-lts
            alpine: 3.20
            architecture: x86_64
        running: False
        next_boot: False
    b:
        fs:
            label: psyopsOS-B
            device: /dev/mock/psyopsOS-B
            mountpoint: ./tests/data/scenarios/ab_same/b
            mockmount: True
        metadata:
            running: False
            next_boot: False
            type: psyopsOS
            filename: psyopsOS.x86_64.20240705-173840.tar
            version: 20240705-173840
            kernel: 6.6.36-0-lts
            alpine: 3.20
            architecture: x86_64
        running: False
        next_boot: False
    firmware:
        fs:
            label: PSYOPSOSEFI
            device: /dev/mock/PSYOPSOSEFI
            mountpoint: ./tests/data/scenarios/ab_same/efisys
            mockmount: True
        metadata:
            type: psyopsESP
            filename: psyopsESP.x86_64.20240705-173849.tar
            version: 20240705-173849
            efi_programs: memtest64.efi,tcshell.efi
        neuralupgrade_info:
            last_updated: 20250308-040402
            default_boot_label: psyopsOS-A
            extra_programs: /memtest64.efi,/tcshell.efi
    booted_label: psyopsOS-A
    nonbooted_label: psyopsOS-B
    nextboot_label: psyopsOS-A

```
<!--[[[end]]]-->

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
usage: neuralupgrade [-h] [--debug] [--verbose] [--no-verify] [--pubkey PUBKEY]
                     [--efisys-dev EFISYS_DEV]
                     [--efisys-mountpoint EFISYS_MOUNTPOINT]
                     [--efisys-label EFISYS_LABEL] [--efisys-mock]
                     [--a-dev A_DEV] [--a-mountpoint A_MOUNTPOINT]
                     [--a-label A_LABEL] [--a-mock] [--b-dev B_DEV]
                     [--b-mountpoint B_MOUNTPOINT] [--b-label B_LABEL]
                     [--b-mock] [--update-tmpdir UPDATE_TMPDIR]
                     [--booted-mock BOOTED_MOCK] [--architecture ARCHITECTURE]
                     [--repository REPOSITORY]
                     [--psyopsOS-filename-format PSYOPSOS_FILENAME_FORMAT]
                     [--psyopsESP-filename-format PSYOPSESP_FILENAME_FORMAT]
                     {show,download,check,apply,set-default} ...

Update psyopsOS boot media

positional arguments:
  {show,download,check,apply,set-default}
                        Subcommand to run
    show                Show information about the running system and/or
                        updates. By default shows running system information.
    download            Download updates
    check               Check whether the running system is up to date
    apply               Apply psyopsOS or EFI system partition updates
    set-default         Set the default boot label in the grub.cfg file

options:
  -h, --help            show this help message and exit
  --debug, -d           Drop into pdb on exception
  --verbose, -v         Verbose logging

Verification options:
  --no-verify           Skip verification of the ostar tarball
  --pubkey PUBKEY       Public key to use for verification (default:
                        /etc/psyopsOS/minisign.pubkey)

Device/mountpoint override options:
  --efisys-dev EFISYS_DEV
                        Override device for EFI system partition (found by label
                        by default)
  --efisys-mountpoint EFISYS_MOUNTPOINT
                        Override mountpoint for EFI system partition (found by
                        label in fstab by default)
  --efisys-label EFISYS_LABEL
                        Override label for EFI system partition, default:
                        PSYOPSOSEFI
  --efisys-mock         Do not actually mount anything to the efisys mountpoint,
                        just use its contents as-is; requires --efisys-
                        mountpoint
  --a-dev A_DEV         Override device for A side (found by label by default)
  --a-mountpoint A_MOUNTPOINT
                        Override mountpoint for A side (found by label in fstab
                        by default)
  --a-label A_LABEL     Override label for A side, default: psyopsOS-A
  --a-mock              Do not actually mount anything to the a mountpoint, just
                        use its contents as-is; requires --a-mountpoint
  --b-dev B_DEV         Override device for B side (found by label by default)
  --b-mountpoint B_MOUNTPOINT
                        Override mountpoint for B side (found by label in fstab
                        by default)
  --b-label B_LABEL     Override label for B side, default: psyopsOS-B
  --b-mock              Do not actually mount anything to the b mountpoint, just
                        use its contents as-is; requires --b-mountpoint
  --update-tmpdir UPDATE_TMPDIR
                        Temporary directory for update downloads
  --booted-mock BOOTED_MOCK
                        Mock the booted side, either 'a' or 'b'

Repository options:
  --architecture ARCHITECTURE
                        Architecture for the update, default is whatever `uname
                        -m` says: arm64. WARNING: NO VERIFICATION IS DONE TO
                        ENSURE THIS MATCHES THE ACTUAL ARCHITECTURE OF THE
                        UPDATE. USE WITH CAUTION.
  --repository REPOSITORY
                        URL for the psyopsOS update repository, default:
                        https://psyops.micahrl.com/os
  --psyopsOS-filename-format PSYOPSOS_FILENAME_FORMAT
                        The format string for the versioned psyopsESP tarfile.
                        Used as the base for the filename in S3, and also of the
                        signature file.
  --psyopsESP-filename-format PSYOPSESP_FILENAME_FORMAT
                        The format string for the versioned psyopsOS tarfile.
                        Used as the base for the filename in S3, and also of the
                        signature file.

________________________________________________________________________

> neuralupgrade show --help
usage: neuralupgrade show [-h] [--list-targets] [target ...]

positional arguments:
  target          What to show information about. Defaults to showing
                  information about the running system. See --list-targets for
                  more information.

options:
  -h, --help      show this help message and exit
  --list-targets  List the available targets for the 'show' subcommand

________________________________________________________________________

> neuralupgrade download --help
usage: neuralupgrade download [-h] [--version VERSION]
                              [--type {psyopsOS,psyopsESP} [{psyopsOS,psyopsESP} ...]]
                              output

positional arguments:
  output                Where to download update(s). If it ends in a slash,
                        treated as a directory and download the default filename
                        of the update. If multiple types are passed, this must
                        be a directory.

options:
  -h, --help            show this help message and exit
  --version VERSION     Version of the update to download, default: latest
  --type {psyopsOS,psyopsESP} [{psyopsOS,psyopsESP} ...]
                        The type of update to download

________________________________________________________________________

> neuralupgrade check --help
usage: neuralupgrade check [-h] [--version VERSION]
                           [--target {a,b,nonbooted,efisys} [{a,b,nonbooted,efisys} ...]]

options:
  -h, --help            show this help message and exit
  --version VERSION     Version of the update to check, default: latest
  --target {a,b,nonbooted,efisys} [{a,b,nonbooted,efisys} ...]
                        The target filesystem(s) to check

________________________________________________________________________

> neuralupgrade apply --help
usage: neuralupgrade apply [-h] [--default-boot-label DEFAULT_BOOT_LABEL]
                           [--no-grub-cfg]
                           [--os-tar OS_TAR | --os-version OS_VERSION]
                           [--esp-tar ESP_TAR | --esp-version ESP_VERSION]
                           {a,b,nonbooted,efisys} [{a,b,nonbooted,efisys} ...]

positional arguments:
  {a,b,nonbooted,efisys}
                        The target(s) to apply updates to

options:
  -h, --help            show this help message and exit
  --default-boot-label DEFAULT_BOOT_LABEL
                        Default boot label if writing the grub.cfg file
  --no-grub-cfg         Skip updating the grub.cfg file (only applies when
                        target includes nonbooted)
  --os-tar OS_TAR       A local path to a psyopsOS tarball to apply
  --os-version OS_VERSION
                        A version in the remote repository to apply
  --esp-tar ESP_TAR     A local path to an efisys tarball to apply
  --esp-version ESP_VERSION
                        A version in the remote repository to apply

________________________________________________________________________

> neuralupgrade set-default --help
usage: neuralupgrade set-default [-h] label

positional arguments:
  label       The label to set as the default boot label

options:
  -h, --help  show this help message and exit

<!--[[[end]]]-->
