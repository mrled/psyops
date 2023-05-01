"""Accept syslog messages from the network and store them locally for analysis"""

from dataclasses import dataclass
from pathlib import Path

from progfiguration.cmd import run
from progfiguration.inventory.roles import ProgfigurationRole


@dataclass(kw_only=True)
class Role(ProgfigurationRole):

    # Where to store logs
    # Note that all logs will be owned by root
    logdir: Path

    # Remote system logs, standard syslog ports on TCP/UDP
    syslog_port: int = 514
    # Remote netconsole logs, Linux kernel messages over the network
    netcons_port: int = 5514
    # Remote temporal logs, stuff that might log often and be archived for only a short time
    nettemp_port: int = 5515

    @property
    def homedir(self) -> Path:
        return Path(f"/home/{self.username}")

    @property
    def sshkey_path(self) -> Path:
        return self.homedir / ".ssh" / "id_pullbackup"

    def apply(self):
        packages = [
            "logrotate",
            "logrotate-openrc",
            "syslog-ng",
            "syslog-ng-openrc",
        ]
        run(["apk", "add", *packages])
        self.localhost.makedirs(self.logdir, owner="root", group="root", mode=0o700)
        self.localhost.temple(
            self.role_file("syslog-ng.conf.temple"),
            "/etc/syslog-ng/syslog-ng.conf",
            {
                "syslog_port": self.syslog_port,
                "netcons_port": self.netcons_port,
                "nettemp_port": self.nettemp_port,
                "logdir": self.logdir,
            },
            owner="root",
            group="root",
            mode=0o644,
            dirmode=0o755,
        )

        run("rc-service syslog-ng start")
        run("rc-update add syslog-ng default")
        run("rc-service syslog-ng reload")  # Ensures config is loaded if we changed it

    def results(self):
        return {
            "syslog_port": self.syslog_port,
            "netcons_port": self.netcons_port,
            "nettemp_port": self.nettemp_port,
        }
