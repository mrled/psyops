# We use this file to override parts of the mkimage process


# The only difference between the upstream create_image_iso and ours is that we customize the volid in the vall to xorrisofs
# Compare that function and ours if something is not working after an update.
# You can verify that this worked on macOS with `hdiutil imageinfo /path/to/asdf.iso | grep partition-name`
create_image_iso() {
	echo "LAUNCHING PSYOPSOS OVERRIDE create_image_iso() FUNCTION"

	# This must be 32 characters or less or else xorriso will fail
	local _volid="psyopsos-boot $RELEASE $ARCH"

	local ISO="${OUTDIR}/${output_filename}"
	local _isolinux
	local _efiboot

	if [ -e "${DESTDIR}/boot/syslinux/isolinux.bin" ]; then
		# isolinux enabled
		_isolinux="
			-isohybrid-mbr ${DESTDIR}/boot/syslinux/isohdpfx.bin
			-eltorito-boot boot/syslinux/isolinux.bin
			-eltorito-catalog boot/syslinux/boot.cat
			-no-emul-boot
			-boot-load-size 4
			-boot-info-table
			"
	fi
	if [ -e "${DESTDIR}/efi" -a -e "${DESTDIR}/boot/grub" ]; then
		# Create the EFI boot partition image
		mformat -i ${DESTDIR}/boot/grub/efi.img -C -f 1440 -N 0 ::
		mcopy -i ${DESTDIR}/boot/grub/efi.img -s ${DESTDIR}/efi ::
		touch -md "@${SOURCE_DATE_EPOCH}" ${DESTDIR}/boot/grub/efi.img

		# Enable EFI boot
		if [ -z "$_isolinux" ]; then
			# efi boot only
			_efiboot="
				-efi-boot-part
				--efi-boot-image
				-e boot/grub/efi.img
				-no-emul-boot
				"
		else
			# hybrid isolinux+efi boot
			_efiboot="
				-eltorito-alt-boot
				-e boot/grub/efi.img
				-no-emul-boot
				-isohybrid-gpt-basdat
				"
		fi
	fi

	if [ "$ARCH" = ppc64le ]; then
		grub-mkrescue --output ${ISO} ${DESTDIR} -follow-links \
			-sysid LINUX \
			-volid "$_volid"
	else
		if [ "$ARCH" = s390x ]; then
			printf %s "$initfs_cmdline $kernel_cmdline " > ${WORKDIR}/parmfile
			for _f in $kernel_flavors; do
				mk-s390-cdboot -p ${WORKDIR}/parmfile \
					-i ${DESTDIR}/boot/vmlinuz-$_f \
					-r ${DESTDIR}/boot/initramfs-$_f \
					-o ${DESTDIR}/boot/merged.img
			done
			iso_opts="$iso_opts -no-emul-boot -eltorito-boot boot/merged.img"
		fi
		xorrisofs \
			-quiet \
			-output ${ISO} \
			-full-iso9660-filenames \
			-joliet \
			-rational-rock \
			-sysid LINUX \
			-volid "$_volid" \
			$_isolinux \
			$_efiboot \
			-follow-links \
			${iso_opts} \
			${DESTDIR}
	fi

	echo "FINISHED RUNNING PSYOPSOS OVERRIDE create_image_iso() FUNCTION"
}


# This must set the same volume ID that we set in create_image_iso
grub_gen_earlyconf() {
	# This must be 32 characters or less or else xorriso will fail
	local _volid="psyopsos-boot $RELEASE $ARCH"
	cat <<- EOF
	search --no-floppy --set=root --label "$_volid"
	set prefix=(\$root)/boot/grub
	EOF
}
