"""PyInvoke tasks file for psyopsOS"""

import datetime
import glob
import os
from pathlib import Path
import pdb
import shlex
import shutil
import string
import sys
import tempfile
import time
import traceback
from typing import NamedTuple

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


_basedir = os.path.abspath(os.path.dirname(__file__))

_docker_builder_volname_workdir = "psyopsos-build-workdir"

# Input configuration
_psyopsdir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
_psyopsosdir = os.path.join(_psyopsdir, "psyopsOS")
_aportsscriptsdir = os.path.join(_psyopsosdir, "aports-scripts")
_staticdir = os.path.join(_basedir, "static")
_progfigsite_dir = os.path.join(_psyopsdir, "progfiguration_blacksite")
_psyopsOS_base_dir = os.path.join(_basedir, "psyopsOS-base")
_docker_builder_tag = "psyopsos-builder"
_docker_builder_dir = os.path.join(_psyopsosdir, "build")

# Output configuration
_site_public_dir = os.path.join(_basedir, "public")
_site_bucket = "com-micahrl-psyops-http-bucket"

# When inside the psyops container, the path to the public/ directory's apk repository
_incontainer_apks_path = "/psyops/psyopsOS/public/apk"


def s3_upload_directory(directory, bucketname):
    """Upload a directory to S3 using AWS creds from ~/.aws

    TODO: keep track of all uploaded files, then at the end list all files in the bucket and delete any we didn't upload
    """
    import boto3

    s3client = boto3.client("s3")
    for root, _, files in os.walk(directory):
        for filename in files:
            local_filepath = os.path.join(root, filename)
            relative_filepath = os.path.relpath(local_filepath, directory)
            print(f"Uploading {local_filepath}...")
            extra_args = {}
            # If you don't do this, browsing to these files will download them without displaying them.
            # We mostly just care about this for the index/error html files.
            if filename.endswith(".html"):
                extra_args["ContentType"] = "text/html"
            s3client.upload_file(
                local_filepath, bucketname, relative_filepath, ExtraArgs=extra_args
            )


@invoke.task
def clean(ctx):
    """Clean the build. Note does not clear the abuild cache; pass --clean to an -abuild task to clean it before building."""
    try:
        shutil.rmtree(_site_public_dir)
    except FileNotFoundError:
        pass


@invoke.task
def cleandockervol(
    ctx,
    volname_workdir=_docker_builder_volname_workdir,
):
    """Remove the Docker volume used for the mkimage.sh working directory"""
    ctx.run(f"docker volume rm {volname_workdir}")


@invoke.task
def deploy(ctx):
    """Deploy the site dir to S3. First copies files from the static dir to the deploy dir."""
    shutil.copytree(_staticdir, _site_public_dir, dirs_exist_ok=True)
    s3_upload_directory(_site_public_dir, _site_bucket)


@invoke.task
def progfigsite_abuild_localhost(ctx, clean=False, skipinstall=False):
    """Build the progfiguration psyops blacksite Python package as an Alpine package. Must be run from the psyops container.

    Args:
        clean: If True, run 'abuild clean' before building.
        skipinstall: If True, skip installing the package before building.
            Installing the package is required because we build with the `progfiguration-blacksite-buildapk` command.
            Once it's been installed, though, there's no reason to waste time running pip install again.

    Sign with the psyopsOS key.
    """

    with ctx.cd(_progfigsite_dir):
        if not skipinstall:
            ctx.run("pip install -e .")
        cmd = "progfiguration-blacksite-buildapk"
        if clean:
            cmd += " --clean"
        ctx.run(cmd)


