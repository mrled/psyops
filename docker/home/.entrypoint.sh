#!/bin/bash

cat "/usr/share/zoneinfo/${PSYOPS_TIMEZONE}" > /etc/localtime
psecrets unlock
psyops-usage
exec /bin/bash -i
