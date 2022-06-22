#!/bin/sh
set -eu

usage() {
    cat <<ENDUSAGE
usage: $0 [-h]

The psyopsOS initialization script.

Handle configuration once the network is up etc, which is handled in the postboot script from local.d.

This script is called asynchronously from the async-init script in local.d.
ENDUSAGE
}

if test $# -gt 0; then
    usage
    exit
fi

. /etc/psyopsOS/psyops-secret.env
. /etc/psyopsOS/init.env

logger --stderr --priority user.debug --tag psyopsOS-postboot "Fetching node configuration from $PSYOPSOS_NODE_CONFIG"
node_json=/etc/psyopsOS/node.json
curl -o "$node_json" "$PSYOPSOS_NODE_CONFIG"
curl -o "$node_json.minisig" "$PSYOPSOS_NODE_CONFIG.minisig"
if minisign -V -p "$PSYOPSOS_MINISIGN_PUB" -m "$node_json"; then
    logger --stderr --priority user.debug --tag psyopsOS-postboot "node.json passed signature validation"
else
    logger --stderr --priority user.error --tag psyopsOS-postboot "node.json FAILED signature validation"
fi

progfig=progfiguration-0.0.0-py3-none-any.whl
progfig_path=/var/psyopsOS/"$progfig"
curl -o "$progfig_path" "$PSYOPSOS_SITE/psyopsOS/$progfig"
curl -o "$progfig_path.minisig" "$PSYOPSOS_SITE/psyopsOS/$progfig.minisig"
if minisign -V -p "$PSYOPSOS_MINISIGN_PUB" -m "$progfig_path"; then
    logger --stderr --priority user.debug --tag psyopsOS-postboot "progfiguration package passed signature validation"
else
    logger --stderr --priority user.error --tag psyopsOS-postboot "progfiguration package FAILED signature validation"
fi

logger --stderr --priority user.debug --tag psyopsOS-postboot "Installing psyopsOS venv..."
python3 -m venv --upgrade-deps /var/psyopsOS/venv
logger --stderr --priority user.debug --tag psyopsOS-postboot "Installing progfiguration..."
/var/psyopsOS/venv/bin/python -m pip install /var/psyopsOS/"$progfig"
ln -sf /var/psyopsOS/venv/bin/psyopsOS-progfiguration /usr/local/sbin/psyopsOS-progfiguration
logger --stderr --priority user.debug --tag psyopsOS-postboot "Running progfiguration..."
psyopsOS-progfiguration apply "$PSYOPSOS_NODENAME"
logger --stderr --priority user.debug --tag psyopsOS-postboot "Finished running progfiguration"

date +'%Y%m%d-%H%M%S %z' > /etc/psyopsOS/status/001-async-init.finished
