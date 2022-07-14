"""WeVersionTogether(tm)"""

import os.path
import subprocess


def getversion():
    """Find the version of the package"""

    try:
        from progfiguration import build_version

        return build_version.VERSION
    except ImportError:
        pass

    parent = os.path.dirname(__file__)
    try:
        result = subprocess.run(["git", "rev-parse", "HEAD"], check=True, capture_output=True, cwd=parent)
        git_revision = result.stdout.decode().strip()
    except BaseException:
        git_revision = None

    if not git_revision:
        raise Exception(
            f"Detected neither build_version.py module or git repository; not sure how to determine version"
        )

    try:
        subprocess.run(["git", "diff", "--quiet"], check=True, capture_output=True, cwd=parent)
        dirty = ""
    except subprocess.CalledProcessError:
        dirty = "-dirty"

    return f"{git_revision}{dirty}"
