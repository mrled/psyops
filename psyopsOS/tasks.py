"""PyInvoke tasks file for psyops.micahrl.com"""

import glob
import json
import os
import pdb
import shutil
import subprocess
import sys
import traceback
from typing import Any, Dict, NamedTuple, Optional

import boto3
import invoke
import yaml


def idb_excepthook(type, value, tb):
    """Call an interactive debugger in post-mortem mode

    If you do "sys.excepthook = idb_excepthook", then an interactive debugger
    will be spawned at an unhandled exception
    """
    if hasattr(sys, "ps1") or not sys.stderr.isatty():
        sys.__excepthook__(type, value, tb)
    else:
        traceback.print_exception(type, value, tb)
        print
        pdb.pm()


sys.excepthook = idb_excepthook


basedir = os.path.abspath(os.path.dirname(__file__))
psyopsos_minisign_encrypted_passwd_file = os.path.join(basedir, ".minisign-pass-secret")

# Input configuration
staticdir = os.path.join(basedir, "static")
psyopsos_cfg = os.path.join(basedir, "psyopsOS.yml")
psyopsos_key = os.path.join(basedir, "minisign.seckey")
progfiguration_dir = os.path.join(basedir, "progfiguration")

# Output configuration
sitedir = os.path.join(basedir, "public")
site_psyopsos_dir = os.path.join(sitedir, "psyopsOS")
site_psyopsos_dir_nodes = os.path.join(site_psyopsos_dir, "nodes")
site_psyopsos_dir_tags = os.path.join(site_psyopsos_dir, "tags")
site_psyopsos_dir_global = os.path.join(site_psyopsos_dir, "global.json")
site_bucket = "com-micahrl-psyops-http-bucket"


class Minisign:
    """A wrapper for minisign operations. Caches the password after retrieving it once."""

    def __init__(self, seckey: str):
        self.seckey = seckey
        self._passwd = None

    def __call__(self, path: str) -> None:
        """Sign a file with minisign"""
        subprocess.run(
            ["minisign", "-S", "-s", self.seckey, "-m", path],
            input=self.passwd,
            check=True,
        )

    @property
    def passwd(self) -> str:
        """Decrypt the PSYOPS/OS minisign secret key password using standard PSYOPS GPG stuff"""
        if not self._passwd:
            proc = subprocess.run(
                [
                    "gpg",
                    "--quiet",
                    "--decrypt",
                    psyopsos_minisign_encrypted_passwd_file,
                ],
                check=True,
                capture_output=True,
            )
            self._passwd = proc.stdout
        return self._passwd


minisign = Minisign(psyopsos_key)


def jsondump(obj: Any, path: str) -> None:
    """A wrapper for json.dump that works the same way every time"""
    with open(path, "w") as fp:
        json.dump(obj, fp, sort_keys=True, indent=2)
        fp.write("\n")
    minisign(path)


def parsecfg(filepath: str) -> Dict[str, Any]:
    with open(filepath) as kfp:
        config = yaml.load(kfp, Loader=yaml.Loader)
    return config


def s3_upload_directory(directory, bucketname):
    """Upload a directory to S3 using AWS creds from ~/.aws

    TODO: keep track of all uploaded files, then at the end list all files in the bucket and delete any we didn't upload
    """
    s3client = boto3.client("s3")
    for root, _, files in os.walk(directory):
        for filename in files:
            local_filepath = os.path.join(root, filename)
            relative_filepath = os.path.relpath(local_filepath, directory)
            print(f"Uploading {local_filepath}...")
            s3client.upload_file(local_filepath, bucketname, relative_filepath)


@invoke.task
def clean(ctx):
    """Clean the build"""
    shutil.rmtree(staticdir)


@invoke.task
def copystatic(ctx):
    """Copy files from the static directory to the site directory"""
    shutil.copytree(staticdir, sitedir, dirs_exist_ok=True)


