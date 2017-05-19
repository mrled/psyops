#!/bin/sh

set -e
set -u

usage() {
    cat << ENDUSAGE
Usage: $0 [-h|--help] [-f|--force]
Set up $(ppsyops)
    -h | --help: Print help and exit
    -f | --force: Remove any existing config files and reinit

Configure the $(ppsyops) environment (gandi, digitalocean, etc)
ENDUSAGE
}

force=
if test $# -eq 1; then
    case "$1" in
        -h | --help ) usage; exit;;
        -f | --force ) force=1;;
        *) usage; exit 1;;
    esac
elif test $# -gt 0; then
    usage
    exit 1
fi

gandicfg=$HOME/.config/gandi/config.yaml
doctlcfg=$HOME/.config/doctl/config.yaml
idrsa=$HOME/.ssh/id_rsa

if test -e "$gandicfg" && test "$force"; then rm "$gandicfg"; fi
if test -e "$doctlcfg" && test "$force"; then rm "$doctlcfg"; fi
# Don't let -f delete an existing SSH key

if test ! -e "$idrsa"; then
    echo "Create SSH key for $(ppsyops)"
    ssh-keygen -f "$idrsa" -t ed25519
else
    echo "SSH key for $(ppsyops) already exists"
fi

if test ! -e "$gandicfg"; then
    echo "Configure Gandi for $(ppsyops):"
    gandi setup
else
    echo "Gandi for $(ppsyops) is already configured"
fi

if test ! -e "$doctlcfg"    ; then
    echo "Configure Digital Ocean for $(ppsyops):"
    doctl auth init
else
    echo "Digital Ocean for $(ppsyops) is already configured"
fi
