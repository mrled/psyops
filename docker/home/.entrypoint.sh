#!/bin/bash

cat "/usr/share/zoneinfo/${PSYOPS_TIMEZONE}" > /etc/localtime

# $HOME/.local/bin is where pip installs --user packages, among other things
mkdir -p "$HOME/.local/bin"

# Sets the $PATH and a bunch of other stuff
$HOME/.dhd/opt/bin/dhd-shdetect

exec ssh-agent /usr/bin/tmux -u
