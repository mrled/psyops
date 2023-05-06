"""Local user and group management"""


from pathlib import Path
import subprocess
from dataclasses import dataclass


@dataclass
class GetentUserResult:
    name: str
    passwd: str
    uid: int
    gid: int
    gecos: str
    homedir: Path
    shell: str


class LocalhostUsers:
    def __init__(self, localhost):
        self.localhost = localhost

    def add_service_account(
        self, username, primary_group, uid=None, primary_gid=None, groups=None, home=True, shell="/sbin/nologin"
    ) -> GetentUserResult:
        """Create a system user without a password and a primary group for it

        home:   If True, create a homedir at the default location
                If False, do not create a homedir
                If a string, treat it as a path to the homedir to be created

        WARNING: Most arguments are not idempotent; if the user already exists, this will not change any of its attributes.
        However, it will add the user to any groups specified in the groups argument.
        """
        self.add_group(primary_group, primary_gid, system=True)
        if not self.user_exists(username):
            cmd = ["adduser", "-D", "-S", "-s", shell, "-G", primary_group]
            if uid:
                cmd += ["-u", uid]
            if home is False:
                cmd += ["-H"]
            elif isinstance(home, str):
                cmd += ["-h", home]
            cmd += [username]
            subprocess.run(cmd, check=True)
        for group in groups or []:
            self.add_user_to_group(username, group)
        return self.getent_user(username)

    def add_group(self, groupname, gid=None, system=False):
        """Add a group"""
        if self.group_exists(groupname):
            return
        cmd = ["addgroup"]
        if gid:
            cmd += ["-g", gid]
        if system:
            cmd += ["-S"]
        cmd += [groupname]
        subprocess.run(cmd, check=True)

    def add_user_to_group(self, username, groupname):
        """Add a user to a group

        This is an idempotent operation with the adduser command
        """
        subprocess.run(["adduser", username, groupname], check=True)

    def user_exists(self, username):
        """Check if a user exists"""
        try:
            subprocess.run(["id", username], check=True)
            return True
        except subprocess.CalledProcessError:
            return False

    def group_exists(self, groupname):
        """Check if a group exists"""
        try:
            subprocess.run(["getent", "group", groupname], check=True)
            return True
        except subprocess.CalledProcessError:
            return False

    def getent_user(self, user):
        """Get the home directory of a user"""
        result = subprocess.run(["getent", "passwd", user], check=True, capture_output=True)
        name, passwd, uid, gid, gecos, homedir, shell = result.stdout.decode().split(":")
        uresult = GetentUserResult(name, passwd, int(uid), int(gid), gecos, Path(homedir), shell)
        return uresult
