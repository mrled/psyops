#!/bin/sh

set -e
set -u

psyops=$(printf "$(ansi fg=magenta)P$(ansi fg=red)S$(ansi fg=yellow)Y$(ansi fg=green)O$(ansi fg=cyan)P$(ansi fg=blue)S$(ansi mode=reset)")

usage() {
    cat <<ENDUSAGE
Usage: $0 [-h|--help] [-f|--force]
Set up $psyops
    -h | --help: Print help and exit
    -f | --force: Remove any existing config files and reinit
    -t | --ssh-key-type: Type of SSH key to expect/generate
    -C | --ssh-key-comment: Comment field of SSH key

Configure the $psyops environment (gandi, digitalocean, etc)
ENDUSAGE
}

force=
keytype=ed25519
keycomm=conspirator@PSYOPS
while test $# -gt 0; do
    case "$1" in
        -h | --help ) usage; exit;;
        -f | --force ) force=1; shift;;
        -t | --ssh-key-type ) keytype=$2; shift 2;;
        -C | --ssh-key-comment ) keycomm=$2; shift 2;;
        *) echo "Unknown argument: '$1'"; usage; exit 1;;
    esac
done

gandicfg=$HOME/.config/gandi/config.yaml
doctlcfg=$HOME/.config/doctl/config.yaml
keypath=$HOME/.ssh/id_$keytype

if test -e "$gandicfg" && test "$force"; then rm "$gandicfg"; fi
if test -e "$doctlcfg" && test "$force"; then rm "$doctlcfg"; fi
# Don't let -f delete an existing SSH key

if test ! -e "$keypath"; then
    echo "Create SSH key for $psyops"
    ssh-keygen -f "$keypath" -t "$keytype" -C "$keycomm"
else
    echo "SSH key for $psyops already exists"
fi

if test ! -e "$gandicfg"; then
    echo "Configure Gandi for $psyops:"
    gandi setup
else
    echo "Gandi for $psyops is already configured"
fi

if test ! -e "$doctlcfg"    ; then
    echo "Configure Digital Ocean for $psyops:"
    doctl auth init
else
    echo "Digital Ocean for $psyops is already configured"
fi
