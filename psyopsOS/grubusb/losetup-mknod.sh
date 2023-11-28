#!/bin/sh -eu

usage() {
    cat <<ENDUSAGE
$(basename "$0"): mknod after losetup
Usage: $(basename "$0") LOOPDEV

Options:
    -h                      Show this help message
    LOOPDEV                 Loop device to mknod

In Docker, "losetup" doesn't create the device nodes, so we have to do it ourselves.

EXAMPLE:
    # First, create an image file and create one partition in it
    losetup /dev/loop0 /path/to/file.img
    # At this point, there is no /dev/loop0p1
    $(basename "$0") /dev/loop0
    # Now there is a /dev/loop0p1

SEE ALSO:
- https://github.com/moby/moby/issues/27886
ENDUSAGE
}

loopdev=
while test $# -gt 0; do
    case "$1" in
    -h) usage; exit 0;;
    -*) echo "Unknown option: $1" >&2; exit 1;;
    *) loopdev="$1"; shift;;
    esac
done

if test -z "$loopdev"; then
    echo "Missing required argument: LOOPDEV" >&2
    usage >&2
    exit 1
elif ! test -b "$loopdev"; then
    echo "LOOPDEV is not a block device: $loopdev" >&2
    exit 1
fi

# The lsblk command returns a list of MAJ:MIN pairs, one per line
# The first line is the LOOPDEV itself. This already exists, so we skip it.
# Each subsequent line is MAJ:MIN for a child partition.
partitions=$(lsblk --raw --output "MAJ:MIN" --noheadings ${loopdev} | tail -n +2)

partdev=1
for i in $partitions; do
    maj=$(echo $i | cut -d: -f1)
    min=$(echo $i | cut -d: -f2)
    if test ! -e "${loopdev}p${partdev}"; then
        mknod "${loopdev}p${partdev}" b $maj $min
    fi
    partdev=$((partdev + 1))
done