@invoke.task
def progfigsite_abuild_docker(ctx):
    """Build the progfiguration psyops blacksite Python package as an Alpine package. Use the mkimage docker container.

    This uses a dedicated Docker container to build the package.

    This decouples the PSYOPS container Alpine version from the psyopsOS Alpine version.
    Some hosts might be running a pretty old version of Alpine,
    and we want to be able to build packages that work for all versions.

    This uses the same Docker container as the psyopsOS build.

    It looks for the abuild private SSH key in the 1Password Personal vault,
    and uses the public key in psyopsOS/build/.
    """

    ssh_key_file = "psyops@micahrl.com-62ca1973.rsa"
    in_container_ssh_key_path = f"/home/build/.abuild/{ssh_key_file}"

    in_container_build_cmd = [
        "export PATH=$PATH:$HOME/.local/bin",
        "cd /home/build/psyops/progfiguration_blacksite",
        "pip install -e .[development]",
        # TODO: remove this once we have a new enough setuptools in the container
        # Ran into this problem: <https://stackoverflow.com/questions/74941714/importerror-cannot-import-name-legacyversion-from-packaging-version>
        # I'm using an older Alpine container, 3.16 at the time of this writing, because psyopsOS is still that old.
        # When we can upgrade, we'll just use the setuptools in apk.
        "pip install -U setuptools",
        f"echo 'PACKAGER_PRIVKEY=\"{in_container_ssh_key_path}\"' > /home/build/.abuild/abuild.conf",
        "ls -alF /home/build/.abuild",
        f"progfiguration-blacksite-buildapk --apks-index-path /home/build/psyops/psyopsOS/public/apk",
        "ls -larth /home/build/psyops/psyopsOS/public/apk/psyopsOS/x86_64/",
    ]

    with tempfile.TemporaryDirectory() as tmpdir_s:
        tempdir = Path(tmpdir_s)

        # We need the APK SSH key from 1password.
        # Place it in the temp directory so it'll get cleaned up when we're done.
        tempdir_sshkey = tempdir / "sshkey"
        ctx.run(
            f"op read op://Personal/psyopsOS_abuild_ssh_key/notesPlain --out-file {tempdir_sshkey.as_posix()}"
        )

        docker_cmd = [
            "docker",
            "run",
            "--rm",
            "--volume",
            f"{_psyopsdir}:/home/build/psyops",
            "--volume",
            f"{tempdir_sshkey.as_posix()}:{in_container_ssh_key_path}:ro",
            "--volume",
            f"{_psyopsdir}/psyopsOS/build/psyops@micahrl.com-62ca1973.rsa.pub:{in_container_ssh_key_path}.pub:ro",
            _docker_builder_tag,
            "sh",
            "-c",
            shlex.quote(" && ".join(in_container_build_cmd)),
        ]

        print("Running Docker...")
        print(" ".join(docker_cmd))

        ctx.run(" ".join(docker_cmd))


@invoke.task
def psyopsOS_base_abuild(ctx, clean=False):
    """Build the psyopsOS-base Python package as an Alpine package. Must be run from the psyops container. TODO: Update to work with the build container like progfiguration_blacksite does.

    Sign with the psyopsOS key.
    """
    epochsecs = int(time.time())
    version = f"1.0.{epochsecs}"

    with open(f"{_psyopsOS_base_dir}/APKBUILD.template") as fp:
        apkbuild_template = string.Template(fp.read())
    apkbuild_contents = apkbuild_template.substitute(version=version)
    apkbuild_path = os.path.join(_psyopsOS_base_dir, "APKBUILD")

    # Place the apk repo inside the public dir
    # This means that 'invoke deploy' will copy it
    build_cmd = f"abuild -r -P {_incontainer_apks_path} -D psyopsOS"

    try:
        with open(apkbuild_path, "w") as afd:
            afd.write(apkbuild_contents)
        print("Running build in progfiguration directory...")
        with ctx.cd(_psyopsOS_base_dir):
            if clean:
                print("Running abuild clean...")
                with ctx.cd(_psyopsOS_base_dir):
                    ctx.run("abuild clean")
            ctx.run("abuild checksum")
            ctx.run(build_cmd)
    finally:
        try:
            os.unlink(apkbuild_path)
        except:
            raise Exception(
                f"When trying to remove ABKBUILD, got an exception. Manually remove: {apkbuild_path}"
            )


