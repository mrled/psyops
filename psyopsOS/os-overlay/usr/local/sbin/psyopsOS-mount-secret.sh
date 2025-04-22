#!/bin/sh
set -eu

loggertag="psyopsOS-mount-secret"

if ! grep -q "LABEL=psyops-secret" /etc/fstab; then
	printf '\nLABEL=psyops-secret /mnt/psyops-secret/mount ext4 ro,noauto 0 0\n' >> /etc/fstab
fi
if ! mountpoint -q /mnt/psyops-secret/mount; then
	logger --stderr --priority user.debug --tag "$loggertag" "Mounting psyopsOS secret volume..."
	mount /mnt/psyops-secret/mount
else
	logger --stderr --priority user.debug --tag "$loggertag" "psyopsOS secret volume already mounted"
fi

# This is intended to make it easier during development
if test -e /mnt/psyops-secret/mount/TESTONLYNOPROD.env; then
	. /mnt/psyops-secret/mount/TESTONLYNOPROD.env
	if test "$PSYOPSOS_TESTING_ONLY_NO_PROD_ADD_TOOR_BLANK_PW" = yes; then
		if ! grep -q toor /etc/passwd; then
			useradd --home-dir /root --no-create-home --no-user-group --non-unique --uid 0 --gid 0 toor
			passwd -d toor
			logger --stderr --priority user.warn --tag "$loggertag" "WARNING: Added toor user with blank password"
		fi
	fi
fi

# Make sure the nodename is set to something.
# If we don't do this, the postboot script will hang waiting for a hostname.
export PSYOPSOS_NODENAME="psyopsOS-unconfigured"
if test -e /mnt/psyops-secret/mount/nodename; then
	nodename_contents="$(head -n1 /mnt/psyops-secret/mount/nodename | tr -d '\r\n' | tr -d ' ')"
	if test "$nodename_contents"; then
		export PSYOPSOS_NODENAME="$nodename_contents"
	fi
fi

export PSYOPSOS_AGEKEY=/mnt/psyops-secret/mount/age.key
export PSYOPSOS_MINISIGN_PUB=/mnt/psyops-secret/mount/minisign.pubkey
export PSYOPSOS_MACTAB=/mnt/psyops-secret/mount/mactab
export PSYOPSOS_INTERFACES=/mnt/psyops-secret/mount/network.interfaces
export PSYOPSOS_SSHD_ED25519_KEY=/mnt/psyops-secret/mount/ssh_host_ed25519_key
export PSYOPSOS_PSYNET_HOST_CRT=/mnt/psyops-secret/mount/psynet.host.crt
export PSYOPSOS_PSYNET_HOST_KEY=/mnt/psyops-secret/mount/psynet.host.key

logger --stderr --priority user.debug --tag "$loggertag" "Values from the psyops-secret volume: $(env | grep '^PSYOPSOS_')"

# TODO: maybe need to rename this psyops-secret.env file
env | grep '^PSYOPSOS_' > /etc/psyopsOS/psyops-secret.env
chmod 644 /etc/psyopsOS/psyops-secret.env

logger --stderr --priority user.debug --tag "$loggertag" "Completing successfully..."
