"""WeVersionTogether(tm)"""

import os.path
import subprocess


def getversion():
    """Find the version of the package"""

    try:
        # The build_version.py file is created by the build process (tasks.py)
        # It isn't and shouldn't be in git
        from progfiguration import build_version

        return build_version.VERSION
    except ImportError:
        pass

    # If we don't have a build_version module, we aren't being called from tasks.py.
    # Probably we are trying to install the package as editable, like 'pip install -e .'
    # Return a useless static version number in that case.
    return "0.0.1-alpha"
