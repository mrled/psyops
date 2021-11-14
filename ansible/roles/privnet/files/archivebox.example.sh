#!/bin/sh
set -eu

# This is just an example script.
# Follow the commented instructions and copy it anywhere you want to run the archivebox command.
# It will connect to the archivebox machine and run the archivebox wrapper script
# to allow you to add new items.

# - Generate this ahead of time
# - Make sure to save it somewhere that it will NOT get automatically added to your SSH agent
# - Add it to {{ privnet_archivebox_allow_ssh_keys }}
archivebox_ssh_id="$HOME/.ssh/archivebox/archivebox_id_ed25519"

archivebox_user=archivebox
archivebox_host=archivebox.home.micahrl.com

ssh -o AddKeysToAgent=no -i "$archivebox_ssh_id" "$archivebox_user@$archivebox_host" "$@"
