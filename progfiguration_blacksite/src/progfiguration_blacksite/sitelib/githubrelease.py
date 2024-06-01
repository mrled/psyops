#!/usr/bin/env python3

import json
import os
import re
import shutil
import urllib.request


def download_github_release(
    projectpath: str,
    assetregex: str,
    outdir: str | None = None,
    outfile: str | None = None,
    version="latest",
    owner: str | None = None,
    group: str | None = None,
    mode: int | None = None,
):
    """Download a release asset from a GitHub project"""

    if outdir is None and outfile is None:
        raise ValueError("Either outdir or outfile must be set")
    if outdir is not None and outfile is not None:
        raise ValueError("Only one of outdir or outfile may be set")

    if version == "latest":
        reluri = f"https://api.github.com/repos/{projectpath}/releases/{version}"
    else:
        reluri = f"https://api.github.com/repos/{projectpath}/releases/tags/{version}"

    jbody = json.loads(urllib.request.urlopen(reluri).read().decode())
    assets = [asset for asset in jbody["assets"] if re.search(assetregex, asset["name"])]

    if len(assets) == 0:
        raise Exception(f"Regular expression '{assetregex}' could not identify any assets")
    elif len(assets) > 1:
        assnames = [ass["name"] for ass in assets]
        raise Exception(f"Regular expression '{assetregex}' found {len(assets)} assets with names: {assnames}")

    asset = assets[0]
    if outfile is None:
        outfile = f"{outdir}/{asset['name']}"
    with open(outfile, "wb") as assfile:
        assfile.write(urllib.request.urlopen(asset["browser_download_url"]).read())

    if owner or group:
        if not owner:
            owner = -1
        shutil.chown(outfile, owner, group)
    if mode is not None:
        os.chmod(outfile, mode)
