if test -z "$PSYOPSOS_OVERLAY"; then
	echo "Missing environment variable \$PSYOPSOS_OVERLAY"
	exit 1
fi

apkworld="$PSYOPSOS_OVERLAY"/etc/apk/world
apkavail="$PSYOPSOS_OVERLAY"/etc/apk/available
apklist=
apklist="$apklist $(cat "$apkworld")"
apklist="$apklist $(cat "$apkavail")"

profile_psyopsOS() {
	profile_standard
	title="psyopsOS"
	desc="The PSYOPS operating system for powerful management of personal infrastructure"
	arch="x86_64"
	kernel_flavors="lts"
	# kernel_addons=""
	boot_addons="intel-ucode"
	initrd_ucode="/boot/intel-ucode.img"

	# Enable serial console
	kernel_cmdline="$kernel_cmdline console=tty0 console=ttyAMA0"

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
	apks="$apks linux-firmware"

	echo "================================ psyopsOS apks:"
	for apk in $apks; do
		echo "	$apk"
	done
	echo "================================ end psyopsOS apks"

	apkovl="genapkovl-psyopsOS.sh"

	# This hostname gets set at boot
	# We override it in a local.d script later
	hostname="psyopsOS-bootstrap"
}
