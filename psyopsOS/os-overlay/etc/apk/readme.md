# About apk overlays

* APKs in the `world` file is installed when the system boots.
  This is an Alpine construct.
  * Aside from packages strictly required for psyopsOS to work at all,
    this should contain troubleshooting tools for systems too broken
    for progfiguration to have run, networking to have started, etc.
* The APKs in the `available` file are added to the ISO when it is built.
  This happens in `mkimg.psyopsOS.sh`, and is a psyopsOS construct.
  * Packages not listed here can still be used by progfiguration (or whatever configuration tool).
    This is an optimization to allow progfiguration
    to get packages from the ISO instead of pulling from the Internet.
  * We keep this list separate from `world` to decouple core psyopsOS stuff from progfiguration stuff.
  * Also, some large packages might be useful to cache but will not be installed on all nodes.
* Note that the version of APKs saved to the ISO from either source
  will become useless the longer the ISO is used,
  as `apk` will find newer versions on remote repos and install them instead.
* Neither file supports comments!
