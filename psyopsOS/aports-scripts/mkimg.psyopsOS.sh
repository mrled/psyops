if test -z "$PSYOPSOS_OVERLAY"; then
	echo "Missing environment variable \$PSYOPSOS_OVERLAY"
	exit 1
fi

apkworld="$PSYOPSOS_OVERLAY"/etc/apk/world
apkavail="$PSYOPSOS_OVERLAY"/etc/apk/available
apklist=
apklist="$apklist $(cat "$apkworld")"
apklist="$apklist $(cat "$apkavail")"


profile_psyopsOScd() {
	profile_standard
	# This is the first part of the filename of the iso
	# Default is alpine-$PROFILE
	image_name="psyopsOS"
	# You can also set the output filename like this:
	# output_filename="psyopsOS.iso"
	title="psyopsOS Boot Disc (ISO image)"
	desc="The PSYOPS operating system for powerful management of personal infrastructure"
	arch="x86_64"

	# Use profile_standard's initfs_cmdline, but remove the 'quiet' option.
	# This will show messages emitted by the initramfs's /init script.
	# (Note that that init script comes from /usr/share/mkinitfs/initramfs-init on the ISO builder system.)
	initfs_cmdline="$(echo "$initfs_cmdline" | sed 's/ quiet / /g')"

	kernel_flavors="lts"
	# kernel_addons=""
	boot_addons="intel-ucode"
	initrd_ucode="/boot/intel-ucode.img"

	# These are kernel command line options
	# debug=all prints dmesg to the screen during boot, and maybe other things
	# earlyprintk=dbgp enables early printk, which prints kernel messages to the screen during boot
	# console=tty0 and console=ttyS0,115200 enable the kernel to print messages to the screen during boot
	#  tty0 is the screen, ttyS0 is the serial port
	kernel_cmdline="$kernel_cmdline earlyprintk=dbgp console=tty0 console=ttyS0,115200"

	# 115200 baud is what is used with qemu and lima
	syslinux_serial="0 115200"

	# These are .apk files that will exist in the resulting iso image
	# This doesn't install them in the image, just adds the package file to /apks
	apks="$apks $apklist"
	local _k _a
	for _k in $kernel_flavors; do
		apks="$apks linux-$_k"
		for _a in $kernel_addons; do
			apks="$apks $_a-$_k"
		done
	done

	apks=$(echo "$apks" | tr '\t' ' ' | tr ' ' '\n' | sort | uniq | tr '\n' ' ')

	echo "================================ psyopsOS apks:"
	echo "$apks" | tr ' ' '\n\t'
	echo "================================ end psyopsOS apks"

	apkovl="genapkovl-psyopsOS.sh"

	# This hostname gets set at boot
	# We override it in a local.d script later
	hostname="psyopsOS-bootstrap"
}
