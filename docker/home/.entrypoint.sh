#!/bin/zsh

cat "/usr/share/zoneinfo/${PSYOPS_TIMEZONE}" > /etc/localtime

# $HOME/.local/bin is where pip installs --user packages, among other things
mkdir -p "$HOME/.local/bin"

# Sets the $PATH and a bunch of other stuff
$HOME/.dhd/opt/bin/dhd-shdetect

# Set up AppArmor. This does nothing unless we run a command with aa-exec.
sudo /sbin/apparmor_parser -r /etc/apparmor.d/claude
sudo /usr/sbin/aa-enforce /etc/apparmor.d/claude

mode=${1:-interactive}
echo "Mode: $mode"
case "$mode" in
  interactive)
    exec ssh-agent /usr/bin/tmux -u
    ;;
  claude)
    # AppArmor profile 'psyops-claude' must be loaded on the Docker host first.
    exec aa-exec -p claude -- claude
    ;;
  *)
    echo "Unknown mode: $mode" >&2
    exit 1
    ;;
esac
