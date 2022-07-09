#!/bin/sh
set -eu

dying_breath() {
    logger --stderr --priority user.error --tag psyopsOS-init.sh "Script exiting with error"
}

trap dying_breath ERR

usage() {
    cat <<ENDUSAGE
usage: $0 [-h]

The psyopsOS initialization script.

Handle configuration once the network is up etc, which is handled in the postboot script from local.d.

This script is called asynchronously from the async-init script in local.d.
ENDUSAGE
}

syslog() {
    priority="$1"
    message="$2"
    logger --stderr --priority "$priority" --tag psyopsOS-init.sh "$message"
}

psyopsos_dl_vf() {
    filename="$1"
    localpath="/var/psyopsOS/$filename"
    curl -o "$localpath" "$PSYOPSOS_SITE/psyopsOS/$filename"
    curl -o "$localpath.minisig" "$PSYOPSOS_SITE/psyopsOS/$filename.minisig"
    if minisign -V -p "$PSYOPSOS_MINISIGN_PUB" -m "$localpath"; then
        syslog user.debug "psyopsOS file '$localpath' passed signature validation"
    else
        syslog user.error "psyopsOS file '$localpath' FAILED signature validation"
        mkdir -p /var/psyopsOS/FAILED_SIG_VALIDATION
        exit 1
    fi
}

if test $# -gt 0; then
    usage
    exit
fi

. /etc/psyopsOS/psyops-secret.env
. /etc/psyopsOS/init.env

psyopsos_dl_vf progfiguration.version.json
verfile_path=/var/psyopsOS/progfiguration.version.json

progfig_version="$(jq -r .version $verfile_path)"
progfig="$(jq -r .wheel $verfile_path)"
progfig_path="/var/psyopsOS/$progfig"
progfig_url="$PSYOPSOS_SITE/psyopsOS/$progfig"
syslog user.debug "progfiguration version file indicates version $progfig_version, will download $progfig_url to $progfig_path"

psyopsos_dl_vf "$progfig"

syslog user.debug "Installing psyopsOS venv..."
python3 -m venv --upgrade-deps /var/psyopsOS/venv
syslog user.debug "Installing progfiguration..."
/var/psyopsOS/venv/bin/python -m pip install --force-reinstall "/var/psyopsOS/$progfig"
ln -sf /var/psyopsOS/venv/bin/psyopsOS-progfiguration /usr/local/sbin/psyopsOS-progfiguration
syslog user.debug "Running progfiguration..."
psyopsOS-progfiguration apply "$PSYOPSOS_NODENAME"
syslog user.debug "Finished running progfiguration"

date +'%Y%m%d-%H%M%S %z' > /etc/psyopsOS/status/001-async-init.finished
