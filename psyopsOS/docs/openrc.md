# OpenRC notes

OpenRC is an init system that is designed to be less convenient and flexible than systemd.

It's the default init system on Alpine.

Here are some notes for how to use it.

## Supervisors

You choose your own "supervisor". Different supervisors support different things.
OpenRC provides `supervise-daemon`, but you could also choose a third party one.
If you do not set a `supervisor=...` line,
it will run without a supervisor.
Supervisors automatically restart crashed daemons and also provide other features.

[`supervise-daemon` guide](https://github.com/OpenRC/openrc/blob/master/supervise-daemon-guide.md).

## Logging to syslog

There is no logging to syslog by default.
One way to do that is by setting `output_logger`/`error_logger`,
and using a supervisor that supports them.
`supervise-daemon` is one such supervisor.
**If you set `output_logger`/`error_logger` without setting `supervisor` to a supervisor that supports these options, your service will crash when it tries to write to its stdout/stderr!**

You can do this in `/etc/init.d/SERVICE`,
but it's maybe more correct to do it in `/etc/conf.d/SERVICE`.
(The difference is more important if you're building a proper operating system package.)
The following would work in either location:

```sh
# Send stdout and stderr to syslog
# This service prints normal messages (not just errors) to stderr
output_logger="logger -p daemon.info -t ${RC_SVCNAME}.stdout >/dev/null 2>&1"
error_logger="logger -p daemon.error -t ${RC_SVCNAME}.stderr >/dev/null 2>&1"

# Required when setting output_logger/error_logger,
# or else the service will crash when it tries to print to its out/err.
supervisor=supervise-daemon
```

Note that this will run a separate `logger` program for each of stderr/stdout.
If the distinction is not important, you may want to combine them; see below.

## Redirecting stdout/stderr of daemons

You can do this without a custom `start()` function with the somewhat odd pattern of setting it in `command`,
even if you also provide `command_args`.
Like so:

```sh
#!/sbin/openrc-run
command="/usr/bin/webhook 2>&1"
command_args="-hotreload -port $CAPTHOOK_PORT -verbose -header 'X-Avast=Matey' -header 'X-Yarr=ItsDrivingMeNuts' -hooks '$CATPHOOK_HOOKS_JSON'"
```
