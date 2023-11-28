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

# Derived values
patchedinit="$initdir"/initramfs-init.patched

patch -o "$patchedinit" "$initdir"/initramfs-init.orig "$initdir"/initramfs-init.psyopsOS.patch

if test -z "$features"; then
    feats=
else
    feats=$(echo "$features" | tr ',' ' ')
fi
test -z "$kvers" && kvers=$(uname -r)

mkinitfs -K -o "$outfile" ${feats:+-F "$feats"} -i "$patchedinit" "$kvers"
