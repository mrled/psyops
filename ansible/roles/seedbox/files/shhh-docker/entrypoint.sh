#!/bin/sh
set -eu
PUID=${PUID:-911}
PGID=${PGID:-911}
TZ=${TZ:-UTC}
W="$(echo Juvfcnee | tr 'A-Za-z' 'N-ZA-Mn-za-m')"
w="$(echo juvfcnee | tr 'A-Za-z' 'N-ZA-Mn-za-m')"
cp /usr/share/zoneinfo/$TZ /etc/localtime
groupadd -g $PGID "$w"
useradd -u $PUID -g "$w" -d /opt/Juvfcnee -s /bin/sh -M "$w"
chown -R "$w":"$w" /opt/Juvfcnee
ls -alF /opt/Juvfcnee
# echo exec su - "$w" -c "$*"
exec su - "$w" -c "/opt/Juvfcnee/$W -nobrowser -data /config"]
