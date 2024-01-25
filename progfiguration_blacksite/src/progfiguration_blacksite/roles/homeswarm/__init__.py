"""Privnet Docker Swarm"""


from dataclasses import dataclass
from pathlib import Path
import textwrap

from progfiguration import logger
from progfiguration.cmd import magicrun
from progfiguration.inventory.roles import ProgfigurationRole
from progfiguration.localhost.disks import is_mountpoint

from progfiguration_blacksite.roles.psyopsos_docker import wait_for_docker
from progfiguration_blacksite.sitelib import get_persistent_secret, line_in_crontab
from progfiguration_blacksite.sitelib.users import add_managed_service_account


@dataclass(kw_only=True)
class Role(ProgfigurationRole):
    roledir: Path

    stackname: str = "homeswarm"

    balancer_domain: str
    acme_email: str
    acme_aws_region: str
    acme_aws_zone: str
    acme_aws_access_key_id: str
    acme_aws_secret_access_key: str
    zerossl_kid: str
    zerossl_hmac: str

    whoami_domain: str

    archivebox_user: str = "archivebox"
    archivebox_group: str = "archivebox"
    archivebox_domain: str

    pihole_webpassword: str
    pihole_domain: str

    homeswarm_blockdevice: str = ""

    # Blacklist notes:
    # - Default value: URL_BLACKLIST = "(://(.*\.)?facebook\.com)|(://(.*\.)?ebay\.com)|(.*\.exe$)"
    # - Yelp wastes our time for 1+ minute before failing
    # - Facebook is mostly useless behind a login wall
    # - Don't just download Youtube homepage lol. (And handle /?feature=asldkfj type bullshit too)
    # - ... actually come to think of it, fuck downloading every Youtube video I ever watch, that's a bad idea
    url_blacklist = r"^(javascript:)|(https?://[A-Za-z0-9\.-]*((facebook\.com)|(yelp\.com)|(youtube\.com)|(youtu\.be)))"

    def apply(self):
        # Create required users
        archivebox_getent = add_managed_service_account(
            self.archivebox_user, self.archivebox_group, groups=["docker"], shell="/bin/sh"
        )

        # Create the role directory
        self.localhost.makedirs(self.roledir, owner="root", group="root", mode=0o0755)

        # If the homeswarm_blockdevice is specified, mount it to the role directory
        if self.homeswarm_blockdevice and not is_mountpoint(str(self.roledir)):
            magicrun(["mount", self.homeswarm_blockdevice, self.roledir])

        # Create required directories
        traefik_confdir = self.roledir / "traefik"
        self.localhost.makedirs(traefik_confdir, owner="root", group="root", mode=0o0755)
        archivebox_sonic_confdir = self.roledir / "archivebox_sonic"
        self.localhost.makedirs(archivebox_sonic_confdir, owner="root", group="root", mode=0o0755)

        # Root for all stuff that the archivebox user should own, like database, git checkout, etc
        archivebox_rootdir = self.roledir / "archivebox"
        self.localhost.makedirs(
            archivebox_rootdir, owner=self.archivebox_user, group=self.archivebox_group, mode=0o0700
        )

        # The data directory for the ArchiveBox program
        archivebox_datadir = archivebox_rootdir / "data"
        archivebox_incoming_dir = archivebox_datadir / "incoming"
        self.localhost.makedirs(
            archivebox_incoming_dir, owner=self.archivebox_user, group=self.archivebox_group, mode=0o0700
        )

        # Generate Sonic backend password
        archivebox_sonic_backend_password = get_persistent_secret(archivebox_sonic_confdir / "password.txt")

        # Traefik configuration file
        traefik_yml_file = traefik_confdir / "traefik.yml"
        self.localhost.temple(
            self.role_file("traefik.yml.temple"),
            traefik_yml_file,
            {
                "acme_email": self.acme_email,
                "acme_domain": self.balancer_domain,
                "zerossl_kid": self.zerossl_kid,
                "zerossl_hmac": self.zerossl_hmac,
            },
            owner="root",
            group="root",
            mode=0o0640,
        )

        # Traefik ACME state files
        traefik_acme_storage = traefik_confdir / "acme"
        self.localhost.makedirs(traefik_acme_storage, owner="root", group="root", mode=0o0700)
        self.localhost.touch(
            traefik_acme_storage / "letsencrypt-production.json", owner="root", group="root", mode=0o0600
        )
        self.localhost.touch(traefik_acme_storage / "letsencrypt-staging.json", owner="root", group="root", mode=0o0600)
        self.localhost.touch(traefik_acme_storage / "zerossl-production.json", owner="root", group="root", mode=0o0600)

        # Traefik ACME credentials file
        traefik_aws_creds_file = traefik_confdir / "aws-credentials"
        self.localhost.set_file_contents(
            traefik_aws_creds_file,
            textwrap.dedent(
                f"""\
                [default]
                aws_access_key_id = {self.acme_aws_access_key_id}
                aws_secret_access_key = {self.acme_aws_secret_access_key}
                """,
            ),
            owner="root",
            group="root",
            mode=0o0600,
        )

        # Build Archivebox Docker image from the dev branch
        # ... actually I don't think we have to do this,
        # the archivebox/archivebox:dev image looks like it's up to date with the latest in dev branch.
        # archivebox_branch = "dev"
        # archivebox_tag = "local-archivebox-dev"
        # magicrun(f"docker build -t {archivebox_tag} https://github.com/ArchiveBox/ArchiveBox.git#{archivebox_branch}")

        # Customize the Archivebox image for local use
        # It's best to build a Docker image in an empty directory, according to its docs
        annals_archivebox_builddir = archivebox_rootdir / "annals.archivebox.build"
        self.localhost.makedirs(annals_archivebox_builddir, owner="root", group="root", mode=0o0755)
        annals_archivebox_dockerfile = annals_archivebox_builddir / "annals.archivebox.Dockerfile"
        self.localhost.temple(
            self.role_file("annals.archivebox.Dockerfile.temple"),
            annals_archivebox_dockerfile,
            {
                "archivebox_tag": "archivebox/archivebox:dev",
            },
            owner="root",
            group="root",
            mode=0o0644,
        )
        annals_archivebox_tag = "annals-archivebox-local"

        # sometimes Docker isn't running yet when we get here, so we have to wait for it
        wait_for_docker(attempts=4, wait=15)

        magicrun(
            [
                "docker",
                "build",
                "--tag",
                annals_archivebox_tag,
                "--file",
                str(annals_archivebox_dockerfile),
                str(annals_archivebox_builddir),
            ]
        )

        # Chrome seccomp profile
        # Described here: <https://hub.docker.com/r/zenika/alpine-chrome>
        # Original via:
        # <https://github.com/jessfraz/dotfiles/blob/master/etc/docker/seccomp/chrome.json>
        # This doesn't work with Docker Swarm though sadly:
        # <https://github.com/moby/moby/issues/41371>
        # Instead we have to give SYS_ADMIN capability to the container, which is less secure.
        # self.localhost.cp(
        #     self.role_file("chrome.seccomp.json"),
        #     archivebox_rootdir / "chrome.seccomp.json",
        #     owner="root",
        #     group="root",
        #     mode=0o0644,
        # )

        # Archivebox Sonic backend config file
        archivebox_sonic_conf_file = archivebox_sonic_confdir / "sonic.cfg"
        self.localhost.temple(
            self.role_file("archivebox.sonic.cfg.temple"),
            archivebox_sonic_conf_file,
            {
                "auth_password": archivebox_sonic_backend_password,
            },
            owner="root",
            group="root",
            mode=0o0640,
        )

        # Pihole configuration
        pihole_datadir = self.roledir / "pihole"
        self.localhost.makedirs(pihole_datadir / "pihole", owner="root", group="root", mode=0o0755)
        self.localhost.makedirs(pihole_datadir / "dnsmasq", owner="root", group="root", mode=0o0755)

        # Archivebox clone
        archivebox_srcdir = archivebox_rootdir / "absrc"
        # magicrun(
        #     [
        #         "sudo",
        #         "-u",
        #         self.archivebox_user,
        #         "git",
        #         "config",
        #         "--global",
        #         "--add",
        #         "safe.directory",
        #         str(archivebox_srcdir),
        #     ]
        # )
        if archivebox_srcdir.exists():
            magicrun(["sudo", "-u", self.archivebox_user, "git", "pull"], cwd=str(archivebox_srcdir))
        else:
            magicrun(
                [
                    "sudo",
                    "-u",
                    self.archivebox_user,
                    "git",
                    "clone",
                    "https://github.com/mrled/ArchiveBox",
                    archivebox_srcdir.name,
                ],
                cwd=str(archivebox_srcdir.parent),
            )

        # Archivebox config file
        # ArchiveBox will generate the Django SECRET_KEY on the first run,
        # but we want to persist it across config rewrites.
        django_secret_key = get_persistent_secret(archivebox_rootdir / "persistent_secret_django_key.txt")
        self.localhost.temple(
            self.role_file("ArchiveBox.conf.temple"),
            archivebox_datadir / "ArchiveBox.conf",
            {
                "django_secret_key": django_secret_key,
                "archivebox_sonic_backend_password": archivebox_sonic_backend_password,
                "url_blacklist": self.url_blacklist,
            },
            owner=self.archivebox_user,
            group=self.archivebox_group,
            mode=0o0600,
        )

        # Archivebox cron job
        archivebox_schedule_script = archivebox_rootdir / "archivebox_daily_grooming.sh"
        self.localhost.temple(
            self.role_file("archivebox_daily_grooming.sh.temple"),
            archivebox_schedule_script,
            {
                "user": self.archivebox_user,
                "stackname": self.stackname,
                "archive_dir": archivebox_datadir / "archive",
            },
            owner=self.archivebox_user,
            group=self.archivebox_group,
            mode=0o0700,
        )
        line_in_crontab(self.archivebox_user, f"MAILTO={self.archivebox_user}", prepend=True)
        line_in_crontab(self.archivebox_user, f"17 3 * * * {str(archivebox_schedule_script)}")

        # Docker Compose file
        homeswarm_compose_file = self.roledir / "compose.yml"
        # pihole_ip = socket.getaddrinfo(self.pihole_domain, None)[0][4][0]
        pihole_ip = "192.168.1.115"
        self.localhost.temple(
            self.role_file("compose.yml.temple"),
            homeswarm_compose_file,
            {
                # "archivebox_container": archivebox_tag,
                "archivebox_container": annals_archivebox_tag,
                "archivebox_uid": archivebox_getent.uid,
                "archivebox_gid": archivebox_getent.gid,
                "archivebox_datadir": str(archivebox_datadir),
                "archivebox_srcdir": str(archivebox_srcdir),
                # "stackname": self.stackname,
                "archivebox_domain": self.archivebox_domain,
                "archivebox_sonic_confdir": str(archivebox_sonic_confdir),
                "archivebox_sonic_backend_password": archivebox_sonic_backend_password,
                "pihole_webpassword": self.pihole_webpassword,
                "pihole_datadir": str(pihole_datadir),
                "pihole_domain": self.pihole_domain,
                "pihole_serverip": pihole_ip,
                "whoami_domain": self.whoami_domain,
                "balancer_domain": self.balancer_domain,
                "traefik_config_file": str(traefik_yml_file),
                "traefik_acme_storage": str(traefik_acme_storage),
                "traefik_aws_creds_file": str(traefik_aws_creds_file),
                "acme_aws_region": self.acme_aws_region,
                "acme_aws_zone": self.acme_aws_zone,
            },
            owner="root",
            group="root",
            mode=0o0640,
        )

        swarmstate = magicrun(["docker", "info", "--format", "{{ .Swarm.LocalNodeState }}"]).stdout.getvalue().strip()
        if swarmstate == "inactive":
            # Initialize Docker Swarm
            magicrun(["docker", "swarm", "init"])
            swarmstate = (
                magicrun(["docker", "info", "--format", "{{ .Swarm.LocalNodeState }}"]).stdout.getvalue().strip()
            )
        if swarmstate != "active":
            raise RuntimeError(f"Swarm state is {swarmstate}")

        # Deploy the stack to Docker Swarm
        magicrun(["docker", "stack", "deploy", "-c", str(homeswarm_compose_file), self.stackname])

        # Install the archivebox docker wrapper scripts
        self.localhost.temple(
            self.role_file("archivebox-docker-run.sh.temple"),
            "/usr/local/bin/archivebox-docker-run.sh",
            {
                "user": self.archivebox_user,
                "container": annals_archivebox_tag,
                "volume": str(archivebox_datadir),
            },
            owner="root",
            group="root",
            mode=0o0755,
        )
        self.localhost.temple(
            self.role_file("archivebox-docker-exec.sh.temple"),
            "/usr/local/bin/archivebox-docker-exec.sh",
            {
                "user": self.archivebox_user,
                "stackname": self.stackname,
            },
            owner="root",
            group="root",
            mode=0o0755,
        )

        # Manual configuration:
        #
        # Create the superuser:
        # archivebox-docker-exec.sh archivebox manage createsuperuser --username archivist --email psyops@micahrl.com --noinput
        # archivebox-docker-exec.sh archivebox manage changepassword archivist
        # ... this requires an interactive session
        #
        # Note that you don't want to exec into the container and run ArchiveBox commands,
        # because the entrypoint script sets environment variables that aren't set in the Dockerfile.
        # If you want to exec into the container,
        # you have to figure out what the entrypoint script does and do that yourself first.
