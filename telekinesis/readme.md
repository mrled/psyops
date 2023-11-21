# Telekinesis

The PSYOPS build and administration tool.

This package is used instead of a Makefile or the `invoke` module.

It doesn't need to cover applying `progfiguration_blacksite` to managed nodes,
but it handles other psyopOS related administration tasks.

## Help

<!--[[[cog
#
# This section is generated with cog
# Run `cog -r readme.md` and it will overwrite the help output below with the latest.
#

import cog
from telekinesis.argparsestr import get_argparse_help_string
from telekinesis.cli.tk import makeparser
cog.outl(get_argparse_help_string("tk", makeparser(prog="tk"), wrap=0))
]]]-->
> tk --help
usage: tk [-h] [--debug] {showconfig,deaddrop,builder,mkimage,buildpkg,deployiso} ...

Telekinesis: the PSYOPS build and administration tool

positional arguments:
  {showconfig,deaddrop,builder,mkimage,buildpkg,deployiso}
    showconfig          Show the current configuration
    deaddrop            Manage the S3 bucket used for psyopOS, called deaddrop, or its local replica
    builder             Actions related to the psyopsOS Docker container that is used for making Alpine packages and ISO images
    mkimage             Make a psyopsOS image
    buildpkg            Build a package
    deployiso           Deploy the ISO image to the S3 bucket

options:
  -h, --help            show this help message and exit
  --debug, -d           Open the debugger if an unhandled exception is encountered.

________________________________________________________________________

> tk showconfig --help
usage: tk showconfig [-h]

options:
  -h, --help  show this help message and exit

________________________________________________________________________

> tk deaddrop --help
usage: tk deaddrop [-h] {ls,forcepull,forcepush} ...

positional arguments:
  {ls,forcepull,forcepush}
    ls                  List the files in the bucket
    forcepull           Pull files from the bucket into the local replica and delete any local files that are not in the bucket... we don't do a
                        nicer sync operation because APKINDEX files can't be managed that way.
    forcepush           Push files from the local replica to the bucket and delete any bucket files that are not in the local replica.

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
usage: tk builder build [-h] [--rebuild] [--interactive] [--clean] [--dangerous-no-clean-tmp-dir]

options:
  -h, --help            show this help message and exit
  --rebuild             Rebuild the build container even if it already exists
  --interactive         Run a shell in the container instead of running the build command
  --clean               Clean the docker volume before running
  --dangerous-no-clean-tmp-dir
                        Don't clean the temporary directory containing the APK key

________________________________________________________________________

> tk builder runcmd --help
usage: tk builder runcmd [-h] [--rebuild] [--interactive] [--clean] [--dangerous-no-clean-tmp-dir] command [command ...]

positional arguments:
  command               The command to run in the container, like 'whoami' or 'ls -larth'. Note that if any of the arguments start with a dash,
                        you'll need to use '--' to separate the command from the arguments, like '... build runcmd -- ls -larth'.

options:
  -h, --help            show this help message and exit
  --rebuild             Rebuild the build container even if it already exists
  --interactive         Run a shell in the container instead of running the build command
  --clean               Clean the docker volume before running
  --dangerous-no-clean-tmp-dir
                        Don't clean the temporary directory containing the APK key

________________________________________________________________________

> tk mkimage --help
usage: tk mkimage [-h] [--rebuild] [--interactive] [--clean] [--dangerous-no-clean-tmp-dir] [--skip-build-apks]

options:
  -h, --help            show this help message and exit
  --rebuild             Rebuild the build container even if it already exists
  --interactive         Run a shell in the container instead of running the build command
  --clean               Clean the docker volume before running
  --dangerous-no-clean-tmp-dir
                        Don't clean the temporary directory containing the APK key
  --skip-build-apks     Don't build APKs before building ISO

________________________________________________________________________

> tk buildpkg --help
usage: tk buildpkg [-h] [--rebuild] [--interactive] [--clean] [--dangerous-no-clean-tmp-dir] {base,blacksite} [{base,blacksite} ...]

positional arguments:
  {base,blacksite}      The package(s) to build

options:
  -h, --help            show this help message and exit
  --rebuild             Rebuild the build container even if it already exists
  --interactive         Run a shell in the container instead of running the build command
  --clean               Clean the docker volume before running
  --dangerous-no-clean-tmp-dir
                        Don't clean the temporary directory containing the APK key

________________________________________________________________________

> tk deployiso --help
usage: tk deployiso [-h] host

positional arguments:
  host        The remote host to deploy to, assumes root@ accepts the psyops SSH key

options:
  -h, --help  show this help message and exit

<!--[[[end]]]-->
