#!/bin/sh
set -eu

# On first run, comment this line out so it will create the database.
# Then uncomment it and restart the container.
#/usr/local/bin/litestream restore -if-db-not-exists "$DB_FILEPATH"
#/usr/local/bin/litestream replicate -exec "/srv/remark42 server"

/srv/remark42 server
