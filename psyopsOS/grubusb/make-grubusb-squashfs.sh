#!/bin/sh
set -eux

script=$(basename "$0")

# Default argument values
apk_keys_dir=/etc/apk/keys
apk_local_repo=
apk_packages=
apk_repos_file=/etc/apk/repositories
default_hostname=psyopsOS-unconfigured
outdir=
psyopsos_overlay_dir=

usage() {
    cat <<ENDUSAGE
$script: Make squashfs for psyopsOS grubusb
Usage: $script [-h]

This script must be run by root.

ARGUMENTS:
    -h                      Show this help message
    --apk-local-repo        Local repository path to use (optional)
                            Will be mounted into the initramroot during package
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
    --default-hostname      Default hostname to use when booting
                            Default: "$default_hostname"
    --outdir                Output directory (required)
    --psyopsos-overlay-dir  Directory containing psyopsOS overlay files
                            (required)

ENVIRONMENT VARIABLES:
    PACKAGER_PRIVKEY        Path to the packager private key
    PACKAGER_PUBKEY         Path to the packager public key

FILES:
    We look in abuild configuration for the packager signing key.
        /etc/abuild.conf
        ~/.abuild/abuild.conf

CONTAINER:
    This script must be run in a privileged container (docker run --privileged=true),
    because this is required to chroot.

ABOUT:
    Inspired by Alpine Linux genapkovl script(s).
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
    --outdir) outdir="$2"; shift 2;;
    --psyopsos-overlay-dir) psyopsos_overlay_dir="$2"; shift 2;;
    -*) echo "Unknown option: $1; see '$script -h'" >&2; exit 1;;
    *) echo "Unknown argument: $1; see '$script -h'" >&2; exit 1;;
    esac
done

#### Early checks

if [ -z "$outdir" || -z "$psyopsos_overlay_dir" ]; then
    echo "Missing required arguments" >&2
    usage >&2
    exit 1
fi

if [ "$(id -u)" != 0 ]; then
    echo "This script must be run by root" >&2
    exit 1
fi

test -f /etc/abuild.conf && . /etc/abuild.conf
test -f "$HOME"/.abuild/abuild.conf && . "$HOME"/.abuild/abuild.conf
pubkey="${PACKAGER_PUBKEY:-"${PACKAGER_PRIVKEY}.pub"}"
if ! test -f "$pubkey" || ! test -f "$PACKAGER_PRIVKEY"; then
    echo "Packager private key file ($PACKAGER_PRIVKEY) and/or public key file ($pubkey) do not exist" >&2
    exit 1
fi

#### Functions

makefile() {
	OWNER="$1"
	PERMS="$2"
	FILENAME="$3"
	cat > "$FILENAME"
	chown "$OWNER" "$FILENAME"
	chmod "$PERMS" "$FILENAME"
	echo "======== $FILENAME"
	cat "$FILENAME"
	echo "======== End $FILENAME"
}

rc_add() {
	install -o root -g root -m 0755 -d "$squashroot"/etc/runlevels/"$2"
	ln -sf /etc/init.d/"$1" "$squashroot"/etc/runlevels/"$2"/"$1"
}

psyops_overlay_install() {
	owner="$1"
	group="$2"
	mode="$3"
	relpath="$4"
	install -o "$owner" -g "$group" -m "$mode" "$psyopsos_overlay_dir"/"$relpath" "$squashroot"/"$relpath"
}

