#!/bin/sh
set -eux

script=$(basename "$0")

# Default argument values
neuralupgrade=
neuralupgrade_args=
psyostar=
efisystar=
secrettarball=
pubkey=
outimg=
loopdev=/dev/loop0
efisize=128
psyabsize=1536
secretsize=128

# Constant values
label_efisys=PSYOPSOSEFI # max 11 chars, no lower case
label_psya=psyopsOS-A # max 16 chars, case sensitive
label_psyb=psyopsOS-B # max 16 chars, case sensitive
label_secret="psyops-secret" # max 16 chars, case sensitive

usage() {
    cat <<ENDUSAGE
$script: Make a bootable USB drive for psyopsOS
Usage: $script [-h] [OPTIONS ...] -n NEURALUPGRADE -p PSYOPSOSTAR -E EFISYSTAR -V PUBKEY -o OUTPUTIMG

ARGUMENTS:
    -h                      Show this help message
    -l LOOPDEV              Loop device to use (default: "$loopdev")
    -e EFISIZE              Size in MiB of the EFI partition
                            (default: "$efisize")
    -s PSYOPSOSIZE          Size in MiB of EACH of the psyopsOS-A/B partitions
                            (default: "$psyabsize")
    -x SECRETTARBALL        Path to the secret tarball to use (optional)
                            If not specified, secret partition will be empty
    -y SECRETSIZE           Size in MiB of the secret partition
                            (default: "$secretsize")
    -n NEURALUPGRADE        Path to the neural upgrade binary to use
    -N NEURALUPGRADEARGS    Arguments to pass to the neural upgrade binary
    -p PSYOPSOSTAR          Path to a psyopsOS tarball to use
    -E EFISYSTAR            Path to a tarball containing extra files for the
                            EFI system partition
    -V PUBKEY               Path to the minisign public key to use for
                            verifying tarballs
    -o OUTPUTIMG            Path to the image file to create (required)

* This script requires a privileged container (docker run --privileged=true)
* Expects these packages:
    * dosfstools (a FAT32 partition is required for EFI boot)
    * e2fsprogs (we use ext4 for its resilience to power loss for OS images)
    * grub-efi
    * lsblk
    * parted
* Creates an output image with a GPT partition table:
    * Creates the following partitions:
        1. EFI system partition, FAT32, size EFISIZE, label $label_efisys
        2. psyopsOS secret partition, ext4, size SECRETSIZE, label $label_secret
        3. psyopsOS A partition, ext4, size PSYABSIZE, label $label_psya
        4. psyopsOS B partition, ext4, size PSYABSIZE, label $label_psyb
    * The total size of the image is (EFISIZE + (2 * PSYABSIZE))
* The PSYOPSOSTAR must contain the following files:
    * kernel
    * initramfs
    * modloop
    * squashfs
* The PSYOPSOSTAR may contain additional files:
    * DTB files (if your platform/kernel uses them)
    * System.map for kernel debugging
    * config showing the kernel config
    * any other files you want to include in the OS image
* The EFISYSTAR may contain additional files for the EFI system partition
  such as a memtest86+ binary.
* The SECRETTARBALL must contain the files psyopsOS expects to find in the
  secret partition, see system-secrets-individuation.md for details.

ENDUSAGE
}

while test $# -gt 0; do
    case "$1" in
    -h) usage; exit 0;;
    -l) loopdev="$2"; shift 2;;
    -e) efisize="$2"; shift 2;;
    -s) psyabsize="$2"; shift 2;;
    -x) secrettarball="$2"; shift 2;;
    -y) secretsize="$2"; shift 2;;
    -n) neuralupgrade="$2"; shift 2;;
    -N) neuralupgrade_args="$2"; shift 2;;
    -p) psyostar="$2"; shift 2;;
    -E) efisystar="$2"; shift 2;;
    -V) pubkey="$2"; shift 2;;
    -o) outimg="$2"; shift 2;;
    -*) echo "Unknown option: $1; see '$script -h'" >&2; exit 1;;
    *) echo "Unknown argument: $1; see '$script -h'" >&2; exit 1;;
    esac
done

