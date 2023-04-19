"""Progfiguration types

Things here should not depend on any other parts of the progfiguration package
"""


from importlib.abc import Traversable
from pathlib import Path as PathlibPath
from typing import Union
from zipfile import Path as ZipfilePath


AnyPath = Union[PathlibPath, Traversable, ZipfilePath]
AnyPathOrStr = Union[AnyPath, str]
