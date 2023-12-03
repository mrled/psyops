#!/bin/sh
set -eux

script=$(basename "$0")

# Default argument values
apk_keys_dir=/etc/apk/keys
apk_local_repo=
apk_packages=
apk_repos_file=/etc/apk/repositories
features=
initdir=
kflavor=lts
outdir=

usage() {
    cat <<ENDUSAGE
$script: Make kernel, initramfs, etc for psyopsOS grubusb
Usage: $script [-h]

This script must be run by root.

ARGUMENTS:
    -h                      Show this help message
    --apk-local-repo        Local repository path to use (optional)
                            Will be mounted into the rootfs during package
                            installation and used for apk add,
                            but not be copied to initramfs repositories file
    --apk-keys-dir          Directory containing signing keys
                            Default: "$apk_keys_dir"
    --apk-packages          Packages to install
    --apk-packages-file     File containing packages to install;
                            may be specified more than once
    --apk-repositories      Repositories file to use;
                            will be copied to initramfs
                            Default: "$apk_repos_file"
    --kernel-flavor         Kernel flavor to use
                            Default: "$kflavor"
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
    which installs mkinitfs to the rootfs dir and uses its stock config.

ABOUT:
    Inspired by Alpine Linux update-kernel, as called in build_kernel() in mkimg.base.sh.
ENDUSAGE
}

while test $# -gt 0; do
    case "$1" in
    -h|--help) usage; exit 0;;
    --apk-keys-dir) apk_keys_dir="$2"; shift 2;;
    --apk-local-repo) apk_local_repo="$2"; shift 2;;
    --apk-packages) apk_packages="$2"; shift 2;;
    --apk-packages-file) apk_packages="$apk_packages $(cat "$2")"; shift 2;;
    --apk-repositories) apk_repos_file="$2"; shift 2;;
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

if [ "$(id -u)" != 0 ]; then
    echo "This script must be run by root" >&2
    exit 1
fi

# Make a temporary working directory
workdir=/tmp/make-grubusb-kernel.$$
mkdir -p "$workdir"

cleanup() {
    # The unmounting is so verbose, don't xtrace it
    set +x
    # Unmount any filesystems mounted inside the workdir
    while read -r mount ; do
        mountpoint=$(echo "$mount" | cut -d' ' -f2)
        case "$mountpoint" in
            "$workdir"/*) umount "$mountpoint" ;;
        esac
    done </proc/mounts
    # Remove the temporary workdir
    rm -rf "$workdir"
}
trap cleanup EXIT

# Derived argument values
rootfs=$workdir/root
bootdir=$rootfs/boot
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

    case $(apk --print-arch) in
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
    _outdir=$1
    dtbdir=
    # TODO: Why do we look in these directories? Are some of these deprecated?
    for possible_dtbdir in \
        $rootfs/boot/dtbs-$kflavor \
        $rootfs/usr/lib/linux-$kvers \
        $rootfs/boot
    do
        if test -d "$possible_dtbdir"; then
            dtbdir="$possible_dtbdir"
            echo "Found possible dtbdir: $dtbdir" >&2
            break
        fi
    done
    if test -z "$dtbdir"; then
        echo "No dtbdir found; assume our platform doesn't need it" >&2
        return 0
    fi

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
    cd "$dtbdir"

    # Using find|cpio this way copies just the dtb/dtbo files to the destination directory
    # and preserves directory structure
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
# We don't have to do --update-cache because we mount /var/cache/apk from the container into the rootfs below,
# and the container has already run apk update and has a populated cache.
apk add --initdb -p $rootfs --keys-dir $apk_keys_dir --repositories-file "$apk_repos_file"

# Install required packages inside the initramfs root filesystem
# Warning: Installing packages --no-scripts still seems to run pre-install scripts, can that be right?
# I notice trying to install nebula-openrc right here fails bc it creates a user on the host system, not the rootfs.
# For now, just install required initial packages here.
#rooted_apk add --no-scripts $initial_apk_packages

# chroot into the rootfs and install the rest of the packages; this will run scripts
# chroot requires docker run --privileged=true
# We need to use an APK cache both inside and outside the chroot,
# otherwise we get temp errors from Alpine mirrors telling us to back off.
mount -t proc none "$rootfs"/proc
mkdir -p "$rootfs"/etc/apk/keys
cp "$apk_keys_dir"/* "$rootfs"/etc/apk/keys/
cp "$apk_repos_file" "$rootfs"/etc/apk/repositories
# Mount the apk cache from the container into the rootfs for access in the chroot
# This is a Docker volume that contains a regular apk cache; see apk-cache(5)
mount -o bind /var/cache/apk "$rootfs"/var/cache/apk
ln -s /var/cache/apk "$rootfs"/etc/apk/cache
# Mount the local repo from the container into the rootfs for access in the chroot
# This is the directory containing locally-built APK packages, like psyopsOS-base and progfiguration_blacksite
if test -n "$apk_local_repo"; then
    mkdir -p "$rootfs"/$apk_local_repo
    mount -o bind "$apk_local_repo" "$rootfs"/$apk_local_repo
fi
# alpine-base contains busybox etc. Running scripts here creates busybox symlinks in /bin etc.
apk add -p $rootfs --keys-dir $apk_keys_dir --repositories-file "$apk_repos_file" ${apk_local_repo:+-X $apk_local_repo} alpine-base
# Now that busybox is installed, we can chroot
chroot $rootfs /bin/busybox ls -alF /var/cache/apk/
# Install Linux kernel and firmware, but don't run scripts because we're not in a regular system
chroot $rootfs /sbin/apk add ${apk_local_repo:+-X $apk_local_repo} --no-scripts linux-$kflavor linux-firmware
# Install all the Alpine pacakges we want in the initramfs, and do run scripts
chroot $rootfs /sbin/apk add ${apk_local_repo:+-X $apk_local_repo} $apk_packages
find $rootfs

# Copy required files from initramfs filesystem to output directory
cp "$bootdir"/vmlinuz-$kflavor "$outdir"/kernel
cp "$bootdir"/config-$kflavor "$outdir"/config
cp "$bootdir"/System.map-$kflavor "$outdir"/System.map

# Copy pubkey file to rootfs
mkdir -p "$rootfs"/etc/apk/keys
cp "$pubkey" "$rootfs"/etc/apk/keys/

# Find the kernel version
kvers=$(basename $(ls -d $rootfs/lib/modules/*"$kflavor"))

make_depmod "$kvers"

# Create modloop
modloopstage=$workdir/boot
modloop=$workdir/modloop
modimg=modloop
modsig_path="$workdir"/$modimg.SIGN.RSA.${pubkey##*/}
make_modloop "$modloop" "$modloopstage" "$modimg" "$modsig_path"

# Make the initramfs
make_fstab >"$workdir"/fstab
mkdir -p "$rootfs"/efisys "$rootfs"/a "$rootfs"/b
patchedinit="$initdir"/initramfs-init.patched.grubusb
patch -o "$patchedinit" "$initdir"/initramfs-init.orig "$initdir"/initramfs-init.psyopsOS.grubusb.patch
mkinitfs -s $modsig_path -i "$patchedinit" -q -b $rootfs -F "$features" -f "$workdir"/fstab -o "$outdir"/initramfs $kvers

mv $modloopstage/* "$outdir"

include_dtb "$outdir"

echo "$script finished successfully"
