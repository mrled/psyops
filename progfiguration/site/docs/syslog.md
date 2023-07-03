# Site syslog

* Busybox syslog on each host is responsible for local logs.
  This is an extremely simple logging daemon.
  It logs to `/var/log/messages` by default,
  and is configured in `psyopsos_postboot_config` to send logs over the psynet overlay network
  to the syslog server on port 514.
* syslog-ng on the syslog server is responsible for collecting logs from the network.
  It is configured in `syslog_collector` to accept logs over the network,
  including psynet and also its local network,
  and save them to disk.
  This doesn't disable busybox syslog,
  which works on this host exatly like all other hosts.
