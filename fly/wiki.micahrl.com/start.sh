#!/bin/sh
set -eu
/usr/local/bin/litestream restore -if-db-not-exists "$DB_FILEPATH"
/usr/local/bin/litestream replicate -exec "/usr/local/bin/docker-entrypoint.sh node server"
