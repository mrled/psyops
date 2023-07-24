from dataclasses import dataclass

from progfiguration.cmd import run
from progfiguration.inventory.roles import ProgfigurationRole

from progfigsite.sitelib import line_in_crontab


@dataclass(kw_only=True)
class Role(ProgfigurationRole):

    # SMTP server info
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_pass: str

    # In fastmail this must be a "sending identity"
    from_addr: str

    # A list of local names to email addresses, like {'root': 'you@example.com'}.
    # A local name of 'default' matches anything not matched by another name.
    aliases: dict[str, str]

    def apply(self):

        run("apk add msmtp mailx")

        # By default, this is a symlink to busybox
        run("ln -sf /usr/bin/msmtp /usr/sbin/sendmail")

        # This file contains the SMTP password, keep it secure
        self.localhost.temple(
            self.role_file("msmtprc.temple"),
            "/etc/msmtprc",
            {
                "smtp_host": self.smtp_host,
                "smtp_port": self.smtp_port,
                "smtp_user": self.smtp_user,
                "smtp_pass": self.smtp_pass,
                "from_addr": self.from_addr,
            },
            owner="root",
            group="root",
            mode=0o0640,
        )

        aliases = "\n".join(f"{k}: {v}" for k, v in self.aliases.items()) + "\n"
        self.localhost.set_file_contents("/etc/aliases", aliases, mode=0o0644)

        # Set root's crontab's MAILTO value.
        # If this is not set at all, it will not send mail,
        # but we can just send it to the local account and let the aliases handle it.
        line_in_crontab("root", f"MAILTO=root", prepend=True)
