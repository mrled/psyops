# Redesigning psyopsOS in 2023

The current system is great but it has a few downsides.

- No A/B updates, which I am so jealous of gokrazy for having
- Long ISO generation times: mksquashfs + mkisofs are both pretty slow
- Updating requires talking to each remote machine individually
- It's hard to test, would like to add qemu tests

## Add A/B updates

- Run this process in Docker; this is important so I don't need a dedicated Alpine system (which I also have to maintain) for builds, and I can build from different versions of Alpine easily
- Make a disk image file, partition it for EFI, install GRUB, and add two partitions for A/B

## Squashfs or initramfs?

- To add squashfs support I have to regenerate initrd anyway. I did this and it works fine.
- However, looking at initramfs-init, there is no reason not to use its existing support for applying apkovl to the initramfs system running in memory. When Alpine is run in diskless mode with lbu/apkovl, it never switches root to something else, it just uses the kernel and initramfs that it booted with. Because I would have to make my own initramfs in order to support squashfs anyway, there's no reason to bother with squashfs.
- The ISO image does a couple of convenient things I could replicate: apk package cache and modloop
- apk package cache allows having packages available that aren't installed. If I'm regenerating initramfs anyway I guess I don't need this, I can just install the packages I need in that. OTOH, having them in a separate package cache is even easier; it lets me install them in a normal alpine way with apkovl.
- modloop requires some investigation, not sure how the iso script does that yet.
- HOWEVER, the entire decompressed initramfs is kept in RAM, while a squashfs root only loads into RAM what is actually being used (same as when loading from a normal r/w filesystem like ext4, i guess).
- In other systems I've worked on, the machine has no local storage (and is not using network storage like NFS root), and when it boots, iPXE pulls the kernel and initrd into RAM via HTTP. In this system, we do have local storage, so we ought to use it to offload RAM.
- Experimenting 20231203, I found that adding all the APKs from my psyopsOS world file to initrd and running cpio|gz resulted in a 590MB compressed initrd and a 1.4GB uncompressed directory. That's just a quick and dirty test, and could be pared down, but it's an order of magnitude worse than the default tiny initrd of 58MB compressed / 189MB uncompressed.

### apkovl support without modifying initramfs

I wanted to make this work, but I don't think it's possible with A/B updates.

initramfs-init automatically searches for apkovl on attached USB drives, but how would it know which one applies to the booting A/B partition?

I can pass `apkovl=[URL|PATH]`, and the PATH can start with a device name like sda1 and init will mount that disk to find it, but I don't know the Linux device name when GRUB boots the kernel.

These are both solvable problems IF I have control of initramfs-init, but there's no way I can see to solve them without customizing init and rebuilding initramfs.

I guess it's worth thinking about how apkovl and psyopsOS are the same and different.

- apkovl is applied on top of a running system.
  It's designed to support changes made to a single system running from RAM.
  Although it's also used in the ISO generation to support the generic ISO image.
- psyopsOS applies progfigsite on top of a running system.
  It's designed to support centralized changes to all systems from a single source of configuration.

These goals have significant overlap, but they aren't the same.

### Custom initramfs

- You can do light initramfs customizations that use mkinitfs by patching the initramfs-init script, creating files on the root filesystem, and listing them in a custom feature
- However, you can't easily install an apk package with mkinitfs. (You could install it on the root and list all its files in a custom feature, but this would be awkward for even a modest number of packges, and you'd also have to include /etc/apk and I'm not sure if that's a good idea.)
    - Actually I think this might be wrong - `mkinitsf -b BASE` if you prepare BASE specially. `update-kernel` does this, maybe we could do that.
- Instead we could use a chroot to create a custom initrd, and use a custom init script. This is annoying, but gives us full control

How to make a custom initrd

- Chroot, install whatever packages we want, install whatever arbitrary files we want
- There is some weird logic in mkinitfs for including just the kernel modules needed to boot and potentially find a root filesystem. we could borrow this logic and use modloop like Alpine does. We could also just take the RAM hit and load all kernel modules into our custom initrd. They're over 100MB for the lts kernel, but about 25MB for the virt kernel, so there would be some significant RAM savings if we did modloop, especially since most modules will never be loaded, and the size of the modules dir will likely only go up with time.
- The way mkimage.sh works for building ISO images, it runs a command called `update-kernel` which runs `mkinitfs`. `update-kernel` also handles building the modloop.
- The result is a very small initramfs which can get any module it needs from the modloop.

## Faster updates for fleet

- Once we have A/B updates, doing automatic updates for the non-running partition becomes safer
- The other issue with updates is breaking changes to the progfigsite package
    - Can I address that with progfigsite tests?

## qemu tests

- What we need is something repeatable
- It looks like qemu supports much of what we'd need for this, including attaching virtual USB drives
