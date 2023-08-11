#!/bin/sh
set -eu

# Save required  environment variables for the backup script to a file.

cat > /etc/backup.sh.d/backup.env <<EOF
BACKUP_DIR=$BACKUP_DIR
BACKUP_S3_BUCKET_NAME=$BACKUP_S3_BUCKET_NAME
BACKUP_S3_ENDPOINT_URL=$BACKUP_S3_ENDPOINT_URL
EOF

/usr/bin/supervisord -c /etc/supervisord.conf
