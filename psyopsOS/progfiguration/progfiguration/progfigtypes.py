"""Progfiguration types

Things here should not depend on any other parts of the progfiguration package
"""


from importlib.abc import Traversable
from pathlib import Path as PathlibPath
from typing import Union
from zipfile import Path as ZipfilePath


AnyPath = Union[PathlibPath, Traversable, ZipfilePath]
AnyPathOrStr = Union[AnyPath, str]


class Bunch:
    """A nice little object wrapper.
    From <https://code.activestate.com/recipes/52308-the-simple-but-handy-collector-of-a-bunch-of-named/?in=user-97991>
    """

    def __init__(self, **kwds):
        self.__dict__.update(kwds)
