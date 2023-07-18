"""WeVersionTogether(tm)"""

import datetime
from dataclasses import dataclass


@dataclass
class VersionInfo:
    """Version information for the package"""

    version_set: bool
    version: str
    date: datetime.datetime

    # TODO: Determine if we're in a git repo, and if so what the commit is and if it's dirty

    def __str__(self):
        return self.version

    def verbose(self):
        """Return a version string for human consumption"""
        if self.version_set:
            return f"progfiguration {self.version}, built on {self.date}"
        else:
            return f"UNVERSIONED (probably running from a git clone)"

    @classmethod
    def from_build_version_or_default(cls):
        """Return a VersionInfo object from the build_version module, or a default if it doesn't exist.

        The build_version module only exists when tasks.py builds the package.
        Otherwise (such as when installing the package with pip -e), it doesn't exist,
        and we return a default version instead.
        """
        try:
            from progfiguration import build_version

            return cls(True, build_version.VERSION, build_version.DATE)
        except ImportError:
            return cls(False, "0.0.1-alpha", datetime.datetime.now())


def getversion():
    """Return only the version of the package"""

    return VersionInfo.from_build_version_or_default().version
