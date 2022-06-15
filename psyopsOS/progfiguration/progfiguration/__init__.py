"""psyopsOS progfiguration module"""

import logging


"""We define a root logger here that will log any level, but no handler.

Expect that cli.py will configure handlers set to the appropriate level.
"""
logger = logging.getLogger()
logger.setLevel(logging.NOTSET)
