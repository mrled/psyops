#!/bin/sh
set -eux

script=$(basename "$0")

# Default argument values
apk_keys_dir=/etc/apk/keys
apk_local_repo=
apk_repos_file=/etc/apk/repositories
features=
initdir=
kflavor=lts
dtbs_dir=
outdir=

usage() {
    cat <<ENDUSAGE
$script: Make kernel, initramfs, etc for psyopsOS
Usage: $script [-h]

This script must be run by root.

ARGUMENTS:
    -h                      Show this help message
    --apk-local-repo        Local repository path to use (optional)
                            Will be used for apk add,
                            but not be copied to initramfs repositories file
    --apk-keys-dir          Directory containing signing keys
                            Default: "$apk_keys_dir"
    --apk-repositories      Repositories file to use;
                            will be copied to initramfs
                            Default: "$apk_repos_file"
    --kernel-flavor         Kernel flavor to use
                            Default: "$kflavor"
    --dtbs-dir              If passed, include this directory in the initramfs
                            Default: none
    --mkinitfs-features     Generate initrd with these mkinitfs features
                            Default: get from mkinitfs.conf
    --outdir                Output directory (required)
    --psyopsOS-init-dir     Directory containing psyopsOS initramfs files
                            (required)

ENVIRONMENT VARIABLES:
    PACKAGER_PRIVKEY        Path to the packager private key
    PACKAGER_PUBKEY         Path to the packager public key

FILES:
    We look in abuild configuration for the packager signing key.
        /etc/abuild.conf
        ~/.abuild/abuild.conf

    If --mkinitfs-features is not passed, get defaults from the host's
        /etc/mkinitfs/mkinitfs.conf
    Note that this is different behavior from upstream update-kernel script,
    which installs mkinitfs to the initramroot dir and uses its stock config.

ABOUT:
    Inspired by Alpine Linux update-kernel, as called in build_kernel() in mkimg.base.sh.
ENDUSAGE
}

while test $# -gt 0; do
    case "$1" in
    -h|--help) usage; exit 0;;
    --apk-keys-dir) apk_keys_dir="$2"; shift 2;;
    --apk-local-repo) apk_local_repo="$2"; shift 2;;
    --apk-repositories) apk_repos_file="$2"; shift 2;;
    --kernel-flavor) kflavor="$2"; shift 2;;
    --dtbs-dir) dtbs_dir="$2"; shift 2;;
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

if [ "$(id -u)" != 0 ]; then
    echo "This script must be run by root" >&2
    exit 1
fi

# Make a temporary working directory
workdir=/tmp/make-psyopsOS-kernel.$$
if test -d "$workdir"; then
    echo "Temporary working directory $workdir already exists; aborting" >&2
    exit 1
fi
mkdir -p "$workdir"

cleanup() {
    # Remove the temporary workdir
    rm -rf "$workdir"
}
trap cleanup EXIT

# Derived argument values
initramroot=$workdir/initramroot
bootdir=$initramroot/boot
initial_apk_packages="alpine-base linux-$kflavor linux-firmware"

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

# Extract kernel modules and make module dependency list
make_depmod() {
    kvers="$1"
    find $initramroot/lib/modules \
        -name \*.ko.gz -exec gunzip {} + \
        -o -name \*.ko.xz -exec unxz {} + \
        -o -name \*.ko.zst -exec unzstd --rm {} + \
        -o ! -name '' # don't fail if no files found. busybox find doesn't support -true
    depmod -b $initramroot "$kvers"
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
    cp -a $initramroot/lib/modules $modloop
    mkdir -p $modloop/modules/firmware
    find $initramroot/lib/modules -type f -name "*.ko*" | xargs modinfo -k $kvers -F firmware | sort -u | while read FW; do
        for f in "$initramroot"/lib/firmware/$FW; do
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
    #     if [ -f "$initramroot/lib/firmware/$_xfw" ]; then
    #         install -pD "$initramroot/lib/firmware/$_xfw" \
    #             "$modloop"/modules/firmware/"$_xfw"
    #     else
    #         echo "Warning: extra firmware \"$_xfw\" not found!"
    #     fi
    # done

    # wireless regulatory db
    if [ -e "$initramroot"/lib/modules/*/kernel/net/wireless/cfg80211.ko* ]; then
        for _regdb in "$initramroot"/lib/firmware/regulatory.db*; do
            [ -e "$_regdb" ] && install -pD "$_regdb" "$modloop"/modules/firmware/"${_regdb##*/}"
        done
    fi

    # include bluetooth firmware in modloop
    if [ -e "$initramroot"/lib/modules/*/kernel/drivers/bluetooth/btbcm.ko* ]; then
        for _btfw in "$initramroot"/lib/firmware/brcm/*.hcd; do
            install -pD "$_btfw" \
                "$modloop"/modules/firmware/brcm/"${_btfw##*/}"
        done
    fi

    case $(apk --print-arch) in
        armhf) mksfs="-Xbcj arm" ;;
        armv7|aarch64) mksfs="-Xbcj arm,armthumb" ;;
        x86|x86_64) mksfs="-Xbcj x86" ;;
        *) mksfs=
    esac
    test -f "$modloopstage/$modimg" && rm "$modloopstage/$modimg"
    mksquashfs $modloop "$modloopstage/$modimg" -comp xz -exit-on-error $mksfs

    # Sign the modloop
    openssl dgst -sha1 -sign "$PACKAGER_PRIVKEY" -out "$modsig_path" "$modloopstage/$modimg"
}

