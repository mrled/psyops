"""PyInvoke tasks file for psyopsOS"""

import datetime
import glob
import json
import os
import pdb
import shutil
import subprocess
import sys
from this import s
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

docker_builder_volname_workdir = "psyopsos-build-workdir"

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
    shutil.rmtree(sitedir)


@invoke.task
def cleandockervol(
    ctx,
    volname_workdir=docker_builder_volname_workdir,
):
    """Remove the Docker volume used for the mkimage.sh working directory"""
    ctx.run(f"docker volume rm {volname_workdir}")


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
    for nodename, nodecfg in config["nodes"].items():
        nodepath = os.path.join(site_psyopsos_dir_nodes, f"{nodename}.json")
        nodecfg["nodename"] = nodename
        jsondump(nodecfg, nodepath)
        if "tags" in nodecfg:
            for tag in nodecfg["tags"]:
                if tag not in tags:
                    tags[tag] = []
                tags[tag].append(nodename)
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
def upload_progfiguration(ctx, host):
    ctx.run(
        f"scp {site_psyopsos_dir}/progfiguration-0.0.0-py3-none-any.whl root@{host}:/tmp/"
    )


def osflavorinfo(flavorname):
    """Given the name of an OS flavor, return its Alpine profile and architecture

    WARNING: the rpi flavor doesn't actually work yet.
    It must be built on an aarch64 host, which I haven't bothered to configure.
    """
    osflavors = {
        'pc': ["psyopsOS", "x86_64"],
        'rpi': ["psyopsOS_rpi", "aarch64"],
    }
    if flavorname not in osflavors.keys():
        print(f"The os flavor must be one of: {osflavors.keys()}")
        sys.exit(1)
    return osflavors[flavorname]


class MkimageBuildInfo(NamedTuple):
    date: datetime.datetime
    revision: str
    dirty: bool


def mkimage_buildinfo(ctx):
    build_date = datetime.datetime.now()
    build_git_revision = ctx.run("git rev-parse HEAD").stdout.strip()
    build_git_dirty = ctx.run("git diff --quiet", warn=True).return_code != 0
    return MkimageBuildInfo(build_date, build_git_revision, build_git_dirty)


def mkimage_clean(ctx, indocker, workdir):
    """Clean directories before build

    This should be done before any runs - it doesn't clean apk cache or other large working datasets.
    That's why it's not a separate Invoke task.
    """
    cleandirs = []
    if indocker:
        # If /tmp is persistent, make sure we don't have old stuff lying around
        # Not necessary in Docker, which has a clean /tmp every time
        cleandirs += glob.glob("/tmp/mkimage*")
    cleandirs += glob.glob(f"{workdir}/apkovl*")
    cleandirs += glob.glob(f"{workdir}/apkroot*")
    for d in cleandirs:
        print(f"Removing {d}...")
        ctx.run(f"rm -rf '{d}'")


@invoke.task
def mkimage_local(
    ctx,
    osflavor,
    alpinetag="0x001",
    aportsdir=os.path.expanduser("~/aports"),
    workdir=os.path.expanduser("~/psyopsOS-build-tmp"),
    isodir=os.path.expanduser("~/isos"),
):
    """Run mkimage.sh directly

    Assumes you're running invoke on an Alpine system

    This is not used as often as regular mkimage (which uses docker), and may be out of date!
    """

    mkimage_profile, architecture = osflavorinfo(osflavor)

    os.umask(0o022)

    psyopsdir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    psyopsosdir = os.path.join(psyopsdir, "psyopsOS")
    aportsscriptsdir = os.path.join(psyopsosdir, "aports-scripts")

    buildinfo = mkimage_buildinfo(ctx)

    mkimage_clean(ctx, indocker=True, workdir=workdir)

    for directory in [workdir, isodir]:
        os.makedirs(directory, exist_ok=True)
    for script in ["genapkovl-psyopsOS.sh", "mkimg.psyopsOS.sh", "mkimg.zzz-overrides.sh"]:
        shutil.copy(f"{aportsscriptsdir}/{script}", f"{aportsdir}/scripts/{script}")

    os.environ["PSYOPSOS_OVERLAY"] = f"{psyopsosdir}/os-overlay"
    os.environ["PSYOPSOS_BUILD_DATE_ISO8601"] = buildinfo.date.strftime('%Y-%m-%dT%H:%M:%S%z')
    os.environ["PSYOPSOS_BUILD_GIT_REVISION"] = buildinfo.revision
    os.environ["PSYOPSOS_BUILD_GIT_DIRTY"] = str(buildinfo.dirty)

    mkimage_cmd = [
        "./mkimage.sh",
        "--tag",
        alpinetag,
        "--outdir",
        "/home/build/iso",
        "--arch",
        architecture,
        "--repository",
        "http://mirrors.edge.kernel.org/alpine/v3.16/main",
        "--repository",
        "http://mirrors.edge.kernel.org/alpine/v3.16/community",
        "--workdir",
        "/home/build/workdir",
        "--profile",
        mkimage_profile,
    ]
    full_cmd = " ".join(mkimage_cmd)
    print(f"Running {full_cmd}")
    with ctx.cd(f"{aportsdir}/scripts"):
        ctx.run(full_cmd)
    ctx.run(f"ls -alFh {isodir}*.iso")


