#!/bin/sh
# Ensure we run only one instance of offlineimap (from the pullbackup user) at a time
set -eu
username="{$}username"
if pgrep -u "$username" -f offlineimap >/dev/null; then
    echo "Tried to run offlineimap but it was already running"
    exit 1
fi
offlineimap
