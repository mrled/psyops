# psyopsOS-base package

This is an Alpine package for the psyopsOS base system.o

## Installed to the ISO directly

This is installed to the ISO filesystem when the ISO image is created,
meaning that its post-install script runs before the image is even booted.

This gives us a good place to configure things that should be up before the system boots at all,
like the root password.

This is the only way I know of to get a script to change the ISO filesystem.
Static files can easily be copied from the genapkovl script,
but modifying a base file, like /etc/shadow, is not possible from genapkovl.

## Does not depend on progfiguration

`progfiguration` is a package used to configure psyopsOS, but also other operating systems.
When installed in psyopsOS,
it maybe installed after this package,
so we do not depend on it here.