#!/usr/bin/env python3

import argparse
import glob
import os
import sys


scriptdir = os.path.dirname(os.path.realpath(__file__))


def buildhooks(hooksdir):
    hooks = []
    for hook in glob.glob(f"{hooksdir}/*.hook.json"):
        with open(hook) as hf:
            hooks.append(hf.read().strip())
    return "[" + ",\n".join(hooks) + "]\n"


def main(*args, **kwargs):
    parser = argparse.ArgumentParser(help="Build a capthook hooks.json file from a directory of .hook.json files")
    parser.add_argument("hooksdir")
    parser.add_argument("outfile")
    parsed = parser.parse_args()
    allhooks = buildhooks(parsed.hooksdir)
    with open(parsed.outfile, "w") as of:
        of.write(allhooks)


if __name__ == "__main__":
    sys.exit(main(*sys.argv))
