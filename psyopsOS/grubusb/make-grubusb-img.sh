#!/bin/sh
set -eux

script=$(basename "$0")

# Default argument values
outimg=
loopdev=/dev/loop0
efisize=128
psyabsize=1024
memtest=

# Constant values
label_efisys=PSYOPSOSEFI # max 11 chars, no lower case
label_psya=psyopsOS-A # max 16 chars, case sensitive
label_psyb=psyopsOS-B # max 16 chars, case sensitive

usage() {
    cat <<ENDUSAGE
$script: Make a bootable USB drive for psyopsOS
Usage: $script [-h] [-l LOOPDEV] [-e EFISIZE] [-s PSYOPSOSSIZE] [-m MEMTEST] -p PSYOPSOSDIR -o OUTPUTIMG

ARGUMENTS:
    -h                      Show this help message
    -l LOOPDEV              Loop device to use (default: "$loopdev")
    -e EFISIZE              Size in MiB of the EFI partition
                            (default: "$efisize")
    -s PSYOPSOSIZE          Size in MiB of EACH of the psyopsOS-A/B partitions
                            (default: "$psyabsize")
    -m MEMTEST              Path to the memtest86+ binary to use (optional)
    -p PSYOPSOSDIR          Directory containing psyopsOS files to use (required)
                            Should contain kernel, initramfs, modloop, etc; see below.
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
        2. psyopsOS-A partition, ext4, size PSYABSIZE, label $label_psya
        3. psyopsOS-B partition, ext4, size PSYABSIZE, label $label_psyb
    * The total size of the image is (EFISIZE + (2 * PSYABSIZE))
* To get the memtest binary, download the "Pre-Compiled Bootable Binary (.zip)"
  file from <https://memtest.org/>, extract it, and pass the "memtest64.efi"
  file to this script with the -m option.
* The PSYOPSOSDIR must contain the following files:
    * kernel
    * initramfs
    * modloop
* The PSYOPSOSDIR may contain additional files:
    * DTB files (if your platform/kernel uses them)
    * System.map for kernel debugging
    * config showing the kernel config
    * any other files you want to include in the OS image

ENDUSAGE
}

while test $# -gt 0; do
    case "$1" in
    -h) usage; exit 0;;
    -l) loopdev="$2"; shift 2;;
    -e) efisize="$2"; shift 2;;
    -s) psyabsize="$2"; shift 2;;
    -m) memtest="$2"; shift 2;;
    -p) psyosdir="$2"; shift 2;;
    -o) outimg="$2"; shift 2;;
    -*) echo "Unknown option: $1; see '$script -h'" >&2; exit 1;;
    *) echo "Unknown argument: $1; see '$script -h'" >&2; exit 1;;
    esac
done

if test -z "$outimg"; then
    echo "Missing required argument(s); see '$script -h'" >&2
    exit 1
fi

# Derived argument values
part_efisys="${loopdev}p1"
part_psya="${loopdev}p2"
part_psyb="${loopdev}p3"

