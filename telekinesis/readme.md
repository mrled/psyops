# Telekinesis

The PSYOPS build and administration tool.

This package is used instead of a Makefile or the `invoke` module.

It doesn't need to cover applying `progfiguration_blacksite` to managed nodes,
but it handles other psyopsOS related administration tasks.

## Examples

* Create the build container: `tk builder build`
* Run a command inside the build container: `tk builder runcmd -- ls -alF /`
  * Run `mkimage.sh` from the `aports` checkout in the build container: `tk builder runcmd -- ./mkimage.sh -h`

## Full help

<!--[[[cog
#
# This section is generated with cog
# Run `cog -r readme.md` and it will overwrite the help output below with the latest.
# Or, run `tk cog` and it will run `cog` on this file and any others it knows about.
#

import cog
from telekinesis.argparsestr import get_argparse_help_string
from telekinesis.cli.tk import makeparser
cog.outl(get_argparse_help_string("tk", makeparser(prog="tk")))
]]]-->
> tk --help
usage: tk [-h] [--debug]
          {showconfig,cog,deaddrop,builder,mkimage,buildpkg,deployiso,vm} ...

Telekinesis: the PSYOPS build and administration tool

positional arguments:
  {showconfig,cog,deaddrop,builder,mkimage,buildpkg,deployiso,vm}
    showconfig          Show the current configuration
    cog                 Run cog on all relevant files
    deaddrop            Manage the S3 bucket used for psyopsOS, called deaddrop,
                        or its local replica
    builder             Actions related to the psyopsOS Docker container that is
                        used for making Alpine packages and ISO images
    mkimage             Make a psyopsOS image
    buildpkg            Build a package
    deployiso           Deploy the ISO image to the S3 bucket
    vm                  Run VM(s)

options:
  -h, --help            show this help message and exit
  --debug, -d           Open the debugger if an unhandled exception is
                        encountered.

________________________________________________________________________

> tk showconfig --help
usage: tk showconfig [-h]

options:
  -h, --help  show this help message and exit

________________________________________________________________________

> tk cog --help
usage: tk cog [-h]

options:
  -h, --help  show this help message and exit

________________________________________________________________________

> tk deaddrop --help
usage: tk deaddrop [-h] {ls,forcepull,forcepush} ...

positional arguments:
  {ls,forcepull,forcepush}
    ls                  List the files in the bucket
    forcepull           Pull files from the bucket into the local replica and
                        delete any local files that are not in the bucket... we
                        don't do a nicer sync operation because APKINDEX files
                        can't be managed that way.
    forcepush           Push files from the local replica to the bucket and
                        delete any bucket files that are not in the local
                        replica.

options:
  -h, --help            show this help message and exit

________________________________________________________________________

> tk deaddrop ls --help
usage: tk deaddrop ls [-h]

options:
  -h, --help  show this help message and exit

________________________________________________________________________

> tk deaddrop forcepull --help
usage: tk deaddrop forcepull [-h]

options:
  -h, --help  show this help message and exit

________________________________________________________________________

> tk deaddrop forcepush --help
usage: tk deaddrop forcepush [-h]

options:
  -h, --help  show this help message and exit

________________________________________________________________________

> tk builder --help
usage: tk builder [-h] {build,runcmd} ...

positional arguments:
  {build,runcmd}
    build         Build the psyopsOS Docker container
    runcmd        Run a single command in the container, for testing purposes

options:
  -h, --help      show this help message and exit

________________________________________________________________________

> tk builder build --help
usage: tk builder build [-h] [--rebuild] [--interactive] [--clean]
                        [--dangerous-no-clean-tmp-dir]

options:
  -h, --help            show this help message and exit
  --rebuild             Rebuild the build container even if it already exists
  --interactive         Run a shell in the container instead of running the
                        build command
  --clean               Clean the docker volume before running
  --dangerous-no-clean-tmp-dir
                        Don't clean the temporary directory containing the APK
                        key

________________________________________________________________________

> tk builder runcmd --help
usage: tk builder runcmd [-h] [--rebuild] [--interactive] [--clean]
                         [--dangerous-no-clean-tmp-dir]
                         command [command ...]

positional arguments:
  command               The command to run in the container, like 'whoami' or
                        'ls -larth'. Note that if any of the arguments start
                        with a dash, you'll need to use '--' to separate the
                        command from the arguments, like '... build runcmd -- ls
                        -larth'.

