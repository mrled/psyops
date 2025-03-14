"""Create users and groups"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

from progfiguration.cmd import magicrun

from progfiguration_blacksite.sitelib import userdb


@dataclass
class GetentPasswdResult:
    name: str
    passwd: str
    uid: int
    gid: int
    gecos: str
    homedir: Path
    shell: str

    def from_passwd_line(line):
        name, passwd, uid, gid, gecos, homedir, shell = line.split(":")
        return GetentPasswdResult(name, passwd, int(uid), int(gid), gecos, Path(homedir), shell)


@dataclass
class GetentGroupResult:
    name: str
    passwd: str
    gid: int
    members: list[str]

    def from_group_line(line):
        splitline = line.split(":")
        if len(splitline) == 3:
            name, passwd, gid = splitline
            return GetentGroupResult(name, passwd, int(gid), [])
        elif len(splitline) == 4:
            name, passwd, gid, members = splitline
            return GetentGroupResult(name, passwd, int(gid), members.split(","))
        else:
            raise ValueError(f"Invalid group line: {line}")


def getent_passwd(user: str) -> GetentPasswdResult:
    """Get passwd entry for a user"""
    result = magicrun(["getent", "passwd", user], check=False)
    if result.returncode != 0:
        raise ValueError(f"User {user} does not exist")
    return GetentPasswdResult.from_passwd_line(result.stdout.getvalue())


def getent_group(group: str) -> GetentGroupResult:
    """Get group entry for a group"""
    result = magicrun(["getent", "group", group], check=False)
    if result.returncode != 0:
        raise ValueError(f"Group {group} does not exist")
    return GetentGroupResult.from_group_line(result.stdout.getvalue())


def add_managed_service_group(groupname: str) -> GetentGroupResult:
    """Create a managed service group.

    Managed service groups must exist in userdb.py.

    Args:

    groupname:
        The groupname

    Do nothing if the group already exists with this UID.
    Raise an exception if the group exists with a different UID.
    """
    gid = userdb.groups[groupname]
    try:
        group = getent_group(groupname)
    except ValueError as exc:
        magicrun(["addgroup", "-g", str(gid), groupname])
        group = getent_group(groupname)
    if group.gid != gid:
        raise ValueError(f"Group {groupname} exists with a different GID")
    return group


def add_managed_service_account(
    username: str,
    primary_group: str,
    groups: Optional[list[str]] = None,
    home: Union[bool, str] = True,
    shell: str = "/sbin/nologin",
) -> GetentPasswdResult:
    """Create a managed service account.

    Managed service accounts must exist in userdb.py.

    Args:

    username:
        The username

    primary_group:
        The primary group name. This must be present in userdb.groups.

    groups:
        A list of additional groups to add the user to.
        These groups must already exist on the system,
        but need not be present in userdb.groups.

    home:
        If True, create a homedir at the default location.
        If False, do not create a homedir.
        If a string, treat it as a path to the homedir to be created.

    Do nothing if the user already exists with this UID.
    Raise an exception if the user exists with a different UID.
    """
    groups = groups or []
    uid = userdb.users[username]
    prim_group_entry = add_managed_service_group(primary_group)
    try:
        user = getent_passwd(username)
    except ValueError:
        cmd = ["adduser", "-D", "-u", str(uid), "-s", shell, "-G", prim_group_entry.name]
        if home is False:
            cmd += ["-H"]
        elif isinstance(home, str):
            cmd += ["-h", home]
        cmd += [username]
        magicrun(cmd)
        user = getent_passwd(username)
    if user.uid != uid:
        raise ValueError(f"User {username} exists with a different UID")
    for group in groups or []:
        magicrun(["adduser", username, group])
    return user
