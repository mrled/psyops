# Telekinesis

The PSYOPS build and administration tool.

This package is used instead of a Makefile or the `invoke` module.

It doesn't need to cover applying `progfiguration_blacksite` to managed nodes,
but it handles other psyopsOS related administration tasks.

## Examples

```sh
# Create the build container
tk builder build

# Run a command inside the build container
tk builder runcmd -- ls -alF /

# Run mkimage.sh from the aports checkout in the build container (for debugging)
tk builder runcmd -- ./mkimage.sh -h

# Build packages in the build container
tk buildpkg base blacksite neuralupgrade-apk

# Build everything required for a bootable disk image
tk mkimage diskimg --stages kernel squashfs efisystar ostar diskimg

# Build OS tarballs and copy them to local deaddrop
tk mkimage diskimg --stages efisystar efisystar-dd ostar ostar-dd

# Rebuild a single package, but not the other packates
tk buildpkg neuralupgrade-apk &&
  tk mkimage --skip-build-apks diskimg --stages squashfs ostar efisystar

# Rebuild certain packages, make OS tarballs, and upload everything to deaddrop
tk buildpkg neuralupgrade-apk &&
  tk mkimage --skip-build-apks diskimg --stages squashfs kernel ostar ostar-dd efisystar efisystar-dd &&
  tk deaddrop forcepush
```

## Dependencies

* Docker.
  The Alpine build process must run on an existing Alpine system;
  using Docker lets us run this anywhere, including macOS.
* An `aports` checkout.
  This should match the version of the [builder system Dockerfile](../psyopsOS/buildcontainer/Dockerfile).
  `git fetch --tags` to get all the latest tags,
  and then check it out with something like `git checkout v3.19.1`.
  The scripts look in the `psyops` parent directory for an `aports` repository,
  but can be configured to look anywhere.

## Troubleshooting

Errors can be hard to track down,
because we use a lot of custom infrastructure to emulate the normal Alpine build environment,
which isn't perfectly documented to begin with.

In general, try looking at what commands failed to run in Docker
(the build container prints out its commands before it runs them)
and running them inside a Docker container yourself.
The best way to do that is with `tk mkimage --interactive`,
which will run all the prep code,
start the Docker container,
and print what it would have run in non-interactive mode for you to run yourself.

Each stage might run more than one container,
and it'll make each one interactive.

Interactive mode requires building for just one architecture,
you'll save time by just running the failing stage interactively,
and you might want to skip building the APK packages,
so the full command is probably something like
`tk --architecture x86_64 mkimage --skip-build-apks --interactive diskimg --stages squashfs`.
Argument order is important.

### Rebuild the docker container

If you get errors like the following,
it's an indication that the apk cache on the image has gone stale:

```text
Signing: /tmp/update-kernel.KAKJJL/boot/modloop-lts
ERROR: intel-ucode-20220510-r0: No such file or directory
gzip: invalid magic
```

The easiest way to handle this is to rebuild the build container with
`tk builder build`.

### Check aports

Note that wherever you keep your local `aports` checkout, you'll have to keep that updated as well.
If you get build errors in the mkimage phase, this is probably part of the problem!

Additionally:
The Alpine image build system dot-sources ALL mkimage.*.sh files.
This is intended so you can define functions like `profile_psyopsOS() { ... }`,
but we can also abuse it to override built-in functions that don't have any other hooks.

Compare any overridden functions in that file to the original versions in the `aports` repo and adjust as necessary.

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
usage: tk [-h] [--debug] [--verbose] [--architecture ARCHITECTURE]
          {showconfig,cog,deaddrop,builder,mkimage,buildpkg,deployos,vm,psynet,signify}
          ...

Telekinesis: the PSYOPS build and administration tool

positional arguments:
  {showconfig,cog,deaddrop,builder,mkimage,buildpkg,deployos,vm,psynet,signify}
    showconfig          Show the current configuration
    cog                 Run cog on all relevant files
    deaddrop            Manage the S3 bucket used for psyopsOS, called deaddrop,
                        or its local replica
    builder             Actions related to the psyopsOS Docker container that is
                        used for making Alpine packages and ISO images
    mkimage             Make a psyopsOS image
    buildpkg            Build a package
    deployos            Deploy the ISO image to a psyopsOS remote host
    vm                  Run VM(s)
    psynet              Manage psynet
    signify             Sign and verify with the psyopsOS signature tooling

options:
  -h, --help            show this help message and exit
  --debug, -d           Open the debugger if an unhandled exception is
                        encountered.
  --verbose, -v         Print more information about what is happening.
  --architecture ARCHITECTURE
                        The architecture(s) to build for. Default:
                        x86_64,aarch64.

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
                  {iso,diskimg} ...

positional arguments:
  {iso,diskimg}
    iso                 Build an ISO image using mkimage.sh and the psyopsOScd
                        profile
    diskimg             Build a disk image that contains GRUB, can do A/B
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

