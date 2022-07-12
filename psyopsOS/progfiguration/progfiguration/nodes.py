"""What the nodes have to say about themselves"""


import os
import shutil
import string
from typing import Any, Dict, List, Optional


class SystemNode:
    """A node managed by progfiguration

    Maintains a cache of files it has read before.
    """

    def __init__(self, nodename):
        self.nodename = nodename
        self._cache_files = {}

    def get_umask(self):
        """Return the umask as integer

        Only works on Linux
        ... how the fuck is this not part of the standard library?
        <https://stackoverflow.com/questions/7150826/how-can-i-get-the-default-file-permissions-in-python>
        """
        mask = None
        with open('/proc/self/status') as fd:
            for line in fd:
                if line.startswith('Umask:'):
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
        path: str,
        contents: str,
        owner: Optional[str] = None,
        group: Optional[str] = None,
        mode: Optional[int] = None,
        dirmode: Optional[int] = None,
    ):
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
        path: str,
        owner: Optional[str] = None,
        group: Optional[str] = None,
        mode: Optional[int] = None,
    ):
        path = os.path.abspath(path)
        if not mode:
            mode = 0o0777 - self.get_umask()
        if os.path.exists(path):
            return
        head, tail = os.path.split(path)
        if not os.path.exists(head):
            self.makedirs(head, owner, group, mode)
        # while os.path.islink(head):
        #     head = os.readlink(head)
        if not os.path.isdir(head):
            raise Exception(f"Path component {head} exists but it is not a directory")
        if not os.path.exists(path):
            # We have to set the mode separately, as os.mkdir()'s mode argument is umasked
            # <https://stackoverflow.com/questions/37118558/python3-os-mkdir-does-not-enforce-correct-mode>
            os.mkdir(path)
            os.chmod(path, mode)
            if owner or group:
                shutil.chown(path, user=owner, group=group)

    def cp(
        self,
        src: str,
        dest: str,
        owner: Optional[str] = None,
        group: Optional[str] = None,
        mode: Optional[int] = None,
        dirmode: Optional[int] = None,
    ):
        self.makedirs(os.path.dirname(dest), owner, group, dirmode)
        shutil.copy(src, dest)
        if owner or group:
            shutil.chown(dest, user=owner, group=group)
        if mode:
            os.chmod(dest, mode)

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
        self.makedirs(os.path.dirname(dest), owner, group, dirmode)
        with open(src) as fp:
            template_contents = string.Template(fp.read())
        inflated = template_contents.substitute(**template_args)
        self.set_file_contents(dest, inflated, owner, group, mode)


class PsyopsOsNode(SystemNode):
    """The node running psyopsOS"""

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
