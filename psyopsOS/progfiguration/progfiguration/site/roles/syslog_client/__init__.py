"""Send syslog messages to a remote server

Currently only supports busybox syslogd.
"""

from dataclasses import dataclass
import textwrap

from progfiguration.cmd import run
from progfiguration.inventory.roles import ProgfigurationRole


@dataclass(kw_only=True)
class Role(ProgfigurationRole):

    syslog_server: str
    syslog_port: int
    client_syslogd: str

    def configure_busybox_syslogd(self):
        self.localhost.set_file_contents(
            "/etc/conf.d/syslog",
            textwrap.dedent(
                f"""\
                SYSLOGD_OPTS="-t -L -R {self.syslog_server}:{self.syslog_port}"
                """
            ),
            owner="root",
            group="root",
            mode=0o644,
        )

        # TODO: this generates a lot of junk when progfiguration tries to log to syslog it's been stopped
        run("rc-service syslog restart")

    def apply(self):
        if self.client_syslogd == "busybox":
            self.configure_busybox_syslogd()
        else:
            raise NotImplementedError(f"Unknown syslog client type {self.client_syslogd}")

    def results(self):
        return {}
