"""What the nodes have to say about themselves"""


from importlib.abc import Traversable
import os
from pathlib import Path
import shutil
import string
import subprocess
from typing import Any, Dict, List, Optional

from progfiguration import temple

from progfiguration.localhost.localusers import LocalhostUsers


class LocalhostLinux:
    """An interface to localhost running Linux.

    Maintains a cache of files it has read before.
    """

    def __init__(self, nodename="localhost"):
        self.nodename = nodename
        self.users = LocalhostUsers(self)
        self._cache_files = {}

    @property
    def uptime(self) -> float:
        """Return system uptime in seconds"""
        # System uptime in seconds, and idle CPU time in seconds
        # Note that idle CPU time accounts for idle seconds per CPU, and thus may be larger than system uptime
        uptimestr, idletimestr = self.get_file_contents("/proc/uptime", refresh=True).split()
        uptime = float(uptimestr)
        return uptime

    def get_umask(self):
        """Return the umask as integer

        Only works on Linux
        ... how the fuck is this not part of the standard library?
        <https://stackoverflow.com/questions/7150826/how-can-i-get-the-default-file-permissions-in-python>
        """
        mask = None
        with open("/proc/self/status") as fd:
            for line in fd:
                if line.startswith("Umask:"):
                    mask = int(line[6:].strip(), 8)
                    break

        if not mask:
            raise Exception("Could not find umask, lol")

        return mask

    def get_file_contents(self, path: str, chomp=True, refresh=False):
        """Retrieve file contents

        path:       The path to retrieve
        chomp:      Remove leading/trailing whitespace
        refresh:    Ignore cache if any
        """
        if refresh or path not in self._cache_files:
            with open(path) as fp:
                contents = fp.read()
        else:
            contents = self._cache_files[path]
        if chomp:
            return contents.strip()
        else:
            return contents

    def set_file_contents(
        self,
        path: str | Path | Traversable,
        contents: str,
        owner: Optional[str] = None,
        group: Optional[str] = None,
        mode: Optional[int] = None,
        dirmode: Optional[int] = None,
    ):
        if not isinstance(path, str):
            path = str(path)
        self.makedirs(os.path.dirname(path), owner, group, dirmode)
        if path in self._cache_files:
            del self._cache_files[path]
        with open(path, "w") as fp:
            fp.write(contents)
        if owner or group:
            shutil.chown(path, owner, group)
        if mode:
            os.chmod(path, mode)

    def makedirs(
        self,
        path: str | Path | Traversable,
        owner: Optional[str] = None,
        group: Optional[str] = None,
        mode: Optional[int] = None,
    ):
        if isinstance(path, str):
            path = Path(os.path.abspath(path))
        if path.exists():
            return
        if not mode:
            mode = 0o0777 - self.get_umask()
        head = path.parent
        if not os.path.exists(head):
            self.makedirs(head, owner, group, mode)
        # while os.path.islink(head):
        #     head = os.readlink(head)
        if not head.is_dir():
            raise Exception(f"Path component {head} exists but it is not a directory")
        # We have to set the mode separately, as os.mkdir()'s mode argument is umasked
        # <https://stackoverflow.com/questions/37118558/python3-os-mkdir-does-not-enforce-correct-mode>
        os.mkdir(str(path))
        path.chmod(mode)
        if owner or group:
            shutil.chown(str(path), user=owner, group=group)

    def cp(
        self,
        src: str | Path | Traversable,
        dest: str | Path | Traversable,
        owner: Optional[str] = None,
        group: Optional[str] = None,
        mode: Optional[int] = None,
        dirmode: Optional[int] = None,
    ):
        if isinstance(dest, str):
            dest = Path(dest)
        self.makedirs(dest.parent, owner, group, dirmode)
        if os.path.exists(str(src)):
            shutil.copy(src, dest)
        elif hasattr(src, "open"):
            if dest.is_dir():
                dest = dest.joinpath(src.parent.name)
            with src.open("r") as srcfp:
                with dest.open("w") as destfp:
                    shutil.copyfileobj(srcfp, destfp)
        else:
            raise Exception(f"Not sure how to copy src (type: {type(src)}) at {src} (does it exist?)")
        if owner or group:
            shutil.chown(dest, user=owner, group=group)
        if mode:
            dest.chmod(mode)

    def _template_backend(
        self,
        template: type,
        src: str | Path | Traversable,
        dest: str | Path | Traversable,
        template_args: Dict[str, Any],
        owner: Optional[str] = None,
        group: Optional[str] = None,
        mode: Optional[int] = None,
        dirmode: Optional[int] = None,
    ):
        """Template a file using the appropriate backend"""
        if isinstance(dest, str):
            dest = Path(dest)
        if isinstance(src, str):
            src = Path(src)
        self.makedirs(dest.parent, owner, group, dirmode)
        with src.open() as fp:
            template_contents = template(fp.read())
        inflated = template_contents.substitute(**template_args)
        self.set_file_contents(dest, inflated, owner, group, mode)

    def template(
        self,
        src: str,
        dest: str,
        template_args: Dict[str, Any],
        owner: Optional[str] = None,
        group: Optional[str] = None,
        mode: Optional[int] = None,
        dirmode: Optional[int] = None,
    ):
        return self._template_backend(string.Template, src, dest, template_args, owner, group, mode, dirmode)

    def temple(
        self,
        src: str,
        dest: str,
        template_args: Dict[str, Any],
        owner: Optional[str] = None,
        group: Optional[str] = None,
        mode: Optional[int] = None,
        dirmode: Optional[int] = None,
    ):
        return self._template_backend(temple.Temple, src, dest, template_args, owner, group, mode, dirmode)

    def linesinfile(self, file: str, lines: List[str]):
        """Ensure all lines in the input list exist in a file.

        Inspired by Ansible's lineinfile module, but simpler and less featureful
        """
        oldlines = self.get_file_contents(file, refresh=True).split("\n")
        newlines = oldlines.copy()
        for line in lines:
            if line not in oldlines:
                newlines += [line]
        self.set_file_contents(file, "\n".join(newlines))

    def get_user_primary_group(self, user: str):
        """Get the primary group for a user.

        Use the `id` command because it is POSIX compliant
        and works with non-local users and groups like LDAP etc.
        """
        result = subprocess.run(["id", "-g", "-n", user], capture_output=True, check=True)
        return result.stdout.decode().strip()


class LocalhostLinuxPsyopsOs(LocalhostLinux):
    """An interface to localhost running psyopsOS"""

    @property
    def alpine_release_str(self) -> str:
        return self.get_file_contents("/etc/alpine-release")

    @property
    def alpine_release(self) -> List[int]:
        return [int(n) for n in self.alpine_release_str.split(".")]

    @property
    def alpine_release_v(self) -> str:
        """If /etc/alpine-release is '3.16.0', this returns 'v3.16'."""
        maj, min, _ = self.alpine_release
        return f"v{maj}.{min}"
