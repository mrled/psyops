"""psyopsOS progfiguration module"""

import logging
import os


"""We define a root logger here that will log any level, but no handler.

Expect that cli.py will configure handlers set to the appropriate level.
"""
logger = logging.getLogger()
logger.setLevel(logging.NOTSET)


"""An editable install can build itself.

We use this so it can find the build script.
"""
repo_root = os.path.dirname(os.path.dirname(__file__))
progfiguration_build_path = os.path.join(repo_root, "progfiguration_build.py")
