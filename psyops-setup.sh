#!/bin/sh

set -e
set -u

psyops=$(printf "$(ansi fg=magenta)P$(ansi fg=red)S$(ansi fg=yellow)Y$(ansi fg=green)O$(ansi fg=cyan)P$(ansi fg=blue)S$(ansi mode=reset)")

usage() {
    cat <<ENDUSAGE
Usage: $0 [-h|--help] [-f|--force]
Configure the $psyops environment (gandi, digitalocean, ssh, etc)
    -h | --help: Print help and exit
    -f | --force: Remove any existing config files and reinit
    -t | --ssh-key-type: Type of SSH key to expect
        Default value: ed25519
    -C | --ssh-key-comment: Comment field of SSH key
        (Does NOT have to match comment supplied when key was generated)
        Default value: conspirator@PSYOPS

We expect an SSH key generated out of band. We recommend doing so like this:
    ssh-keygen -t ed25519 -C conspirator@PSYOPS
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
privkey="${HOME}/.ssh/id_${keytype}"
pubkey="${HOME}/.ssh/id_${keytype}.pub"

if test "$force"; then
    rm "$gandicfg" "$doctlcfg" "$privkey" "$pubkey" || true
fi

if test ! -e "$privkey"; then
    echo "Configure SSH key for $psyops"
    echo "Paste the private $keytype key here"
    echo "Then hit ctrl+d on an empty line to read the key"
    cat > "$privkey"
    pubkeydata=$(ssh-keygen -y -f "$privkey")
    pubkeydata="${pubkeydata} ${keycomm}"
    echo "Private key accepted; public key: $pubkeydata"
    echo "$pubkeydata" > "$pubkey"
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