def osflavorinfo(flavorname):
    """Given the name of an OS flavor, return its Alpine profile and architecture

    WARNING: the rpi flavor doesn't actually work yet.
    It must be built on an aarch64 host, which I haven't bothered to configure.
    """
    osflavors = {
        "pc": ["psyopsOS", "x86_64"],
        "rpi": ["psyopsOS_rpi", "aarch64"],
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
#
#     This is not used as often as the regular 'mkimage' target (which uses docker), and may be out of date!
#     """
#
#     mkimage_profile, architecture = osflavorinfo(osflavor)
#     os.umask(0o022)
#     buildinfo = mkimage_buildinfo(ctx)
#
#     mkimage_clean(ctx, indocker=True, workdir=workdir)
#
#     for directory in [workdir, isodir]:
#         os.makedirs(directory, exist_ok=True)
#     for script in ["genapkovl-psyopsOS.sh", "mkimg.psyopsOS.sh", "mkimg.zzz-overrides.sh"]:
#         shutil.copy(f"{aportsscriptsdir}/{script}", f"{aportsdir}/scripts/{script}")
#
#     os.environ["PSYOPSOS_OVERLAY"] = f"{psyopsosdir}/os-overlay"
#     os.environ["PSYOPSOS_BUILD_DATE_ISO8601"] = buildinfo.date.strftime('%Y-%m-%dT%H:%M:%S%z')
#     os.environ["PSYOPSOS_BUILD_GIT_REVISION"] = buildinfo.revision
#     os.environ["PSYOPSOS_BUILD_GIT_DIRTY"] = str(buildinfo.dirty)
#
#     mkimage_cmd = get_mkimage_cmd(osflavor, alpinetag)
#     full_cmd = " ".join(mkimage_cmd)
#     print(f"Running {full_cmd}")
#     with ctx.cd(f"{aportsdir}/scripts"):
#         ctx.run(full_cmd)
#     ctx.run(f"ls -alFh {isodir}*.iso")


@invoke.task
def build_docker_container(ctx, rebuild=False):
    """Build the docker container that builds the ISO image"""
    cmd = ["docker", "build"]
    if rebuild:
        cmd += ["--no-cache"]
    cmd += ["--tag", shlex.quote(_docker_builder_tag), shlex.quote(_docker_builder_dir)]
    ctx.run(" ".join(cmd))


def get_docker_cmd_for_mkimage(
    buildinfo: MkimageBuildInfo,
    aportsdir,
    isodir,
    volname_workdir,
    shell_or_prefix,
):
    """Return the docker command to run mkimage.sh

    This is a helper function for the mkimage task.

    :param buildinfo: The buildinfo object returned by mkimage_buildinfo()
    :param aportsdir: The path to the aports directory
    :param isodir: The path to the directory where the ISO will be written
    :param volname_workdir: The name of the volume that will be mounted to /home/build
    :param shell_or_prefix: Either "shell" or "prefix"; 'shell' is a string that can be presented to the user to run in their terminal and get an interactive shell in the container, while 'prefix' is a string that can be prepended to some other command to run it in the container.
    :return: The docker command to run mkimage.sh
    """
    shell = False
    if shell_or_prefix == "shell":
        shell = True
    elif shell_or_prefix == "prefix":
        pass
    else:
        raise Exception("shell_or_prefix argument must be 'shell' or 'prefix'")
    docker_cmd = [
        "docker",
        "run",
        "--rm",
    ]
    if shell:
        docker_cmd += ["--interactive", "--tty"]
    docker_cmd += [
        # You must mount the aports scripts
        # (And don't forget to update them)
        "--volume",
        f"{aportsdir}:/home/build/aports",
        # genapkovl-psyopsOS.sh partially sets up the filesystem of the iso live OS
        "--volume",
        f"{_aportsscriptsdir}/genapkovl-psyopsOS.sh:/home/build/aports/scripts/genapkovl-psyopsOS.sh",
        # mkimage.psyopsOS.sh defines the profile that we pass to mkimage.sh
        "--volume",
        f"{_aportsscriptsdir}/mkimg.psyopsOS.sh:/home/build/aports/scripts/mkimg.psyopsOS.sh",
        # mkimage.zzz-overrides.sh will let us customize any mkimage function by overriding it
        "--volume",
        f"{_aportsscriptsdir}/mkimg.zzz-overrides.sh:/home/build/aports/scripts/mkimg.zzz-overrides.sh",
        # Use the previously defined docker volume for temporary files etc when building the image.
        # Saving this between runs makes rebuilds much faster.
        "--volume",
        f"{volname_workdir}:/home/build/workdir",
        # This is where the iso will be copied after it is built
        "--volume",
        f"{isodir}:/home/build/iso",
        # Mounting this allows the build to access the psyopsOS/os-overlay/ and the public APK packages directory.
        "--volume",
        f"{_psyopsdir}:/home/build/psyops",
        # Environment variables that mkimage.sh (or one of the scripts it calls) uses
        "--env",
        f"PSYOPSOS_BUILD_DATE_ISO8601={buildinfo.date.strftime('%Y-%m-%dT%H:%M:%S%z')}",
        "--env",
        f"PSYOPSOS_BUILD_GIT_REVISION={buildinfo.revision}",
        "--env",
        f"PSYOPSOS_BUILD_GIT_DIRTY={str(buildinfo.dirty)}",
        _docker_builder_tag,
    ]
    if shell:
        docker_cmd += ["/bin/bash"]
    return docker_cmd


def get_mkimage_cmd(
    osflavor="pc",
    alpinetag="0x001",
):
    mkimage_profile, architecture = osflavorinfo(osflavor)
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
        "https://psyops.micahrl.com/apk/psyopsOS",
        "--workdir",
        "/home/build/workdir",
        "--profile",
        mkimage_profile,
    ]
    return mkimage_cmd


