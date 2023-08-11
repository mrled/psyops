#!/bin/sh
set -eu
. /etc/backup.sh.d/backup.env
aws s3 cp --recursive $BACKUP_DIR s3://$BACKUP_S3_BUCKET_NAME/ --endpoint-url $BACKUP_S3_ENDPOINT_URL