# Include the device tree blobs (used in e.g. ARM).
# The flow here comes from Alpine scripts.
# TODO: include dtbo files as well?
include_dtb() {
    _outdir=$1

    # The upstream update-kernel script differentiates between RPi and non-RPi in this way.
    # However, I think that if we boot GRUB on the RPi, this may not be important?
    # TODO: test RPi booting with this disabled.
    case "$kflavor" in
        rpi*) _dtb="$_outdir/" ;;
        *)    _dtb="$_outdir/boot/dtbs-$kflavor" ;;
    esac

    _opwd=$PWD
    mkdir -p "$_dtb"
    _dtb=$(realpath "$_dtb")
    cd "$dtbs_dir"

    # Using find|cpio this way copies just the dtb/dtbo files to the destination directory
    # and preserves directory structure
    find -type f \( -name "*.dtb" -o -name "*.dtbo" \) | cpio -pudm "$_dtb"

    cd "$_opwd"
}

# Set up the initramfs root filesystem
setup_initramfs_root() {
    # Creates APKINDEX etc in the initramroot
    apk add --initdb -p $initramroot --keys-dir $apk_keys_dir --repositories-file "$apk_repos_file" ${apk_local_repo:+-X $apk_local_repo}

    # Install alpine-base and Linux kernel and firmware, but don't run scripts because we're not in a regular system
    apk add --no-scripts -p $initramroot --keys-dir $apk_keys_dir --repositories-file "$apk_repos_file" ${apk_local_repo:+-X $apk_local_repo} alpine-base linux-$kflavor linux-firmware

    # Set up apk keys in initramroot
    mkdir -p "$initramroot"/etc/apk/keys
    cp "$apk_keys_dir"/* "$pubkey" "$initramroot"/etc/apk/keys/
    cp "$apk_repos_file" "$initramroot"/etc/apk/repositories
}

#### Main

# Create output directory
mkdir -p "$outdir"

# Set up the initramfs root filesystem
setup_initramfs_root

# Copy required files from initramfs filesystem to output directory
# This must run after setup_initramfs_root which installs these files
ls -alF "$bootdir"
cp "$bootdir"/vmlinuz-$kflavor "$outdir"/kernel
cp "$bootdir"/config-*-$kflavor "$outdir"/config
cp "$bootdir"/System.map-*-$kflavor "$outdir"/System.map

# Find the kernel version
kvers=$(basename $(ls -d $initramroot/lib/modules/*"$kflavor"))
echo "$kvers" > "$outdir"/kernel.version

make_depmod "$kvers"

# Create modloop
modloopstage=$workdir/boot
modloop=$workdir/modloop
modimg=modloop
modsig_path="$workdir"/$modimg.SIGN.RSA.${pubkey##*/}
make_modloop "$modloop" "$modloopstage" "$modimg" "$modsig_path"

# Make the initramfs
patchedinit="$initdir"/initramfs-init.patched
test -f "$outdir"/initramfs && rm "$outdir"/initramfs
mkinitfs -s $modsig_path -i "$patchedinit" -q -b $initramroot -F "$features" -o "$outdir"/initramfs $kvers

mv $modloopstage/* "$outdir"

if test "$dtbs_dir"; then
    include_dtb "$outdir"
fi

echo "$script finished successfully"