cleanup() {
    echo "======== Cleaning up..."
    losetup -a
    umount /mnt/grubusb/efisys || true
    umount /mnt/grubusb/psya || true
    umount /mnt/grubusb/psyb || true
    losetup -d "$loopdev" || true
    for loop in /dev/loop?; do
        losetup -d "$loop" || true
    done
    # Delete devices created by losetup_mknod
    rm "$part_efisys" || true
    rm "$part_psya" || true
    rm "$part_psyb" || true
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
imgsize=$(( efi_start + efisize + ( 2 * psyabsize ) + end_buffer ))
psya_start=$(( efi_start + efisize ))
psyb_start=$(( psya_start + psyabsize ))
psyb_end=$(( psyb_start + psyabsize ))

# 1048576 == 1MiB
dd if=/dev/zero of="$outimg" bs=1048576 count=$imgsize

# Note that this requires a privileged container (docker run --privileged=true)
losetup "$loopdev" "$outimg"

parted -s "$loopdev" mklabel gpt
parted -s "$loopdev" mkpart primary fat32   ${efi_start}MiB     ${psya_start}MiB
parted -s "$loopdev" mkpart primary ext4    ${psya_start}MiB    ${psyb_start}MiB
parted -s "$loopdev" mkpart primary ext4    ${psyb_start}MiB    ${psyb_end}MiB
parted -s "$loopdev" set 1 boot on

# After partitioning, we need to mknod the partition devices
losetup_mknod

# Set up the psyopsOS-A partition
mkfs.ext4 -L "$label_psya" "$part_psya"
mkdir -p /mnt/grubusb/psya
mount "$part_psya" /mnt/grubusb/psya
cp -r "$psyosdir"/* /mnt/grubusb/psya

# Set up the psyopsOS-B partition
# This contains the same files as psyopsOS-A so either works out of the box,
# but it's designed to allow A/B updates.
mkfs.ext4 -L "$label_psyb" "$part_psyb"
mkdir -p /mnt/grubusb/psyb
mount "$part_psyb" /mnt/grubusb/psyb
cp -r "$psyosdir"/* /mnt/grubusb/psyb

# Set up the EFI system partition
mkfs.fat -F32 -n "$label_efisys" "$part_efisys"
mkdir -p /mnt/grubusb/efisys
mount "$part_efisys" /mnt/grubusb/efisys
# I don't understand why I need --boot-directory too, but I do
grub-install --target=x86_64-efi --efi-directory=/mnt/grubusb/efisys --boot-directory=/mnt/grubusb/efisys "$part_efisys" --removable

find /mnt/grubusb/efisys

# Kernel parameters added to both A and B menu entries.
#
# debug=all prints dmesg to the screen during boot, and maybe other things
# earlyprintk=dbgp enables early printk, which prints kernel messages to the screen during boot
# console=tty0 and console=ttyS0,115200 enable the kernel to print messages to the screen during boot
#   tty0 is the screen, ttyS0 is the serial port
kernel_params_suffix="earlyprintk=dbgp console=tty0 console=ttyS0,115200"

# Create the grub.cfg file
cat <<EOF > /mnt/grubusb/efisys/grub/grub.cfg
# psyopsOS grub.cfg

set default="$label_psya"
set timeout=5

insmod all_video
set gfxmode=auto
serial --speed=115200 --unit=0 --word=8 --parity=no --stop=1
terminal_input console serial
terminal_output console serial

# This is slow and uselessly verbose
#set debug=all


menuentry "Welcome to psyopsOS grubusb. GRUB configuration last updated: $(date)" {
    echo "Welcome to psyopsOS grubusb. GRUB configuration last updated: $(date)"
}
menuentry "----------------------------------------" {
    echo "----------------------------------------"
}

menuentry "$label_psya" {
    search --no-floppy --label $label_psya --set root
    linux /kernel ro psyopsos=$label_psya $kernel_params_suffix
    initrd /initramfs
}

menuentry "$label_psyb" {
    search --no-floppy --label $label_psyb --set root
    linux /kernel ro psyopsos=$label_psyb $kernel_params_suffix
    initrd /initramfs
}
EOF

if test -n "$memtest"; then
    cp "$memtest" /mnt/grubusb/efisys/memtest64.efi
    cat <<EOF >> /mnt/grubusb/efisys/grub/grub.cfg
menuentry "MemTest86 EFI (64-bit)" {
    insmod part_gpt
    insmod fat
    insmod chain
    search --no-floppy --label $label_efisys --set root
    chainloader /memtest64.efi
}
EOF
fi

cat <<EOF >> /mnt/grubusb/efisys/grub/grub.cfg
menuentry "UEFI fwsetup" {
    fwsetup
}

menuentry "Reboot" {
    reboot
}

menuentry "Poweroff" {
    halt
}

menuentry "Exit GRUB" {
    exit
}
EOF

echo "$script finished successfully"
