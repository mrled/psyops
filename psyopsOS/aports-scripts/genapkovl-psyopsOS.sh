#!/bin/sh -e

if test -z "$PSYOPSOS_OVERLAY"; then
	echo "Missing environment variable \$PSYOPSOS_OVERLAY"
	exit 1
fi

# mkimage.sh will call this with a HOSTNAME of "alpine",
# and that's what the hostname will be when the image first boots.
# We later set it in a local.d script.
HOSTNAME="$1"
if [ -z "$HOSTNAME" ]; then
	echo "usage: $0 hostname"
	exit 1
fi

cleanup() {
	echo sudo rm -rf "$tmp"
}

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
	install -o root -g root -m 0755 -d "$tmp"/etc/runlevels/"$2"
	ln -sf /etc/init.d/"$1" "$tmp"/etc/runlevels/"$2"/"$1"
}

psyops_overlay_install() {
	owner="$1"
	group="$2"
	mode="$3"
	relpath="$4"
	install -o "$owner" -g "$group" -m "$mode" "$PSYOPSOS_OVERLAY"/"$relpath" "$tmp"/"$relpath"
}

umask 022
tmp="$(mktemp -d)"
trap cleanup EXIT

install -o root -g root -m 0755 -d "$tmp"/etc "$tmp"/etc/conf.d "$tmp"/etc/runlevels
install -o root -g root -m 0755 -d "$tmp"/etc/runlevels

makefile root:root 0644 "$tmp"/etc/hostname <<EOF
$HOSTNAME
EOF

install -o root -g root -m 0755 -d "$tmp"/var/psyopsOS

install -o root -g root -m 0755 -d "$tmp"/etc/apk
psyops_overlay_install root root 0644 etc/apk/world
install -o root -g root -m 0755 -d "$tmp"/etc/apk/keys
psyops_overlay_install root root 0644 etc/apk/keys/psyops@micahrl.com-62ca1973.rsa.pub

install -o root -g root -m 0755 -d "$tmp"/etc/ssh
psyops_overlay_install root root 0644 etc/ssh/sshd_config
psyops_overlay_install root root 0644 etc/conf.d/sshd

psyops_overlay_install root root 0644 etc/issue
psyops_overlay_install root root 0644 etc/motd

install -o root -g root -m 0755 -d "$tmp"/etc/psyopsOS "$tmp"/etc/psyopsOS/status

# Could generate the date here: "$(date +%Y-%m-%dT%H:%M:%S%z)"
# However, we do it in tasks.py so we can also get the git stats
makefile root:root 0644 "$tmp"/etc/psyopsOS/iso.json <<EOF
{
	"generated": {
		"iso8601": "$PSYOPSOS_BUILD_DATE_ISO8601",
		"revision": "$PSYOPSOS_BUILD_GIT_REVISION",
		"dirty": "$PSYOPSOS_BUILD_GIT_DIRTY"
	}
}
EOF

psyops_overlay_install root root 0600 etc/psyopsOS/postboot.secrets

install -o root -g root -m 0755 -d "$tmp"/usr/local/sbin
psyops_overlay_install root root 0700 usr/local/sbin/psyopsOS-mount-secret.sh

install -o root -g root -m 0755 -d "$tmp"/etc/local.d
psyops_overlay_install root root 0755 etc/local.d/000-psyopsOS-postboot.start


# Add a secret directory that is only readable by root.
# Mount inside of that, so that no matter what filesystem permissions in the psyops-secret mount are,
# no user except root will be able to read the files there.
install -o root -g root -m 0700 -d "$tmp"/mnt/psyops-secret "$tmp"/mnt/psyops-secret/mount

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

chmod 0755 "$tmp"
chown root:root "$tmp"

echo "About to create apkovl"
echo "PWD: $(pwd)"
echo "Tmp dir: $tmp"
ls -alF "$tmp"

tar -c -C "$tmp" . | gzip -9n > $HOSTNAME.apkovl.tar.gz
