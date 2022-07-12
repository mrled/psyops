"""PyInvoke tasks file for psyopsOS"""

import datetime
import glob
import json
import os
import pdb
import re
import shutil
import string
import subprocess
import sys
import textwrap
import traceback
from typing import Any, Dict, NamedTuple, Optional

import boto3
import invoke


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
psyopsos_key = os.path.join(basedir, "minisign.seckey")
progfiguration_dir = os.path.join(basedir, "progfiguration")

# Output configuration
sitedir = os.path.join(basedir, "public")
site_psyopsos_dir = os.path.join(sitedir, "psyopsOS")
site_psyopsos_dir_nodes = os.path.join(site_psyopsos_dir, "nodes")
site_psyopsos_dir_tags = os.path.join(site_psyopsos_dir, "tags")
site_psyopsos_dir_global = os.path.join(site_psyopsos_dir, "global.json")
site_bucket = "com-micahrl-psyops-http-bucket"


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
def deploy(ctx):
    """Deploy the site dir to S3"""
    s3_upload_directory(sitedir, site_bucket)


@invoke.task
def progfiguration_abuild(ctx):
    """Build the progfiguration Python package as an Alpine package. Must be run from the psyops container.

    Sign with the psyopsOS key.
    """
    versionfile = os.path.join(progfiguration_dir, "progfiguration", "build_version.py")
    version = datetime.datetime.now().strftime("%Y%m%d.%H%M%S.0")

    apkbuild_template = string.Template(textwrap.dedent("""\
        pkgname="progfiguration"
        _pyname="progfiguration"
        pkgver="$version"
        pkgrel=0
        pkgdesc="Programmatic configuration of hosts"
        options="!check" # No tests, yolo
        url="https://github.com/mrled/psyops"
        arch="noarch"
        license="WTFPL"
        depends="python3 py3-requests py3-tz py3-yaml"
        makedepends="py3-build py3-setuptools py3-wheel"

        build() {
            python3 -m build --no-isolation --wheel
        }

        package() {
            python3 -m installer -d "$$pkgdir" dist/$$_pyname-$$pkgver-py3-none-any.whl
        }
        """)
    )
    apkbuild_contents = apkbuild_template.substitute(version=version)
    apkbuild_path = os.path.join(progfiguration_dir, "APKBUILD")

    # Place the apk repo inside the public dir
    # This means that 'invoke deploy' will copy it
    build_cmd = "abuild -P /psyops/psyopsOS/public/apk -D psyopsOS"

    try:
        with open(versionfile, 'w') as vfd:
            vfd.write(f"VERSION = '{version}'\n")
        with open(apkbuild_path, 'w') as afd:
            afd.write(apkbuild_contents)
        print("Running build in progfiguration directory...")
        with ctx.cd(progfiguration_dir):
            ctx.run(build_cmd)
    finally:
        failed = False
        try:
            os.unlink(versionfile)
        except:
            # raise Exception(f"When trying to remove version file at {versionfile}, got exception {rmexc}. ***REMOVE {versionfile} MANUALLY***.")
            failed = True
        try:
            os.unlink(apkbuild_path)
        except:
            failed = True
        if failed:
            raise Exception(f"When trying to remove version file and/or ABKBUILD, got an exception. Manually remove these two files, if they exist: {versionfile}, {apkbuild_path}")


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


# @invoke.task
# def mkimage_local(
#     ctx,
#     osflavor,
#     alpinetag="0x001",
#     aportsdir=os.path.expanduser("~/aports"),
#     workdir=os.path.expanduser("~/psyopsOS-build-tmp"),
#     isodir=os.path.expanduser("~/isos"),
# ):
#     """Run mkimage.sh directly. Must be run from an Alpine system.

#     This is not used as often as the regular 'mkimage' target (which uses docker), and may be out of date!
#     """

#     mkimage_profile, architecture = osflavorinfo(osflavor)

#     os.umask(0o022)

#     psyopsdir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
#     psyopsosdir = os.path.join(psyopsdir, "psyopsOS")
#     aportsscriptsdir = os.path.join(psyopsosdir, "aports-scripts")

#     buildinfo = mkimage_buildinfo(ctx)

#     mkimage_clean(ctx, indocker=True, workdir=workdir)

#     for directory in [workdir, isodir]:
#         os.makedirs(directory, exist_ok=True)
#     for script in ["genapkovl-psyopsOS.sh", "mkimg.psyopsOS.sh", "mkimg.zzz-overrides.sh"]:
#         shutil.copy(f"{aportsscriptsdir}/{script}", f"{aportsdir}/scripts/{script}")

#     os.environ["PSYOPSOS_OVERLAY"] = f"{psyopsosdir}/os-overlay"
#     os.environ["PSYOPSOS_BUILD_DATE_ISO8601"] = buildinfo.date.strftime('%Y-%m-%dT%H:%M:%S%z')
#     os.environ["PSYOPSOS_BUILD_GIT_REVISION"] = buildinfo.revision
#     os.environ["PSYOPSOS_BUILD_GIT_DIRTY"] = str(buildinfo.dirty)

#     mkimage_cmd = [
#         "./mkimage.sh",
#         "--tag",
#         alpinetag,
#         "--outdir",
#         "/home/build/iso",
#         "--arch",
#         architecture,
#         "--repository",
#         "http://mirrors.edge.kernel.org/alpine/v3.16/main",
#         "--repository",
#         "http://mirrors.edge.kernel.org/alpine/v3.16/community",
#         "--workdir",
#         "/home/build/workdir",
#         "--profile",
#         mkimage_profile,
#     ]
#     full_cmd = " ".join(mkimage_cmd)
#     print(f"Running {full_cmd}")
#     with ctx.cd(f"{aportsdir}/scripts"):
#         ctx.run(full_cmd)
#     ctx.run(f"ls -alFh {isodir}*.iso")


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
    """Build the docker image in build/Dockerfile and use it to run mkimage.sh to build a new Alpine ISO. Works from any host with Docker (doesn't require an Alpine host OS)."""

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
        # Mounting this allows the build to access the psyopsOS/os-overlay/ and the public APK packages directory.
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
        "http://dl-cdn.alpinelinux.org/alpine/v3.16/main",
        "--repository",
        "http://dl-cdn.alpinelinux.org/alpine/v3.16/community",
        "--repository",
        "/home/build/psyops/psyopsOS/public/apk/psyopsOS",
        "--repository",
        "https://com-micahrl-psyops-http-bucket.s3.us-east-2.amazonaws.com/apk/psyopsOS",
        "--workdir",
        "/home/build/workdir",
        "--profile",
        mkimage_profile,
    ]
    full_cmd = " ".join(docker_cmd + mkimage_cmd)
    print(f"Running docker with: {full_cmd}")
    ctx.run(full_cmd)
    ctx.run(f"ls -alFh {isodir}*.iso")
