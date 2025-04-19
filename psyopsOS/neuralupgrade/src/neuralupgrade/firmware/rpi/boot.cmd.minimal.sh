# A minimal boot script for the Raspberry Pi 4.
# Useful during development.
# Just added here as documentation.
#
# Assumes a psyopsOS layout on the USB drive:
# partition 1: FAT32 (boot, contains this script)
# partition 2: ext4 (psyops-secret, not relevant here)
# partition 3: ext4 (psyopsOS A partition, contains kernel, initramfs, dtbs)
# partition 4: ext4 (psyopsOS B partition, not relevant here)

# Starting addresses for kernel and initramfs.
# These are JUST used during boot and do not affect OS runtime;
# Linux will move itself around in memory as needed,
# and initrd is mounted to a tmpfs instance at boot,
# so the original memory buffer from U-Boot is freed.
setenv kernel_addr_r 0x80200000
setenv ramdisk_addr_r 0x82200000
setenv dtb_addr_r 0x8a200000
setenv dtbo_1_addr_r 0x8a100000

echo "Welcome to psyopsOS."
echo ""

usb start

setenv bootargs "psyopsos=psyopsOS-A console=tty0 console=ttyAMA0,115200 earlyprintk ignore_loglevel loglevel=8"
echo "Set bootargs to: ${bootargs}"

echo "ext4load usb 0:3 ${kernel_addr_r} /kernel" &&
ext4load usb 0:3 ${kernel_addr_r} /kernel &&
echo "ext4load usb 0:3 ${ramdisk_addr_r} /initramfs" &&
ext4load usb 0:3 ${ramdisk_addr_r} /initramfs &&
setenv initrdsize ${filesize} &&
echo "setenv initrdsize ${initrdsize}" &&
echo "ext4load usb 0:3 ${dtb_addr_r} /dtbs/bcm2711-rpi-4-b.dtb" &&
ext4load usb 0:3 ${dtb_addr_r} /dtbs/merged.dtb &&
#echo "ext4load usb 0:3 ${dtb_addr_r} /dtbs/merged.dtb" &&
#ext4load usb 0:3 ${dtb_addr_r} /dtbs/merged.dtb &&
echo "fdt addr ${dtb_addr_r}" &&
fdt addr ${dtb_addr_r} &&
echo "fdt resize" &&
fdt resize &&
echo "Printing /soc/serial@7e201000" &&
fdt print /soc/serial@7e201000 &&
echo "ext4load usb 0:3 ${dtbo_1_addr_r} /dtbs/overlays/disable-bt.dtbo" &&
ext4load usb 0:3 ${dtbo_1_addr_r} /dtbs/overlays/disable-bt.dtbo &&
echo "fdt apply ${dtbo_1_addr_r}" &&
fdt apply ${dtbo_1_addr_r} &&
echo "Printing /soc/serial@7e201000 after applying overlay" &&
fdt print /soc/serial@7e201000 &&
echo "Printing /aliases" &&
fdt print /aliases &&
echo "booti ${kernel_addr_r} ${ramdisk_addr_r}:${initrdsize} ${dtb_addr_r}" &&
booti ${kernel_addr_r} ${ramdisk_addr_r}:${initrdsize} ${dtb_addr_r}
