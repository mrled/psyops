#!/bin/sh
set -eu

# Generate passwords with mkpasswd from busybox
rootpasswd='$6$0b5NLl0l8QhyNYMF$0cAhVoTARzFUtVJxBjn4FFrXRIiTsHV55jvxPLq.LsAyEIUgmI/GFcCbrS8o1nWPW2Mml70yqhlIB8RBwJL3Z0'

usermod --password "$rootpasswd" root

ssh_key_psyops='ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIJ/zN5QLrTpjL1Qb8oaSniRQSwWpe5ovenQZOLyeHn7m conspirator@PSYOPS'
install -o root -g root -m 0700 -d /root/.ssh
if test -e /root/.ssh/authorized_keys && ! grep -q "$ssh_key_psyops" /root/.ssh/authorized_keys; then
    echo "$ssh_key_psyops" >> /root/.ssh/authorized_keys
fi

exit 0
