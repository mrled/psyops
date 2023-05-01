# Todo

## Ideas

* A role to control psyopsOS secrets from progfiguration
    * Secrets still have to be mounted by the psyopsOS postboot startup script
    * progfiguration can check whether each file matches what it has internally
    * If any of them do not match, remount the volume rw and copy that file, then remount again ro
* Further enhancement: allow easier creation of the secrets partition
    * Write psyopsOS-base script to create the partition
    * Copy just progfiguration itself to a brand new node
    * progfiguration then has to contain ssh host keys etc
    * Run script with path to progfiguration, age secret key, and node name as arguments, and it does everything
* Add a `pause_syslog_logging` context manager so that I can do things like restart syslog without errors
    * Currently progfiguration sends logs to syslog if it can write to `/dev/log`
    * If I restart syslog or replace busybox syslog with syslog-ng, this prints lots of errors
    * Add a context manager so I can do those actions with `with pause_syslog_logging: ...`
      and avoid generating the errors
    * Maybe with an argument like `with pause_syslog_logging(logfile="/var/log/syslog.paused"): ...`
      so that it can write log lines there for troubleshooting.
    * Alternative: don't log to syslog by default, just log to a file in /var/log directly and avoid this
* Research using Mozilla SOPS instead of my own custom thing
