# psyopsOS aports-scripts

These scripts require a working aports development environment, see
[How to make a custom ISO image with mkimage](https://wiki.alpinelinux.org/wiki/How_to_make_a_custom_ISO_image_with_mkimage).

The `build.sh` script will create a psyopsOS image in ~/isos.
See that script for some globals, including the location of aports (assumed to be ~/aports).
It is expected you'll run this script as the `build` user with `NOPASSWD: ALL` sudo permissions --
a dedicated build VM is recommended.

The first build will take a few minutes (~5 on my VM on my 2020 Intel MBP).
We set the workdir and this makes rebuilds lightning fast.

## Notes to self

- You can't get into the ISO filesystem chroot? But you can build an apkovl, which is probably good enough, and lighter weight
- Lots of stuff is undocumented or severely under-documented, even like command line options, but the source shell scripts are short. No way around reading them.