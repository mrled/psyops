#!/bin/sh
set -eu

# Replace password tokens with actual passwords
sed "s/___admin_password_token___/$ISSO_ADMIN_PASSWORD/g" < /etc/isso.cfg.template |
    sed "s/___fastmail_password_token___/$ISSO_SMTP_PASSWORD/g" > /etc/isso.cfg

# On first run, comment this line out so it will create the database.
# Then uncomment it and restart the container.
/usr/local/bin/litestream restore -if-db-not-exists "$DB_FILEPATH"
/usr/local/bin/litestream replicate -exec "/isso/bin/gunicorn --bind 0.0.0.0:8080 --workers 4 --worker-tmp-dir /dev/shm isso.run"
