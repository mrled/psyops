#!/usr/bin/env python3
import glob
import os
from os import path
import sys

reporoot = path.dirname(path.dirname(path.abspath(__file__)))
repohooks = path.join(reporoot, "githooks")
githooks = path.join(reporoot, ".git", "hooks")
for hook in glob.glob(path.join(repohooks, "*")):
    hookname = path.basename(hook)
    if hookname == path.basename(__file__):
        continue
    dest = path.join(githooks, hookname)
    relhook = path.relpath(hook, githooks)
    print("Hook", hookname, end=" ")
    if path.islink(dest):
        linktarget = os.readlink(dest)
        if linktarget == relhook:
            print("is already installed.")
            continue
        print(
            f"is already installed, but points to {linktarget} instead of correct hook {hook}."
        )
        sys.exit(1)
    elif path.exists(dest):
        print("exists and is not a symlink.")
        sys.exit(1)
    print("... installing ...", end=" ")
    os.symlink(relhook, dest)
    print("Done")