options:
  -h, --help            show this help message and exit
  --rebuild             Rebuild the build container even if it already exists
  --interactive         Run a shell in the container instead of running the
                        build command
  --clean               Clean the docker volume before running
  --dangerous-no-clean-tmp-dir
                        Don't clean the temporary directory containing the APK
                        key

________________________________________________________________________

> tk mkimage --help
usage: tk mkimage [-h] [--rebuild] [--interactive] [--clean]
                  [--dangerous-no-clean-tmp-dir] [--skip-build-apks]
                  {iso,grubusb} ...

positional arguments:
  {iso,grubusb}
    iso                 Build an ISO image using mkimage.sh and the psyopsOScd
                        profile
    grubusb             Build a disk image that contains GRUB, can do A/B
                        updates, and boots to initramfs root images without
                        squashfs.

options:
  -h, --help            show this help message and exit
  --rebuild             Rebuild the build container even if it already exists
  --interactive         Run a shell in the container instead of running the
                        build command
  --clean               Clean the docker volume before running
  --dangerous-no-clean-tmp-dir
                        Don't clean the temporary directory containing the APK
                        key
  --skip-build-apks     Don't build APKs before building ISO

________________________________________________________________________

> tk mkimage iso --help
usage: tk mkimage iso [-h]

options:
  -h, --help  show this help message and exit

________________________________________________________________________

> tk mkimage grubusb --help
usage: tk mkimage grubusb [-h]
                          [--stages {mkinitpatch,applyinitpatch,kernel,squashfs,sectar,diskimg} [{mkinitpatch,applyinitpatch,kernel,squashfs,sectar,diskimg} ...]]
                          [--node-secrets NODE_SECRETS]

options:
  -h, --help            show this help message and exit
  --stages {mkinitpatch,applyinitpatch,kernel,squashfs,sectar,diskimg} [{mkinitpatch,applyinitpatch,kernel,squashfs,sectar,diskimg} ...]
                        The stages to build, comma-separated. Default:
                        ['kernel', 'squashfs', 'diskimg']. mkinitpatch: diff -u
                        initramfs-init.orig initramfs.patched.grubusb >
                        initramfs-init.psyopsOS.grubusb.patch. applyinitpatch:
                        patch -o initramfs-init.patched.grubusb initramfs-
                        init.orig initramfs-init.psyopsOS.grubusb.patch. kernel:
                        Build the kernel/initramfs/etc. squashfs: Build the
                        squashfs root filesystem. sectar: Create a tarball of
                        secrets for the qreamsqueen test VM. diskimg: Build the
                        disk image from the kernel/squashfs.
  --node-secrets NODE_SECRETS
                        If passed, generate a node-specific grubusb image with a
                        populated secrets volume containing secrets from
                        'progfiguration-blacksite-node save NODENAME ...'.

________________________________________________________________________

> tk buildpkg --help
usage: tk buildpkg [-h] [--rebuild] [--interactive] [--clean]
                   [--dangerous-no-clean-tmp-dir]
                   {base,blacksite} [{base,blacksite} ...]

positional arguments:
  {base,blacksite}      The package(s) to build

options:
  -h, --help            show this help message and exit
  --rebuild             Rebuild the build container even if it already exists
  --interactive         Run a shell in the container instead of running the
                        build command
  --clean               Clean the docker volume before running
  --dangerous-no-clean-tmp-dir
                        Don't clean the temporary directory containing the APK
                        key

________________________________________________________________________

> tk deployiso --help
usage: tk deployiso [-h] host

positional arguments:
  host        The remote host to deploy to, assumes root@ accepts the psyops SSH
              key

options:
  -h, --help  show this help message and exit

________________________________________________________________________

> tk vm --help
usage: tk vm [-h] {diskimg,osdir} ...

positional arguments:
  {diskimg,osdir}
    diskimg        Run the grubusb image in qemu
    osdir          Run the kernel/initramfs from the osdir in qemu without
                   building a grubusb image with EFI and A/B partitions

options:
  -h, --help       show this help message and exit

________________________________________________________________________

> tk vm diskimg --help
usage: tk vm diskimg [-h] [--grubusb-image GRUBUSB_IMAGE] [--macaddr MACADDR]

options:
  -h, --help            show this help message and exit
  --grubusb-image GRUBUSB_IMAGE
                        Path to the grubusb image
  --macaddr MACADDR     The MAC address to use for the VM, defaults to
                        00:00:00:00:00:00

________________________________________________________________________

> tk vm osdir --help
usage: tk vm osdir [-h]

options:
  -h, --help  show this help message and exit

<!--[[[end]]]-->