@invoke.task
def mkimage(
    ctx,
    osflavor='pc',
    alpinetag="0x001",
    aportsdir=os.path.expanduser("~/Documents/Repositories/aports"),
    workdir=os.path.expanduser("~/Scratch/psyopsOS-build-tmp"),
    isodir=os.path.expanduser("~/Downloads/"),
    dockertag="psyopsos-builder",
    volname_workdir=docker_builder_volname_workdir,
):
    """Build the docker image in build/Dockerfile and use it to run mkimage.sh to build a new Alpine ISO"""

    mkimage_profile, architecture = osflavorinfo(osflavor)

    os.umask(0o022)

    psyopsdir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    psyopsosdir = os.path.join(psyopsdir, "psyopsOS")
    aportsscriptsdir = os.path.join(psyopsosdir, "aports-scripts")

    buildinfo = mkimage_buildinfo(ctx)

    mkimage_clean(ctx, indocker=True, workdir=workdir)

    docker_builder_dir = os.path.join(psyopsosdir, "build")
    ctx.run(f"docker build --tag '{dockertag}' '{docker_builder_dir}'")

    # We use a docker local volume for the workdir
    # This would not be necessary on Linux, but
    # on Docker Desktop for Mac (and probably also on Windows),
    # permissions will get fucked up if you try to use a volume on the host.
    try:
        ctx.run(f"docker volume inspect {volname_workdir}")
    except invoke.Failure:
        ctx.run(f"docker volume create {volname_workdir}")

    docker_cmd = [
        "docker",
        "run",
        "--rm",
        # You must mount the aports scripts
        # (And don't forget to update them)
        "--volume",
        f"{aportsdir}:/home/build/aports",
        # genapkovl-psyopsOS.sh partially sets up the filesystem of the iso live OS
        "--volume",
        f"{aportsscriptsdir}/genapkovl-psyopsOS.sh:/home/build/aports/scripts/genapkovl-psyopsOS.sh",
        # mkimage.psyopsOS.sh defines the profile that we pass to mkimage.sh
        "--volume",
        f"{aportsscriptsdir}/mkimg.psyopsOS.sh:/home/build/aports/scripts/mkimg.psyopsOS.sh",
        # mkimage.zzz-overrides.sh will let us customize any mkimage function by overriding it
        "--volume",
        f"{aportsscriptsdir}/mkimg.zzz-overrides.sh:/home/build/aports/scripts/mkimg.zzz-overrides.sh",
        # Use the previously defined docker volume for temporary files etc when building the image.
        # Saving this between runs makes rebuilds much faster.
        "--volume",
        f"{volname_workdir}:/home/build/workdir",
        # This is where the iso will be copied after it is build
        "--volume",
        f"{isodir}:/home/build/iso",
        # Mounting this allows the build to access the psyopsOS/os-overlay/
        "--volume",
        f"{psyopsdir}:/home/build/psyops",
        # Environment variables that mkimage.sh (or one of the scripts it calls) uses
        "--env",
        f"PSYOPSOS_BUILD_DATE_ISO8601={buildinfo.date.strftime('%Y-%m-%dT%H:%M:%S%z')}",
        "--env",
        f"PSYOPSOS_BUILD_GIT_REVISION={buildinfo.revision}",
        "--env",
        f"PSYOPSOS_BUILD_GIT_DIRTY={str(buildinfo.dirty)}",
        dockertag,
    ]
    mkimage_cmd = [
        "./mkimage.sh",
        "--tag",
        alpinetag,
        "--outdir",
        "/home/build/iso",
        "--arch",
        architecture,
        "--repository",
        "http://mirrors.edge.kernel.org/alpine/v3.16/main",
        "--repository",
        "http://mirrors.edge.kernel.org/alpine/v3.16/community",
        "--workdir",
        "/home/build/workdir",
        "--profile",
        mkimage_profile,
    ]
    full_cmd = " ".join(docker_cmd + mkimage_cmd)
    print(f"Running docker with: {full_cmd}")
    ctx.run(full_cmd)
    ctx.run(f"ls -alFh {isodir}*.iso")