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
