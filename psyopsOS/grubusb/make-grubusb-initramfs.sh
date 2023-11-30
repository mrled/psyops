#!/bin/sh
set -eux

script=$(basename "$0")

# Default argument values
outfile=
features=
kvers=

usage() {
    cat <<ENDUSAGE
$script: Make an initramfs for psyopsOS
Usage: $script [-h]

ARGUMENTS:
    -h                      Show this help message
    -o OUTFILE              Output file name (required)
    -I INITDIR              Directory containing psyopsOS initramfs files
                            (required)
    -F FEATURES             Generate initrd with these mkinitfs features
                            Can be comma- or space- separated
    -K KVERS                The kernel version to use with mkinitfs,
                            where modules are assumed to exist in /lib/modules;
                            defaults to the running kernel
ENDUSAGE
}

while test $# -gt 0; do
    case "$1" in
    -h) usage; exit 0;;
    -o) outfile="$2"; shift 2;;
    -I) initdir="$2"; shift 2;;
    -F) features="$2"; shift 2;;
    -K) kvers="$2"; shift 2;;
    -*) echo "Unknown option: $1; see '$script -h'" >&2; exit 1;;
    *) echo "Unknown argument: $1; see '$script -h'" >&2; exit 1;;
    esac
done

if [ -z "$outfile" ] || [ -z "$initdir" ]; then
    echo "Missing required arguments" >&2
    usage >&2
    exit 1
fi

# If kvers was not passed, assume the running kernel
test -z "$kvers" && kvers=$(uname -r)

# Derived values
patchedinit="$initdir"/initramfs-init.patched.grubusb

# Create fstab
# Use the mkinitfs fstab as a starting point
# Add some psyopsOS-specific entries that are nice to have in the rescue shell
cat </usr/share/mkinitfs/fstab >/tmp/fstab <<EOF
LABEL=PSYOPSOSEFI /efisys vfat ro 0 0
LABEL=psyopsOS-A /a ext4 ro 0 0
LABEL=psyopsOS-B /b ext4 ro 0 0
EOF

patch -o "$patchedinit" "$initdir"/initramfs-init.orig "$initdir"/initramfs-init.psyopsOS.grubusb.patch
mkinitfs -K -o "$outfile" ${feats:+-F "$feats"} -i "$patchedinit" "$kvers"
