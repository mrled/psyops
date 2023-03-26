#!/bin/bash
cat "/usr/share/zoneinfo/${PSYOPS_TIMEZONE}" > /etc/localtime
$HOME/.dhd/opt/bin/dhd-shdetect
exec ssh-agent /usr/bin/tmux -u
