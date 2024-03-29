#!/usr/bin/env python3

import argparse
import glob
import json
import sys


def buildhooks(hooksdir):
    hooks = []
    for hook in glob.glob(f"{hooksdir}/*.hook.json"):
        with open(hook) as hf:
            hookstr = hf.read()
            try:
                json.loads(hookstr)
            except json.decoder.JSONDecodeError as e:
                print(f"HOOKS COULD NOT BE UPDATED: Error parsing {hook}: {e}")
                sys.exit(1)
            hooks.append(hookstr.strip())
    return "[" + ",\n".join(hooks) + "]\n"


def main(*args, **kwargs):
    parser = argparse.ArgumentParser(
        description="Build a capthook hooks.json file from a directory of .hook.json files"
    )
    parser.add_argument("hooksdir")
    parser.add_argument("outfile")
    parsed = parser.parse_args()
    allhooks = buildhooks(parsed.hooksdir)
    with open(parsed.outfile, "w") as of:
        of.write(allhooks)


if __name__ == "__main__":
    sys.exit(main(*sys.argv))
