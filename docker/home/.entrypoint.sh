#!/bin/bash
cat "/usr/share/zoneinfo/${PSYOPS_TIMEZONE}" > /etc/localtime
exec /usr/bin/tmux
