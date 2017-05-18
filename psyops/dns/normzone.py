#!/usr/bin/env python3
"""
The Gandi API doesn't strip comments from zonefiles, so I guess I have to do it myself
"""

import argparse
import logging
import os
import re
import sys


scriptdir = os.path.dirname(os.path.realpath(__file__))


def resolvepath(path):
    return os.path.realpath(os.path.normpath(os.path.expanduser(path)))


def normalize(zone):
    """Normalize a zonefile by stripping comments and empty lines
    zone: A string representing a zonefile
    returns: A string representing a normalized zonefile
    """
    return re.sub("\s*\;.*", "", zone)


# Main handling
# The main() function is not special - it's invoked explicitly at the end
def main(*args, **kwargs):
    logging.basicConfig()
    parser = argparse.ArgumentParser(
        description="A template for writing a new Python3 command line tool")
    parser.add_argument(
        "-d", action='store_true', dest='debug',
        help="Include debugging output")
    parser.add_argument(
        "zonefile", nargs='+',
        help="The zonefile(s) to normalize")
    parsed = parser.parse_args()
    if parsed.debug:
        logging.root.setLevel(logging.DEBUG)
    for zf in parsed.zonefile:
        # import pdb; pdb.set_trace()
        with open(resolvepath(zf), 'br') as file:
            # Open in binary so we can deal w/ a possible byte order mark
            # 'utf-8-sig' will strip BOM if present and work like 'utf-8' otherwise
            zone = file.read().decode('utf-8-sig')
            normalized = normalize(zone)
        normfile = resolvepath("{}.normalized".format(zf))
        logging.debug("Normalized zonefile:\n{}".format(normfile))
        with open(normfile, 'bw') as file:
            file.write(normalized.encode())


# Unless we are running this script directly on the commandline, the main()
# function will NOT execute
if __name__ == '__main__':
    sys.exit(main(*sys.argv))
