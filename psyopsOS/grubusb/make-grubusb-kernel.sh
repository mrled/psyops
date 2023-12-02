#!/bin/sh
set -eux

script=$(basename "$0")

# Default argument values
apk_keys_dir=/etc/apk/keys
apk_packages=
apk_repos_file=/etc/apk/repositories
arch=$(apk --print-arch)
features=
initdir=
kflavor=lts
outdir=

usage() {
    cat <<ENDUSAGE
$script: Make kernel, initramfs, etc for psyopsOS grubusb
Usage: $script [-h]

ARGUMENTS:
    -h                      Show this help message
    --apk-keys-dir          Directory containing signing keys
                            Default: "$apk_keys_dir"
    --apk-packages          Packages to install
    --apk-packages-file     File containing packages to install;
                            may be specified more than once
    --apk-repositories      Repositories file to use
                            Default: "$apk_repos_file"
    --arch                  Architecture to build for
                            Default: the system arch: "$arch"
    --kernel-flavor         Kernel flavor to use
                            Default: "$kflavor"
    --mkinitfs-features     Generate initrd with these mkinitfs features
                            Default: get from mkinitfs.conf
    --outdir                Output directory (required)
    --psyopsOS-init-dir     Directory containing psyopsOS initramfs files
                            (required)

FILES:
    We require abuild configuration to contain the packager signing key.
        /etc/abuild.conf
        ~/.abuild/abuild.conf

    If --mkinitfs-features is not passed, get defaults from the host's
        /etc/mkinitfs/mkinitfs.conf
    Note that this is different behavior from upstream update-kernel script,
    which installs mkinitfs to the rootfs dir and uses its stock config.

ABOUT:
    Inspired by Alpine Linux update-kernel, as called in build_kernel() in mkimg.base.sh.
ENDUSAGE
}

while test $# -gt 0; do
    case "$1" in
    -h|--help) usage; exit 0;;
    --apk-keys-dir) apk_keys_dir="$2"; shift 2;;
    --apk-packages) apk_packages="$2"; shift 2;;
    --apk-packages-file) apk_packages="$apk_packages $(cat "$2")"; shift 2;;
    --apk-repositories) apk_repos_file="$2"; shift 2;;
    --arch) arch="$2"; shift 2;;
    --kernel-flavor) kflavor="$2"; shift 2;;
    --mkinitfs-features) features="$2"; shift 2;;
    --outdir) outdir="$2"; shift 2;;
    --psyopsOS-init-dir) initdir="$2"; shift 2;;
    -*) echo "Unknown option: $1; see '$script -h'" >&2; exit 1;;
    *) echo "Unknown argument: $1; see '$script -h'" >&2; exit 1;;
    esac
done

if [ -z "$initdir" ] || [ -z "$outdir" ]; then
    echo "Missing required arguments" >&2
    usage >&2
    exit 1
fi

# Make a temporary working directory
workdir=/tmp/make-grubusb-kernel.$$
mkdir -p "$workdir"

cleanup() {
    rm -rf "$workdir"
}
trap cleanup EXIT

# Derived argument values
rootfs=$workdir/root
bootdir=$rootfs/boot
apk_packages="$apk_packages alpine-base linux-$kflavor linux-firmware"

# Read external configuration
test -f /etc/abuild.conf && . /etc/abuild.conf
test -f "$HOME"/.abuild/abuild.conf && . "$HOME"/.abuild/abuild.conf
pubkey="${PACKAGER_PUBKEY:-"${PACKAGER_PRIVKEY}.pub"}"
if ! test -f "$pubkey" || ! test -f "$PACKAGER_PRIVKEY"; then
    echo "Packager private key file ($PACKAGER_PRIVKEY) and/or public key file ($pubkey) do not exist" >&2
    exit 1
fi

if [ -z "$features" ]; then
	. /etc/mkinitfs/mkinitfs.conf
fi
# We always require base and squashfs
features="base squashfs $features"

#### Functions

# Run apk in the rootfs
rooted_apk() {
    cmd="$1"
    shift
    apk $cmd -p $rootfs --arch "$arch" --keys-dir $apk_keys_dir --repositories-file "$apk_repos_file" "$@"
}

# Extract kernel modules and make module dependency list
make_depmod() {
    kvers="$1"
    find $rootfs/lib/modules \
        -name \*.ko.gz -exec gunzip {} + \
        -o -name \*.ko.xz -exec unxz {} + \
        -o -name \*.ko.zst -exec unzstd --rm {} + \
        -o ! -name '' # don't fail if no files found. busybox find doesn't support -true
    depmod -b $rootfs "$kvers"
}