@invoke.task
def copyconfig(ctx):
    """Copy global/node/etc config from psyopsOS.yml into JSON files in the site directory

    Sign the resulting files with minisign
    """
    copystatic(ctx)
    config = parsecfg(psyopsos_cfg)
    for d in [site_psyopsos_dir_nodes, site_psyopsos_dir_tags]:
        os.makedirs(d, exist_ok=True)
    jsondump(config["global"], site_psyopsos_dir_global)
    tags: Dict[str, str] = {}
    for node, nodecfg in config["nodes"].items():
        nodepath = os.path.join(site_psyopsos_dir_nodes, f"{node}.json")
        jsondump(nodecfg, nodepath)
        if "tags" in nodecfg:
            for tag in nodecfg["tags"]:
                if tag not in tags:
                    tags[tag] = []
                tags[tag].append(node)
    for tag, nodes in tags.items():
        tagdir = os.path.join(site_psyopsos_dir_tags, tag)
        os.makedirs(tagdir, exist_ok=True)
        nodelistpath = os.path.join(tagdir, "nodes.json")
        jsondump(nodes, nodelistpath)


@invoke.task
def deploy(ctx):
    """Deploy the site dir to S3"""
    s3_upload_directory(sitedir, site_bucket)


@invoke.task
def progfiguration(ctx):
    """Build the progfiguration package, copy it to the site dir, and sign it with minisign"""
    print("Running build in progfiguration directory...")
    with ctx.cd(progfiguration_dir):
        # ctx.run("./venv/bin/pip install wheel")
        ctx.run("./venv/bin/python -m build")
    os.rename(
        f"{progfiguration_dir}/dist/progfiguration-0.0.0.tar.gz",
        f"{site_psyopsos_dir}/progfiguration-0.0.0.tar.gz",
    )
    os.rename(
        f"{progfiguration_dir}/dist/progfiguration-0.0.0-py3-none-any.whl",
        f"{site_psyopsos_dir}/progfiguration-0.0.0-py3-none-any.whl",
    )
    print("Signing builds...")
    minisign(f"{site_psyopsos_dir}/progfiguration-0.0.0.tar.gz")
    minisign(f"{site_psyopsos_dir}/progfiguration-0.0.0-py3-none-any.whl")


@invoke.task
def mkimage(
    ctx,
    tag="0x001",
    aportsdir=os.path.expanduser("~/aports"),
    workdir=os.path.expanduser("~/tmp/mkimage-workdir"),
    isodir=os.path.expanduser("~/tmp/isos")
):
    """Run mkimage.sh to build a new Alpine ISO

    Copies prerequisites into the aports directory.
    """
    os.umask(0o022)
    psyopsdir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    psyopsosdir = os.path.join(psyopsdir, "psyopsOS")
    aportsscriptsdir = os.path.join(psyopsosdir, "aports-scripts")

    env = os.environ.copy()
    env["PSYOPSOS_OVERLAY"] = os.path.join(psyopsosdir, "os-overlay")

    # psyopsOS mkimage and genapkovl scripts expect this to be present
    shutil.copy(f"{aportsscriptsdir}/genapkovl-psyopsOS.sh", f"{aportsdir}/scripts/genapkovl-psyopsOS.sh")
    shutil.copy(f"{aportsscriptsdir}/mkimg.psyopsOS.sh", f"{aportsdir}/scripts/mkimg.psyopsOS.sh")

    cleandirs = glob.glob("/tmp/mkimage*") + glob.glob(f"{workdir}/apkovl*") + glob.glob(f"{workdir}/apkroot*")
    for d in cleandirs:
        print(f"Removing {d}...")
        ctx.run(f"sudo rm -rf '{d}'")

    # Doing this just takes too long
    # ctx.run("sudo apk update")

    with ctx.cd(f"{aportsdir}/scripts"):
        cmd = [
            "./mkimage.sh",
            "--tag", tag,
            "--outdir", isodir,
            "--arch", "x86_64",
            "--repository", "http://mirrors.edge.kernel.org/alpine/v3.16/main",
            "--repository", "http://mirrors.edge.kernel.org/alpine/v3.16/community",
            "--workdir", workdir,
            "--profile", "psyopsOS",
        ]
        ctx.run(" ".join(cmd), env=env)