def prettycmd(cmd):
    """Given a command for ctx.run(), return a pretty version with arguments on separate lines"""
    return " \\\n  ".join(cmd)


@invoke.task
def mkimage(
    ctx,
    osflavor="pc",
    alpinetag="0x001",
    aportsdir=os.path.expanduser("~/Documents/Repositories/aports"),
    workdir=os.path.expanduser("~/Scratch/psyopsOS-build-tmp"),
    isodir=os.path.expanduser("~/Downloads/"),
    volname_workdir=_docker_builder_volname_workdir,
    whatif=False,
):
    """TODO: THIS NEEDS TO BE UPDATED SINCE I CHANGED THE DOCKERFILE RECENTLY. SEE BELOW. Build the docker image in build/Dockerfile and use it to run mkimage.sh to build a new Alpine ISO. Works from any host with Docker (doesn't require an Alpine host OS), but does require an x86_64 host.

    TODO: I recently changed the Dockerfile to work for building progfiguration_blacksite. This means I no longer have to build it in the psyops container, can use this dedicated build container instead. Make sure this mkimgae still works.
    """

    os.umask(0o022)
    buildinfo = mkimage_buildinfo(ctx)
    mkimage_clean(ctx, indocker=True, workdir=workdir)
    build_docker_container(ctx)

    # We use a docker local volume for the workdir
    # This would not be necessary on Linux, but
    # on Docker Desktop for Mac (and probably also on Windows),
    # permissions will get fucked up if you try to use a volume on the host.
    try:
        ctx.run(f"docker volume inspect {volname_workdir}")
    except invoke.Failure:
        ctx.run(f"docker volume create {volname_workdir}")

    docker_cmd_with_shell = get_docker_cmd_for_mkimage(
        buildinfo,
        aportsdir,
        isodir,
        volname_workdir,
        "shell",
    )
    docker_cmd_prefix = get_docker_cmd_for_mkimage(
        buildinfo,
        aportsdir,
        isodir,
        volname_workdir,
        "prefix",
    )
    mkimage_cmd = get_mkimage_cmd(osflavor, alpinetag)
    full_cmd = docker_cmd_prefix + mkimage_cmd
    print(f"========")
    print(
        f"Run mkimage inside docker. This will happen next if you didn't pass --whatif:"
    )
    print(prettycmd(full_cmd))
    print(f"========")
    print(
        f"Run the Docker container and get a shell. This can be helpful for debugging"
    )
    print(prettycmd(docker_cmd_with_shell))
    print(f"========")
    print(f"From a shell in the docker image, you can run a command like this:")
    print(prettycmd(mkimage_cmd))
    print(f"========")
    if whatif:
        return
    ctx.run(" ".join(full_cmd))
    ctx.run(f"ls -alFh {isodir}*.iso")
