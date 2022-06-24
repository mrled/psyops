"""What the nodes have to say about themselves"""


import os
import shutil
from typing import List, Optional


class SystemNode:
    """A node managed by progfiguration

    Maintains a cache of files it has read before.
    """

    def __init__(self, nodename):
        self.nodename = nodename
        self._cache_files = {}

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

    def set_file_contents(self, path: str, contents: str, owner: Optional[str] = None, group: Optional[str] = None, mode: Optional[int] = None):
        if path in self._cache_files:
            del self._cache_files[path]
        with open(path, "w") as fp:
            fp.write(contents)
        if owner or group:
            shutil.chown(path, owner, group)
        if mode:
            os.chmod(path, mode)



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
