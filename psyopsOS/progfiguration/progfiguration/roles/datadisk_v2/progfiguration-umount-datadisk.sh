#!/bin/sh

debug="${PSYOPSOS_DEBUG:-""}"

set -eu

if test "$debug"; then
    set -x
fi

. /etc/psyopsOS/roles/datadisk/env.sh

mountpoint_killall_umount() {
    mountpoint="$1"
    pids="$(lsof -t +D "$mountpoint" || true)"
    if test "$pids"; then
        echo "Killing all processes with open files on ${mountpoint}..."
        kill -9 $pids
    else
        echo "No processes found with open files on ${mountpoint}"
    fi
    echo "Unmounting ${mountpoint}..."
    umount "$mountpoint"
}

for mountline in "$(mount | grep "^${PSYOPSOS_DATADISK_DEVICE}")"; do
    mountpoint=$(echo ${mountline} | awk '{print $3}')
    if test "$mountpoint" = "$PSYOPSOS_DATADISK_MOUNTPOINT"; then
        continue
    fi
    echo "Device ${PSYOPSOS_DATADISK_DEVICE} is mounted at ${mountpoint}"
    mountpoint_killall_umount "$mountpoint"
done

mountpoint_killall_umount "$PSYOPSOS_DATADISK_MOUNTPOINT"