for arg in "$efisystar" "$neuralupgrade" "$psyostar" "$pubkey" "$outimg"; do
    if test -z "$arg"; then
        echo "Missing required argument(s); see '$script -h'" >&2
        exit 1
    fi
done

# Derived argument values
part_efisys="${loopdev}p1"
part_secret="${loopdev}p2"
part_psya="${loopdev}p3"
part_psyb="${loopdev}p4"
mntbase="/mnt/psyopsOSimg"

cleanup() {
    echo "======== Cleaning up..."
    set +e
    for mount in "$mntbase"/*; do
        mountpoint -q "$mount" || continue
        umount "$mount"
    done
    for loop in $(losetup -a | cut -d: -f1); do
        losetup -d "$loop"
    done
    # Delete devices created by losetup_mknod
    rm "$part_efisys"
    rm "$part_secret"
    rm "$part_psya"
    rm "$part_psyb"
    losetup -a
    echo "======== Done cleaning up."
}

trap cleanup EXIT

# In Docker, "losetup" doesn't create the device nodes, so we have to do it ourselves.
# See: <https://github.com/moby/moby/issues/27886>
losetup_mknod() {
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
        partdev=$(( partdev + 1 ))
    done
}

# Partition math
efi_start=1 # don't start at 0, cargo culting this
end_buffer=1 # math is hard, so we add a little extra space at the end
imgsize=$(( efi_start + efisize + secretsize + ( 2 * psyabsize ) + end_buffer ))
secret_start=$(( efi_start + efisize ))
psya_start=$(( secret_start + secretsize ))
psyb_start=$(( psya_start + psyabsize ))
psyb_end=$(( psyb_start + psyabsize ))

# Create a sparse output image file - seek to the end but write nothing
# 1048576 == 1MiB
test -f "$outimg" && rm "$outimg"
dd if=/dev/zero of="$outimg" bs=1048576 seek=$imgsize count=0

# Note that this requires a privileged container (docker run --privileged=true)
losetup "$loopdev" "$outimg"

parted -s "$loopdev" mklabel gpt
parted -s "$loopdev" mkpart primary fat32   ${efi_start}MiB     ${secret_start}MiB
parted -s "$loopdev" mkpart primary ext4    ${secret_start}MiB  ${psya_start}MiB
parted -s "$loopdev" mkpart primary ext4    ${psya_start}MiB    ${psyb_start}MiB
parted -s "$loopdev" mkpart primary ext4    ${psyb_start}MiB    ${psyb_end}MiB
parted -s "$loopdev" set 1 boot on

# After partitioning, we need to mknod the partition devices
losetup_mknod

# Set up the psyopsOS-A partition
mkfs.ext4 -L "$label_psya" "$part_psya"
mkdir -p "$mntbase"/psya

# Set up the psyopsOS-B partition
# This contains the same files as psyopsOS-A so either works out of the box,
# but it's designed to allow A/B updates.
mkfs.ext4 -L "$label_psyb" "$part_psyb"
mkdir -p "$mntbase"/psyb

# Set up the EFI system partition
mkfs.fat -F32 -n "$label_efisys" "$part_efisys"
mkdir -p "$mntbase"/efisys

# Install psyopsOS A/B and the EFI system partition
"$neuralupgrade" \
    $neuralupgrade_args \
    "--verbose" \
    --efisys-dev "$part_efisys" \
    --efisys-mountpoint "$mntbase"/efisys \
    --a-dev "$part_psya" \
    --a-mountpoint "$mntbase"/psya \
    --b-dev "$part_psyb" \
    --b-mountpoint "$mntbase"/psyb \
    --pubkey "$pubkey" \
    apply \
    --default-boot-label "$label_psya" \
    --os-tar "$psyostar" \
    --esp-tar "$efisystar" \
    a b efisys

# Set up the secret partition
mkfs.ext4 -L "$label_secret" "$part_secret"
ls -alF "$secrettarball"
if test -n "$secrettarball"; then
    mkdir -p "$mntbase"/secret
    mount "$part_secret" "$mntbase"/secret
    tar xf "$secrettarball" -C "$mntbase"/secret
    umount "$mntbase"/secret
fi

trap - EXIT
cleanup

echo "$script finished successfully"
