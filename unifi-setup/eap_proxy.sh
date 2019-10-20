#!/bin/sh
# EdgeOS startup script for eap_proxy.py. See README.md.

# Adjust IF_WAN and IF_ROUTER for your setup.
IF_WAN=eth0     # Interface connected to the AT&T ONT
IF_ROUTER=eth2  # Interface connected to the AT&T Router Gateway (RG)

# CONFIG_OPTIONS don't normally need to be adjusted. See README.MD.
CONFIG_OPTIONS=(
  --restart-dhcp
  --ignore-when-wan-up
  --ignore-logoff
  --ping-gateway
  --set-mac
)

# DAEMON_OPTIONS don't normally need to be adjusted. See README.MD.
DAEMON_OPTIONS=(
  --daemon
  --pidfile /var/run/eap_proxy.pid
  --syslog
)

if test -f /var/run/eap_proxy.pid; then
  kill $(head -1 /var/run/eap_proxy.pid) 2>/dev/null
fi

/usr/bin/python /config/scripts/eap_proxy.py \
    "$IF_WAN" "$IF_ROUTER" "${CONFIG_OPTIONS[@]}" "${DAEMON_OPTIONS[@]}" &
