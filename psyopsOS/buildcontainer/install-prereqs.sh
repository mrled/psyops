#!/bin/sh -eu

# Include everything necessary for building psyopsOS images and our apk packages.
apk add \
    abuild \
    age \
    alpine-base \
    alpine-conf \
    alpine-sdk \
    apk-tools \
    bash \
    bind-tools \
    build-base \
    busybox \
    dosfstools \
    e2fsprogs \
    e2fsprogs-extra \
    fakeroot \
    findmnt \
    git \
    gpg \
    lsblk \
    make \
    minisign \
    mtools \
    ncurses \
    openssh \
    openssl \
    parted \
    python3 \
    py3-build \
    py3-installer \
    py3-pip \
    py3-requests \
    py3-setuptools \
    py3-tz \
    py3-wheel \
    ripgrep \
    rsync \
    shadow \
    sqlite \
    squashfs-tools \
    sudo \
    tmux \
    vim \
    wget \
    xorriso

# Install architecture-specific packages without running their package scripts.
# Some packages have scripts that will only work on a system that is going to boot with the package.
# For instance, GRUB tries to run grub-probe, which fails in Docker with an error like this:
#     (2/2) Installing grub-efi (2.06-r2)
#     Executing busybox-1.35.0-r17.trigger
#     Executing grub-2.06-r2.trigger
#     /usr/sbin/grub-probe: error: failed to get canonical path of `overlay'.
#     ERROR: grub-2.06-r2.trigger: script exited with error 1
# We need the grub binaries installed to build a bootable ISO,
# but we don't need it to actually work on the Docker system, so we skip these.

# Architecture specific packages
archpkgs=""
case $(uname -m) in
    aarch64)
        # the linux-rpi kernel contains
        #   a kernel in raw Image format (not compressed)
        #   NO initrd
        #   device trees for Raspberry Pi
        #   d3evbice tree overlays (.dtbo files) for Raspberry Pi
        #   System.map, config, etc
        archpkgs="${archpkgs} linux-rpi"
        # raspberrypi-bootloader contains
        #   /boot/fixup.dat
        #   /boot/fixup4.dat
        #   /boot/start.elf
        #   /boot/start4.elf
        archpkgs="${archpkgs} raspberrypi-bootloader"
        # u-boot-raspberrypi contains
        #   /usr/share/u-boot/rpi_arm64/u-boot.bin
        archpkgs="${archpkgs} u-boot-raspberrypi"
        # u-boot-tools contains
        #   the U-Boot mkimage binary
        archpkgs="${archpkgs} u-boot-tools"
        ;;
    x86_64)
        # grub-efi contains grub-install etc
        archpkgs="${archpkgs} grub-efi"
        # linux-firmware-intel has CPU microcode
        archpkgs="${archpkgs} linux-firmware-intel"
        # linux-firmware-mediatek has WiFi firmware
        archpkgs="${archpkgs} linux-firmware-mediatek"
        # linux-firmware-rtl_bt has Bluetooth firmware
        archpkgs="${archpkgs} linux-firmware-rtl_bt"
        # linux-lts is the long-term support kernel built by Alpine
        archpkgs="${archpkgs} linux-lts"
        # syslinux contains the SYSLINUX bootloader, and some tools for building bootable USB drives, I think
        archpkgs="${archpkgs} syslinux"
        ;;
esac

apk add --no-scripts ${archpkgs}