> tk mkimage diskimg --help
usage: tk mkimage diskimg [-h]
                          [--stages {mkinitpatch,applyinitpatch,kernel,squashfs,efisystar,efisystar-dd,ostar,ostar-dd,sectar,diskimg} [{mkinitpatch,applyinitpatch,kernel,squashfs,efisystar,efisystar-dd,ostar,ostar-dd,sectar,diskimg} ...]]
                          [--list-stages] [--node-secrets NODE_SECRETS]

options:
  -h, --help            show this help message and exit
  --stages {mkinitpatch,applyinitpatch,kernel,squashfs,efisystar,efisystar-dd,ostar,ostar-dd,sectar,diskimg} [{mkinitpatch,applyinitpatch,kernel,squashfs,efisystar,efisystar-dd,ostar,ostar-dd,sectar,diskimg} ...]
                        The stages to build. Default: ['kernel', 'squashfs',
                        'diskimg']. See --list-stages for all possible stages
                        and their descriptions.
  --list-stages         Show all possible stages and their descriptions.
  --node-secrets NODE_SECRETS
                        If passed, generate a node-specific image with a
                        populated secrets volume containing secrets from
                        'progfiguration-blacksite-node save NODENAME ...'.

________________________________________________________________________

> tk buildpkg --help
usage: tk buildpkg [-h] [--rebuild] [--interactive] [--clean]
                   [--dangerous-no-clean-tmp-dir]
                   {base,blacksite,neuralupgrade-apk,neuralupgrade-pyz}
                   [{base,blacksite,neuralupgrade-apk,neuralupgrade-pyz} ...]

positional arguments:
  {base,blacksite,neuralupgrade-apk,neuralupgrade-pyz}
                        The package(s) to build

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

> tk deployos --help
usage: tk deployos [-h] [--type {iso,diskimg}] host

positional arguments:
  host                  The remote host to deploy to, assumes root@ accepts the
                        psyops SSH key

options:
  -h, --help            show this help message and exit
  --type {iso,diskimg}  The type of image to deploy

________________________________________________________________________

> tk vm --help
usage: tk vm [-h] {diskimg,osdir,profile} ...

positional arguments:
  {diskimg,osdir,profile}
    diskimg             Run the disk image in qemu
    osdir               Run the kernel/initramfs from the osdir in qemu without
                        building a disk image with EFI and A/B partitions
    profile             Run a predefined VM profile (a shortcut for running
                        specific VMs like qreamsqueen which we use for testing
                        psyopsOS)

options:
  -h, --help            show this help message and exit

________________________________________________________________________

> tk vm diskimg --help
usage: tk vm diskimg [-h] [--disk-image DISK_IMAGE] [--macaddr MACADDR]

options:
  -h, --help            show this help message and exit
  --disk-image DISK_IMAGE
                        Path to the disk image
  --macaddr MACADDR     The MAC address to use for the VM, defaults to
                        00:00:00:00:00:00

________________________________________________________________________

> tk vm osdir --help
usage: tk vm osdir [-h]

options:
  -h, --help  show this help message and exit

________________________________________________________________________

> tk vm profile --help
usage: tk vm profile [-h] [--list-profiles] {qreamsqueen}

positional arguments:
  {qreamsqueen}    The profile to run. See --list-profiles for all possible
                   profiles and their descriptions.

options:
  -h, --help       show this help message and exit
  --list-profiles  Show all possible profiles and their descriptions.

________________________________________________________________________

> tk psynet --help
usage: tk psynet [-h] {run,get,set} ...

positional arguments:
  {run,get,set}
    run          Run a command in the context of the psynet certificate
                 authority
    get          Get a node from the psynet
    set          Set a node in the psynet

options:
  -h, --help     show this help message and exit

________________________________________________________________________

> tk psynet run --help
usage: tk psynet run [-h] [--cadir CADIR] command [command ...]

positional arguments:
  command        The command to run in the context of the psynet certificate
                 authority. If any of the arguments start with a dash, you'll
                 need to use '--' to separate the command from the arguments,
                 like '... psynet run -- ls -larth'.

options:
  -h, --help     show this help message and exit
  --cadir CADIR  The directory containing the psynet certificate authority. If
                 not passed, a temporary directory is created, and deleted along
                 with its contents when the command exits.

________________________________________________________________________

> tk psynet get --help
usage: tk psynet get [-h] node

positional arguments:
  node        The node to get

options:
  -h, --help  show this help message and exit

________________________________________________________________________

> tk psynet set --help
usage: tk psynet set [-h] node crt key

positional arguments:
  node        The node to set
  crt         The filename of the node's certificate
  key         The filename of the node's key

options:
  -h, --help  show this help message and exit

________________________________________________________________________

> tk signify --help
usage: tk signify [-h] {sign,verify} ...

positional arguments:
  {sign,verify}
    sign         Sign a file
    verify       Verify a file

options:
  -h, --help     show this help message and exit

________________________________________________________________________

> tk signify sign --help
usage: tk signify sign [-h] file

positional arguments:
  file        The file to sign

options:
  -h, --help  show this help message and exit

________________________________________________________________________

> tk signify verify --help
usage: tk signify verify [-h] file

positional arguments:
  file        The file to verify

options:
  -h, --help  show this help message and exit

<!--[[[end]]]-->
