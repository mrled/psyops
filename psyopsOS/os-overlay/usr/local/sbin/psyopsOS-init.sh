#!/bin/sh
set -eu

usage() {
    cat <<ENDUSAGE
The psyopsOS initialization script.

Handle configuration once the network is up etc, which is handled in the postboot script from local.d.

This script is called asynchronously from the async-init script in local.d.
ENDUSAGE
}

. /etc/psyopsOS/nodename.env
. /etc/psyopsOS/init.env

logger --stderr --priority user.debug --tag psyopsOS-postboot "Fetching node configuration from $PSYOPSOS_NODE_CONFIG"
curl -o /etc/psyopsOS/node.json "$PSYOPSOS_NODE_CONFIG"
curl -o /var/psyopsOS/progfiguration-0.0.0-py3-none-any.whl "$PSYOPS_SITE/progfiguration-0.0.0-py3-none-any.whl"

logger --stderr --priority user.debug --tag psyopsOS-postboot "Installing psyopsOS venv..."
python3 -m venv --upgrade-deps /var/psyopsOS/venv
logger --stderr --priority user.debug --tag psyopsOS-postboot "Installing progfiguration..."
/var/psyopsOS/venv/bin/python -m pip install /var/psyopsOS/progfiguration-0.0.0-py3-none-any.whl
logger --stderr --priority user.debug --tag psyopsOS-postboot "Running progfiguration..."
/var/psyopsOS/venv/bin/progfiguration $PSYOPS_NODENAME
logger --stderr --priority user.debug --tag psyopsOS-postboot "Finished running progfiguration"

date +'%Y%m%d-%H%M%S %z' > /etc/psyopsOS/status/001-async-init.finished
