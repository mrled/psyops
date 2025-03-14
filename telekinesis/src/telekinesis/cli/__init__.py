"""Supporting functions for the telekinesis command line interface(s)"""

import os
import pdb
import sys
import traceback


def idb_excepthook(type, value, tb):
    """Call an interactive debugger in post-mortem mode"""
    if hasattr(sys, "ps1") or not sys.stderr.isatty():
        sys.__excepthook__(type, value, tb)
    else:
        traceback.print_exception(type, value, tb)
        print
        pdb.pm()


def setup_repo_python_path():
    """Add packages in this repository to the python path

    A hack because we don't have progfiguration_blacksite as a PyPI package,
    and while progfiguration is a PyPI pacakge,
    we might want to use local modifications.
    """

    # Find the closest ancestor directory containing a pyproject.toml file
    current_dir = os.path.abspath(os.path.dirname(__file__))
    while not os.path.exists(os.path.join(current_dir, "pyproject.toml")):
        current_dir = os.path.dirname(current_dir)
        if current_dir == "/":
            raise Exception("Could not find pyproject.toml")
    tk_root = current_dir

    # Find the repository root, and important packages from there
    repo_root = os.path.abspath(os.path.join(tk_root, ".."))
    progfiguration_dir = os.path.join(repo_root, "submod", "progfiguration", "src")
    blacksite_dir = os.path.join(repo_root, "progfiguration_blacksite", "src")

    if progfiguration_dir not in sys.path:
        sys.path.insert(0, progfiguration_dir)
    if blacksite_dir not in sys.path:
        sys.path.insert(1, blacksite_dir)
