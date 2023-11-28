# psyopsOS initramfs-init

This directory contains an unmodified initramfs-init from Alpine,
and a patch with changes to allow switching root to a squashfs image.

To make the patch:

1. Copy `initramfs-init.orig` to `initramfs-init.patched.wip`
2. Modify `initramfs-init.patched.wip`
3. `diff -u initramfs-init.orig initramfs-init.patched.wip > initramfs-init.psyopsOS.patch`

Don't commit `initramfs-init.new`.
When building a grubusb image, it runs
`patch -o initramfs-init.patched initramfs-init.orig initramfs-init.psyopsOS.patch`
