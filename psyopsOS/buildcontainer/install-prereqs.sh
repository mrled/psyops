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
    linux-firmware-intel \
    linux-firmware-mediatek \
    linux-firmware-rtl_bt \
    linux-lts \
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

# Install grub without running its package scripts.
# Grub tries to run grub-probe, which fails in Docker with an error like this:
#     (2/2) Installing grub-efi (2.06-r2)
#     Executing busybox-1.35.0-r17.trigger
#     Executing grub-2.06-r2.trigger
#     /usr/sbin/grub-probe: error: failed to get canonical path of `overlay'.
#     ERROR: grub-2.06-r2.trigger: script exited with error 1
# We need the grub binaries installed to build a bootable ISO,
# but we don't need it to actually work on the Docker system, so we skip these.
apk add grub-efi --no-scripts

# Install architecture specific packages
case $(uname -m) in
    aarch64)
        apk add \
            u-boot-raspberrypi \
            u-boot-tools
        ;;
    x86_64)
        apk add syslinux
        ;;
esac