# Make the modloop squashfs image
# This contains the kernel modules and firmware, but doesn't take up space in the initramfs
make_modloop() {
    modloop=$1
    modloopstage=$2
    modimg=$3
    modsig_path=$4
    modimg_path=$modloopstage/$modimg

    mkdir $modloop $modloopstage
    cp -a $rootfs/lib/modules $modloop
    mkdir -p $modloop/modules/firmware
    find $rootfs/lib/modules -type f -name "*.ko*" | xargs modinfo -k $kvers -F firmware | sort -u | while read FW; do
        for f in "$rootfs"/lib/firmware/$FW; do
            if ! [ -e "$f" ]; then
                continue
            fi
            install -pD "$f" "$modloop/modules/firmware/${f#*/lib/firmware}"
            # copy also all potentially associated files
            for _file in "${f%.*}".*; do
                install -pD "$_file" "$modloop/modules/firmware/${_file#*/lib/firmware/}"
            done
        done
    done

    # Taken from update-kernel, which can accept $modloopfw via a cli option; not sure what the use case for this is.
    #
    # install extra firmware files in modloop (i.e. not detected by modinfo)
    # for _xfw in $modloopfw; do
    #     if [ -f "$rootfs/lib/firmware/$_xfw" ]; then
    #         install -pD "$rootfs/lib/firmware/$_xfw" \
    #             "$modloop"/modules/firmware/"$_xfw"
    #     else
    #         echo "Warning: extra firmware \"$_xfw\" not found!"
    #     fi
    # done

    # wireless regulatory db
    if [ -e "$rootfs"/lib/modules/*/kernel/net/wireless/cfg80211.ko* ]; then
        for _regdb in "$rootfs"/lib/firmware/regulatory.db*; do
            [ -e "$_regdb" ] && install -pD "$_regdb" "$modloop"/modules/firmware/"${_regdb##*/}"
        done
    fi

    # include bluetooth firmware in modloop
    if [ -e "$rootfs"/lib/modules/*/kernel/drivers/bluetooth/btbcm.ko* ]; then
        for _btfw in "$rootfs"/lib/firmware/brcm/*.hcd; do
            install -pD "$_btfw" \
                "$modloop"/modules/firmware/brcm/"${_btfw##*/}"
        done
    fi

    case $arch in
        armhf) mksfs="-Xbcj arm" ;;
        armv7|aarch64) mksfs="-Xbcj arm,armthumb" ;;
        x86|x86_64) mksfs="-Xbcj x86" ;;
        *) mksfs=
    esac
    mksquashfs $modloop "$modloopstage/$modimg" -comp xz -exit-on-error $mksfs

    # Sign the modloop
    openssl dgst -sha1 -sign "$PACKAGER_PRIVKEY" -out "$modsig_path" "$modloopstage/$modimg"
}

# Include the device tree blobs (used in e.g. ARM)
include_dtb() {
    dtbdir=
    for possible_dtbdir in \
        $rootfs/boot/dtbs-$kflavor \
        $rootfs/usr/lib/linux-$kvers \
        $rootfs/boot
    do
        if test -d "$possible_dtbdir"; then
            dtbdir="$possible_dtbdir"
            echo "Found dtbdir: $dtbdir" >&2
            break
        fi
    done
    if test -z "$dtbdir"; then
        echo "No dtbdir found; assume our platform doesn't need it" >&2
        return 0
    fi


    _opwd=$PWD
    case "$kflavor" in
        rpi*) _dtb="$outdir/" ;;
        *)    _dtb="$outdir/boot/dtbs-$kflavor" ;;
    esac
    mkdir -p "$_dtb"
    _dtb=$(realpath "$_dtb")
    cd "$dtbdir"
    find -type f \( -name "*.dtb" -o -name "*.dtbo" \) | cpio -pudm "$_dtb"
    cd "$_opwd"
}

# Make an fstab for the initramfs
# Include some psyopsOS-specific entries that are nice to have in the rescue shell
make_fstab() {
    cat </usr/share/mkinitfs/fstab <<EOF
LABEL=PSYOPSOSEFI /efisys vfat ro 0 0
LABEL=psyopsOS-A /a ext4 ro 0 0
LABEL=psyopsOS-B /b ext4 ro 0 0
EOF
}

#### Main

# Create output directory
mkdir -p "$outdir"

# Creates APKINDEX etc in the rootfs
rooted_apk add --initdb --update-cache

# Install packages
# Running this with --no-scripts still seems to run pre-install scripts, can that be right?
# I notice trying to install nebula-openrc fails bc it creates a user on the host system,
# ... not the rootfs.
rooted_apk add --no-scripts $apk_packages

# Copy pubkey file to rootfs
mkdir -p "$rootfs"/etc/apk/keys
cp "$pubkey" "$rootfs"/etc/apk/keys/

# Find the kernel version
kvers=$(basename $(ls -d $rootfs/lib/modules/*"$kflavor"))

make_depmod "$kvers"

# Create modloop
modloopstage=$workdir/boot
modloop=$workdir/modloop
modimg=modloop-$kflavor
modsig_path="$workdir"/$modimg.SIGN.RSA.${pubkey##*/}
make_modloop "$modloop" "$modloopstage" "$modimg" "$modsig_path"

# Make the initramfs
make_fstab >"$workdir"/fstab
patchedinit="$initdir"/initramfs-init.patched.grubusb
patch -o "$patchedinit" "$initdir"/initramfs-init.orig "$initdir"/initramfs-init.psyopsOS.grubusb.patch
mkinitfs -s $modsig_path -i "$patchedinit" -q -b $rootfs -F "$features" -f "$workdir"/fstab -o "$outdir"/initramfs-$kflavor $kvers

for file in System.map config vmlinuz; do
	if [ -f "$bootdir/$file-$kflavor" ]; then
		cp "$bootdir/$file-$kflavor" $modloopstage
	else
		cp "$bootdir/$file" $modloopstage
	fi
done

mv $modloopstage/* "$outdir"

include_dtb
