#!/usr/bin/env python3

import argparse
from dataclasses import dataclass, field
from functools import cached_property
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from typing import List
import urllib.request


@dataclass
class State:
    """A bag of holding for state, constants, and global variables"""

    project_path: str = "slackhq/nebula"
    asset_regex: str = r"linux-amd64.*\.tar\.gz"
    bin_path: str = "/usr/local/bin"
    asset_dl_filename: str = "nebula.tgz"
    binaries: List[str] = field(default_factory=lambda: ["nebula", "nebula-cert"])

    @property
    def bin_path_nebula(self):
        return os.path.join(self.bin_path, "nebula")

    @property
    def bin_path_nebula_cert(self):
        return os.path.join(self.bin_path, "nebula-cert")

    @cached_property
    def installed(self):
        return os.path.exists(self.bin_path_nebula)

    @cached_property
    def version_installed(self):
        if not self.installed:
            return None
        output = subprocess.run(
            [self.bin_path_nebula, "--version"], capture_output=True, check=True
        )
        verstr = output.stdout.decode().strip()
        version = verstr.replace("Version: ", "")
        return version

    @cached_property
    def version_released(self):
        tag_raw = get_gh_release_tag(self.project_path)
        version = tag_raw.replace("v", "")
        return version

    @cached_property
    def needs_update(self):
        return tuple_compare_versions_gt(self.version_installed, self.version_released)


def get_gh_release(projectpath, assetregex, outpath):
    latesturi = f"https://api.github.com/repos/{projectpath}/releases/latest"
    jbody = json.loads(urllib.request.urlopen(latesturi).read().decode())
    assets = [
        asset for asset in jbody["assets"] if re.search(assetregex, asset["name"])
    ]

    if len(assets) == 0:
        raise Exception(
            f"Regular expression '{assetregex}' could not identify any assets"
        )
    elif len(assets) > 1:
        assnames = [ass["name"] for ass in assets]
        raise Exception(
            f"Regular expression '{assetregex}' found {len(assets)} assets with names: {assnames}"
        )

    asset = assets[0]
    # with open(f"{outdir}/{asset['name']}", "wb") as assfile:
    with open(outpath, "wb") as assfile:
        assfile.write(urllib.request.urlopen(asset["browser_download_url"]).read())


def get_gh_release_tag(projectpath):
    latesturi = f"https://api.github.com/repos/{projectpath}/releases/latest"
    jbody = json.loads(urllib.request.urlopen(latesturi).read().decode())
    return jbody["tag_name"]


def tuple_compare_versions_gt(ver1, ver2):
    """Use a tuple to compare version, returning True if ver2 is higher than ver1, False otherwise.

    This has some drawbacks, but it's simple and requires no external libraries.
    <https://stackoverflow.com/questions/11887762/how-do-i-compare-version-numbers-in-python>
    """
    if not ver1:
        ver1 = "0"
    if not ver2:
        ver2 = "0"
    vertup1 = tuple(map(int, ver1.split(".")))
    vertup2 = tuple(map(int, ver2.split(".")))
    return vertup2 > vertup1


def nebula_cap_admin(state: State):
    """Give the Nebula binary permission to create new network interfaces for its tun"""
    subprocess.run(["setcap", "cap_net_admin=+pe", state.bin_path_nebula])


def download_install_nebula(state: State, force: bool = False):
    needsinstall = not state.installed or force or state.needs_update
    if not needsinstall:
        print(
            f"Nothing to do, installed version {state.version_installed} is the latest"
        )
    else:
        with tempfile.TemporaryDirectory() as tmpdir:
            dlfile = os.path.join(tmpdir, state.asset_dl_filename)
            get_gh_release(state.project_path, state.asset_regex, dlfile)
            with tarfile.open(dlfile, "r:gz") as tar:
                os.chdir(tmpdir)
                # This extracts to CWD
                tar.extractall()
                for bin in state.binaries:
                    shutil.move(
                        os.path.join(tmpdir, bin), os.path.join(state.bin_path, bin)
                    )
        nebula_cap_admin(state)


def main(*args, **kwargs):
    default_state = State()
    parser = argparse.ArgumentParser(
        description="Download the latest release of Nebula"
    )
    parser.add_argument(
        "--project-path",
        default=default_state.project_path,
        help="Project path relative to Github, like 'slackhq/nebula' for https://github.com/slackhq/nebula.",
    )
    parser.add_argument(
        "--asset-regex",
        default=default_state.asset_regex,
        help="A regular expression to uniquely identify the asset for a given release.",
    )
    parser.add_argument(
        "--bin-path",
        default=default_state.bin_path,
        help=f"Path to install binaries. Defaults to {default_state.bin_path}",
    )
    subparsers = parser.add_subparsers(dest="action", required=True)
    s_download = subparsers.add_parser(
        "download",
        help="Download a release from Github",
    )
    s_download.add_argument(
        "outfile",
        help="Path to save the downloaded binary to",
    )
    s_checkver = subparsers.add_parser(
        "checkver", help="Check the local and remote versions"
    )
    s_install = subparsers.add_parser(
        "install",
        help="Download a release from Github and install it",
    )
    s_install.add_argument(
        "--force",
        action="store_true",
        help="Re-install even if the upstream version is the same",
    )
    s_setcap = subparsers.add_parser(
        "setcap", help="Add NET_CAP_ADMIN to nebula binary"
    )

    parsed = parser.parse_args()

    state = State(parsed.project_path, parsed.asset_regex, parsed.bin_path)

    if parsed.action == "download":
        get_gh_release(state.project_path, state.asset_regex, parsed.outfile)

    elif parsed.action == "checkver":
        print(f"Installed version:  {state.version_installed}")
        print(f"Latest release:     {state.version_released}")
        print(f"Needs update?       {state.needs_update}")

    elif parsed.action == "install":
        download_install_nebula(state, force=parsed.force)

    elif parsed.action == "setcap":
        nebula_cap_admin(state)

    else:
        raise Exception(f"Unknown action {parsed.action}")


if __name__ == "__main__":
    sys.exit(main(*sys.argv))