# Unmount any filesystems mounted inside the workdir
# We mount filesystems here for access in the squashfs chroot, so we have to clean them up
umount_workdir_submounts() {
    while read -r mount ; do
        mountpoint=$(echo "$mount" | cut -d' ' -f2)
        case "$mountpoint" in
            "$workdir"/*) umount "$mountpoint" ;;
        esac
    done </proc/mounts
}

cleanup() {
    # The unmounting is so verbose, don't xtrace it
    set +x
    umount_workdir_submounts
    # Remove the temporary workdir
    rm -rf "$workdir"
}

#### Main

# Make a temporary working directory
umask 022
workdir=/tmp/make-grubusb-squashfs.$$
if test -d "$workdir"; then
    echo "Temporary working directory $workdir already exists; aborting" >&2
    exit 1
fi
squashroot=$workdir/squashroot
mkdir -p "$workdir" "$squashroot" "$outdir"
trap cleanup EXIT

# Create the squashfs filesystem
# chroot into the squashroot and install the rest of the packages; this will run scripts
# We need to use an APK cache both inside and outside the chroot,
# otherwise we get temp errors from Alpine mirrors telling us to back off.

# Create APKINDEX etc in the squashroot
# We don't have to do --update-cache because we mount /var/cache/apk from the container into the squashroot below,
# and the container has already run apk update and has a populated cache.
apk add --initdb -p "$squashroot" --keys-dir "$apk_keys_dir" --repositories-file "$apk_repos_file"

mount -t proc none "$squashroot"/proc
mkdir -p "$squashroot"/etc/apk/keys
cp "$apk_keys_dir"/* "$squashroot"/etc/apk/keys/
cp "$apk_repos_file" "$squashroot"/etc/apk/repositories

# Mount the apk cache from the container into the squashroot for access in the chroot
# This is a Docker volume that contains a regular apk cache; see apk-cache(5)
mount -o bind /var/cache/apk "$squashroot"/var/cache/apk
ln -s /var/cache/apk "$squashroot"/etc/apk/cache
# Mount the local repo from the container into the squashroot for access in the chroot
# This is the directory containing locally-built APK packages, like psyopsOS-base and progfiguration_blacksite
if test -n "$apk_local_repo"; then
    mkdir -p "$squashroot"/$apk_local_repo
    mount -o bind "$apk_local_repo" "$squashroot"/$apk_local_repo
fi
# alpine-base contains busybox etc. Running scripts here creates busybox symlinks in /bin etc.
apk add -p $squashroot --keys-dir $apk_keys_dir --repositories-file "$apk_repos_file" ${apk_local_repo:+-X $apk_local_repo} alpine-base
# Now that busybox is installed, we can chroot
# Show us that we have a populated cache
chroot $squashroot /bin/busybox ls -alF /var/cache/apk/
# Install all the Alpine pacakges we want in the squashroot, and do run scripts
chroot $squashroot /sbin/apk add ${apk_local_repo:+-X $apk_local_repo} $apk_packages

# # squishsquash
# gourdpw='$6$MD90OtVoclidZroK$PL5K20z8wWVhNhqNpt.M4HQIBbSzmfopAI87ZqtgaL0Fx616Zy/WApy0WOvA1J8PgXyEjbRzkcKa9Ogr2lccT1'
# chroot $squashroot /bin/busybox adduser -D -h /home/gourd -s /bin/sh gourd
# chroot $squashroot /usr/sbin/usermod -p "$gourdpw" gourd
# mkdir -p "$squashroot"/etc/sudoers.d
# chmod 0750 "$squashroot"/etc/sudoers.d
# echo "gourd ALL=(ALL) NOPASSWD: ALL" > "$squashroot"/etc/sudoers.d/gourd

# psyopsOS specific stuff

# I think this should already be happening when installing psyopsOS-base,
# but it isn't for some reason?
chroot $squashroot /usr/sbin/psyopsOS-base-setup.sh


install -o root -g root -m 0755 -d "$squashroot"/etc "$squashroot"/etc/conf.d "$squashroot"/etc/runlevels
install -o root -g root -m 0755 -d "$squashroot"/etc/runlevels

makefile root:root 0644 "$squashroot"/etc/hostname <<EOF
$default_hostname
EOF

install -o root -g root -m 0755 -d "$squashroot"/var/psyopsOS

install -o root -g root -m 0755 -d "$squashroot"/etc/ssh
psyops_overlay_install root root 0644 etc/ssh/sshd_config
psyops_overlay_install root root 0644 etc/conf.d/sshd

psyops_overlay_install root root 0644 etc/issue
psyops_overlay_install root root 0644 etc/motd
psyops_overlay_install root root 0644 etc/inittab

install -o root -g root -m 0755 -d "$squashroot"/etc/psyopsOS "$squashroot"/etc/psyopsOS/status

# Could generate the date here: "$(date +%Y-%m-%dT%H:%M:%S%z)"
# However, we do it in tasks.py so we can also get the git stats
makefile root:root 0644 "$squashroot"/etc/psyopsOS/iso.json <<EOF
{
	"generated": {
		"iso8601": "$PSYOPSOS_BUILD_DATE_ISO8601",
		"revision": "$PSYOPSOS_BUILD_GIT_REVISION",
		"dirty": "$PSYOPSOS_BUILD_GIT_DIRTY"
	}
}
EOF

install -o root -g root -m 0755 -d "$squashroot"/usr/local/sbin
psyops_overlay_install root root 0700 usr/local/sbin/psyopsOS-mount-secret.sh

install -o root -g root -m 0755 -d "$squashroot"/etc/local.d
psyops_overlay_install root root 0755 etc/local.d/000-psyopsOS-postboot.start

# Configure /etc/fstab
# Make sure this matches what we do in initramfs-init
mkdir -p "$squashroot"/mnt/psyopsOS/efisys "$squashroot"/mnt/psyopsOS/a "$squashroot"/mnt/psyopsOS/b "$squashroot"/mnt/psyops-secret/mount
cat > "$squashroot"/etc/fstab <<EOF

LABEL=PSYOPSOSEFI    /mnt/psyopsOS/efisys       vfat ro,noauto 0 0
LABEL=psyops-secret  /mnt/psyops-secret/mount  ext4 ro,noauto 0 0
LABEL=psyopsOS-A     /mnt/psyopsOS/a            ext4 ro,noauto 0 0
LABEL=psyopsOS-B     /mnt/psyopsOS/b            ext4 ro,noauto 0 0
EOF

# Add a secret directory that is only readable by root.
# Mount inside of that, so that no matter what filesystem permissions in the psyops-secret mount are,
# no user except root will be able to read the files there.
install -o root -g root -m 0700 -d "$squashroot"/mnt/psyops-secret "$squashroot"/mnt/psyops-secret/mount

# Note that we do not call setup-alpine here.
# I saw that this project did this: <https://github.com/mayarid/penyu/blob/master/genapkovl-penyu.sh>
# But it's abandoned so I'm not even sure if that is correct
# Instead lets read the setup-alpine code, call the parts I care about in psyopsOS-postboot.start, and ignroe the rest.


rc_add devfs sysinit
rc_add dmesg sysinit
rc_add mdev sysinit
rc_add hwdrivers sysinit
rc_add modloop sysinit

rc_add hwclock boot
rc_add modules boot
rc_add sysctl boot
rc_add hostname boot
rc_add bootmisc boot
rc_add syslog boot

# Don't start ntpd here.
# Networking comes up properly in 000-psyopsOS-postboot.start in local.d;
# start ntpd there instead.
#rc_add ntpd default
rc_add local default
rc_add sshd default

rc_add mount-ro shutdown
rc_add killprocs shutdown
rc_add savecache shutdown

chmod 0755 "$squashroot"
chown root:root "$squashroot"

# Clean up
umount_workdir_submounts
echo "About to make squashfs"
find $squashroot

# Squash dat FS
# Write it to workdir first in case writing it to the outdir Docker volume is slow, then mv it over
test -f "$outdir"/squashfs && rm "$outdir"/squashfs
mksquashfs "$squashroot" "$workdir"/squashfs -noappend -comp xz
mv "$workdir"/squashfs "$outdir"/squashfs


echo "$script finished successfully"
