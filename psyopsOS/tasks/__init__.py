"""PyInvoke tasks file for psyopsOS"""

import datetime
import glob
import os
from pathlib import Path
import pdb
import shlex
import shutil
import string
import subprocess
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
_aportsdir = os.path.expanduser("~/Documents/Repositories/aports")
_workdir = os.path.expanduser("~/Scratch/psyopsOS-build-tmp")
_isodir = os.path.expanduser("~/Downloads/")
_ssh_key_file = "psyops@micahrl.com-62ca1973.rsa"
_psyopsdir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
_psyopsosdir = os.path.join(_psyopsdir, "psyopsOS")
_aportsscriptsdir = os.path.join(_psyopsosdir, "aports-scripts")
_staticdir = os.path.join(_basedir, "static")
_progfigsite_dir = os.path.join(_psyopsdir, "progfiguration_blacksite")
_psyopsOS_base_dir = os.path.join(_basedir, "psyopsOS-base")
_docker_builder_tag_prefix = "psyopsos-builder-"
_docker_builder_dir = os.path.join(_psyopsosdir, "build")

# TODO: Accept an exact version here, and update aports checkout to that version, and rebuild the Docker container if necessary.
# One problem with multiple Alpine base versions is different Python versions,
# which means the progfiguration_blacksite package is being built with different Python version requirements
# dependong on what's on the builder container.
# Might need to split the APK repo by Alpine base version.
_alpine_version = "3.16"

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
def validate_alpine_version(ctx, alpine_version=_alpine_version):
    """Validate that the alpine version matches what we check out in aports and what is in build/Dockerfile."""

    dockerfile = Path(_docker_builder_dir) / "Dockerfile"
    with dockerfile.open("r") as f:
        for line in f.readlines():
            if line.startswith("FROM alpine:"):
                dockerfile_alpine_version = line.split(":")[1]
                break

    cmd = ["git", "name-rev", "--name-only", "HEAD"]
    gitresult = subprocess.run(cmd, cwd=_aportsdir, check=True, capture_output=True)
    aports_alpine_version = ""
    if gitresult.returncode == 0:
        aports_alpine_version = gitresult.stdout.decode("utf-8").strip()

    errors = []

    if alpine_version not in dockerfile_alpine_version:
        errors.append(
            f"Alpine version in Dockerfile ({dockerfile_alpine_version}) does not match alpine_version ({alpine_version})"
        )
    if alpine_version not in aports_alpine_version:
        errors.append(
            f"Alpine version in aports ({aports_alpine_version}) does not match alpine_version ({alpine_version})"
        )

    if errors:
        raise Exception("Alpine version mismatch: " + "\n".join(errors))
    print(
        f"Validated that the Dockerfile and the aports checkout are both Alpine v{alpine_version}"
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
def build_docker_container(ctx, rebuild=False, alpine_version=_alpine_version):
    """Build the docker container that builds the ISO image and Alpine packages"""
    cmd = ["docker", "build", "--progress=plain"]
    if rebuild:
        cmd += ["--no-cache"]
    cmd += ["--tag", _docker_builder_tag_prefix + alpine_version, _docker_builder_dir]
    subprocess.run(cmd, check=True)


class AlpineDockerBuilder:
    """A context manager for building Alpine packages and ISO images in a Docker container

    It saves the psyopsOS build key from 1Password to a temp directory so that you can use it to sign packages.
    It has property `tempdir_sshkey` that you can pass to the Docker container to use the key.
    """

    # We create a Docker volume for the workdir - it's not a bind mount because Docker volumes are faster.
    # Use this for its name.
    workdir_volname = "psyopsos-build-workdir"

    def __init__(
        self,
        # The path to the aports checkout directory
        aports_checkout_dir,
        # The path to the directory containing the aports scripts overlay files
        aports_scripts_overlay_dir,
        # Persistent path Use the previously defined docker volume for temporary files etc when building the image.
        # Saving this between runs makes rebuilds much faster.
        workdir,
        # The place to put the ISO image when its done
        isodir,
        # The SSH key to use for signing packages
        ssh_key_file,
        # The Alpine version to use
        alpine_version,
    ) -> None:
        self.aports_checkout_dir = aports_checkout_dir
        self.aports_scripts_overlay_dir = aports_scripts_overlay_dir
        self.workdir = workdir
        self.isodir = isodir
        self.ssh_key_file = ssh_key_file
        self.in_container_ssh_key_path = f"/home/build/.abuild/{ssh_key_file}"
        self.alpine_version = alpine_version

    def __enter__(self):

        os.umask(0o022)
        buildinfo = self.mkimage_buildinfo()
        build_docker_container(
            invoke.context.Context(), alpine_version=self.alpine_version
        )

        # We use a docker local volume for the workdir
        # This would not be necessary on Linux, but
        # on Docker Desktop for Mac (and probably also on Windows),
        # permissions will get fucked up if you try to use a volume on the host.
        inspected = subprocess.run(
            f"docker volume inspect {self.workdir_volname}", shell=True
        )
        if inspected.returncode != 0:
            subprocess.run(f"docker volume create {self.workdir_volname}", shell=True)

        self.mkimage_clean(False, self.workdir)

        self.tempdir = Path(tempfile.mkdtemp())
        tempdir_sshkey = self.tempdir / "sshkey"
        subprocess.run(
            f"op read op://Personal/psyopsOS_abuild_ssh_key/notesPlain --out-file {tempdir_sshkey.as_posix()}",
            shell=True,
            check=True,
        )

        self.docker_cmd = [
            "docker",
            "run",
            "--rm",
            # Give us full access to the psyops dir
            # Mounting this allows the build to access the psyopsOS/os-overlay/ and the public APK packages directory for mkimage.
            # Also gives us access to progfiguration stuff.
            "--volume",
            f"{_psyopsdir}:/home/build/psyops",
            # I have somehow made it so I can't build psyopsOS-base package without this,
            # but I couldn't tell u why. :(
            # TODO: fucking fix this
            "--volume",
            f"{_psyopsdir}:/psyops",
            # You must mount the aports scripts
            # (And don't forget to update them)
            "--volume",
            f"{self.aports_checkout_dir}:/home/build/aports",
            # genapkovl-psyopsOS.sh partially sets up the filesystem of the iso live OS
            "--volume",
            f"{self.aports_scripts_overlay_dir}/genapkovl-psyopsOS.sh:/home/build/aports/scripts/genapkovl-psyopsOS.sh",
            # mkimage.psyopsOS.sh defines the profile that we pass to mkimage.sh
            "--volume",
            f"{self.aports_scripts_overlay_dir}/mkimg.psyopsOS.sh:/home/build/aports/scripts/mkimg.psyopsOS.sh",
            # Use the previously defined docker volume for temporary files etc when building the image.
            # Saving this between runs makes rebuilds much faster.
            "--volume",
            f"{self.workdir_volname}:/home/build/workdir",
            # This is where the iso will be copied after it is built
            "--volume",
            f"{self.isodir}:/home/build/iso",
            # Mount my SSH keys into the container
            "--volume",
            f"{tempdir_sshkey.as_posix()}:{self.in_container_ssh_key_path}:ro",
            "--volume",
            f"{_psyopsdir}/psyopsOS/build/psyops@micahrl.com-62ca1973.rsa.pub:{self.in_container_ssh_key_path}.pub:ro",
            "--env",
            # Environment variables that mkimage.sh (or one of the scripts it calls) uses
            f"PSYOPSOS_BUILD_DATE_ISO8601={buildinfo.date.strftime('%Y-%m-%dT%H:%M:%S%z')}",
            "--env",
            f"PSYOPSOS_BUILD_GIT_REVISION={buildinfo.revision}",
            "--env",
            f"PSYOPSOS_BUILD_GIT_DIRTY={str(buildinfo.dirty)}",
            _docker_builder_tag_prefix + self.alpine_version,
        ]

        return self

    def __exit__(self, exc_type, exc_value, traceback):
        shutil.rmtree(self.tempdir)

    def mkimage_buildinfo(self):
        build_date = datetime.datetime.now()
        revision_result = subprocess.run(
            "git rev-parse HEAD", shell=True, capture_output=True
        )
        build_git_revision = revision_result.stdout.decode("utf-8").strip()
        build_git_dirty = subprocess.run("git diff --quiet", shell=True).returncode != 0
        return MkimageBuildInfo(build_date, build_git_revision, build_git_dirty)

    def mkimage_clean(self, indocker, workdir):
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
            subprocess.run(f"rm -rf '{d}'", shell=True, check=True)


@invoke.task
def progfigsite_abuild_docker(
    ctx,
    aportsdir=os.path.expanduser("~/Documents/Repositories/aports"),
    workdir=os.path.expanduser("~/Scratch/psyopsOS-build-tmp"),
    isodir=os.path.expanduser("~/Downloads/"),
    ssh_key_file="psyops@micahrl.com-62ca1973.rsa",
    alpine_version=_alpine_version,
):
    """Build the progfiguration psyops blacksite Python package as an Alpine package. Use the mkimage docker container."""

    with AlpineDockerBuilder(
        aportsdir, _aportsscriptsdir, workdir, isodir, ssh_key_file, alpine_version
    ) as builder:

        in_container_build_cmd = [
            "export PATH=$PATH:$HOME/.local/bin",
            "cd /home/build/psyops/progfiguration_blacksite",
            "pip install -e .[development]",
            # TODO: remove this once we have a new enough setuptools in the container
            # Ran into this problem: <https://stackoverflow.com/questions/74941714/importerror-cannot-import-name-legacyversion-from-packaging-version>
            # I'm using an older Alpine container, 3.16 at the time of this writing, because psyopsOS is still that old.
            # When we can upgrade, we'll just use the setuptools in apk.
            "pip install -U setuptools",
            f"echo 'PACKAGER_PRIVKEY=\"{builder.in_container_ssh_key_path}\"' > /home/build/.abuild/abuild.conf",
            "ls -alF /home/build/.abuild",
            f"progfiguration-blacksite-buildapk --apks-index-path /home/build/psyops/psyopsOS/public/apk",
            "ls -larth /home/build/psyops/psyopsOS/public/apk/psyopsOS/x86_64/",
        ]

        full_cmd = builder.docker_cmd + [
            "sh",
            "-c",
            shlex.quote(" && ".join(in_container_build_cmd)),
        ]

        print("Running Docker...")
        print(" ".join(full_cmd))

        ctx.run(" ".join(full_cmd))


@invoke.task
def psyopsOS_base_abuild_docker(ctx, alpine_version=_alpine_version):
    """Build the psyopsOS-base Python package as an Alpine package. Use the mkimage docker container.

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
        with AlpineDockerBuilder(
            aports_checkout_dir=_aportsdir,
            aports_scripts_overlay_dir=_aportsscriptsdir,
            workdir=_workdir,
            isodir=_isodir,
            ssh_key_file=_ssh_key_file,
            alpine_version=alpine_version,
        ) as builder:

            in_container_build_cmd = [
                "set -x",
                "export PATH=$PATH:$HOME/.local/bin",
                "cd /home/build/psyops/psyopsOS/psyopsOS-base",
                # grub-efi package is broken in Docker.
                # If we don't remove it we get a failure like this trying to run abuild:
                #     >>> psyopsOS-base: Analyzing dependencies...
                #     >>> ERROR: psyopsOS-base: builddeps failed
                #     >>> psyopsOS-base: Uninstalling dependencies...
                #     ERROR: No such package: .makedepends-psyopsOS-base
                "sudo apk update",
                "sudo apk del grub-efi",
                "sudo apk fix",
                #
                f"echo 'PACKAGER_PRIVKEY=\"{builder.in_container_ssh_key_path}\"' > /home/build/.abuild/abuild.conf",
                "ls -alF /home/build/.abuild",
                f"abuild checksum",
                build_cmd,
                "ls -larth /home/build/psyops/psyopsOS/public/apk/psyopsOS/x86_64/",
            ]

            full_cmd = builder.docker_cmd + [
                "sh",
                "-c",
                shlex.quote(" && ".join(in_container_build_cmd)),
            ]

            print("Running Docker...")
            print(" ".join(full_cmd))

            ctx.run(" ".join(full_cmd))

    finally:
        try:
            os.unlink(apkbuild_path)
        except:
            raise Exception(
                f"When trying to remove ABKBUILD, got an exception. Manually remove: {apkbuild_path}"
            )


@invoke.task
def psyopsOS_base_abuild_localhost(ctx, clean=False):
    """Build the psyopsOS-base Python package as an Alpine package. Must be run from the psyops container.

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
            ctx.run("ls -alF")
            if clean:
                print("Running abuild clean...")
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


@invoke.task
def mkimage(
    ctx,
    osflavor="pc",
    alpinetag="psyopsos-boot",
    aportsdir=_aportsdir,
    workdir=_workdir,
    isodir=_isodir,
    ssh_key_file=_ssh_key_file,
    alpine_version=_alpine_version,
    whatif=False,
):
    """Run Alpine mkimage.sh inside a Docker container. The alpine_version must match the version of the host's aports checkout and the version in build/Dockerfile. (Note that this is different from the psyops container at ../docker/Dockerfile.)"""

    validate_alpine_version(ctx, alpine_version)

    # Make sure we have an up-to-date Docker builder
    build_docker_container(ctx, alpine_version)

    # Build the APKs that are also included in the ISO
    # Building them here makes sure that they are up-to-date
    # and especially that they're built on the right Python version
    # (Different Alpine versions use different Python versions,
    # and if the latest APK doesn't match what's installed on the new ISO,
    # it will fail.)
    progfigsite_abuild_docker(ctx, alpine_version)
    psyopsOS_base_abuild_docker(ctx, alpine_version)

    with AlpineDockerBuilder(
        aportsdir, _aportsscriptsdir, workdir, isodir, ssh_key_file, alpine_version
    ) as builder:
        mkimage_profile, architecture = osflavorinfo(osflavor)
        in_container_mkimage_cmd = [
            f"echo 'PACKAGER_PRIVKEY=\"{builder.in_container_ssh_key_path}\"' > /home/build/.abuild/abuild.conf",
            "ls -alF /home/build/.abuild",
            "ls -alF /home/build/aports/scripts",
            # This package doesn't work in Docker and leaves apk in a broken state. (apk fix doesn't fix it.)
            #     It shows a message like:
            #     (2/2) Installing grub-efi (2.06-r2)
            #     Executing busybox-1.35.0-r17.trigger
            #     Executing grub-2.06-r2.trigger
            #     /usr/sbin/grub-probe: error: failed to get canonical path of `overlay'.
            #     ERROR: grub-2.06-r2.trigger: script exited with error 1
            # However, it is required to build a bootable ISO.
            "sudo apk add grub-efi",
            " ".join(
                [
                    "./mkimage.sh",
                    "--tag",
                    alpinetag,
                    "--outdir",
                    "/home/build/iso",
                    "--arch",
                    architecture,
                    "--repository",
                    f"http://dl-cdn.alpinelinux.org/alpine/v{alpine_version}/main",
                    "--repository",
                    f"http://dl-cdn.alpinelinux.org/alpine/v{alpine_version}/community",
                    "--repository",
                    "/home/build/psyops/psyopsOS/public/apk/psyopsOS",
                    "--repository",
                    "https://psyops.micahrl.com/apk/psyopsOS",
                    "--workdir",
                    "/home/build/workdir",
                    "--profile",
                    mkimage_profile,
                ]
            ),
        ]
        full_cmd = builder.docker_cmd + [
            "sh",
            "-c",
            shlex.quote(" && ".join(in_container_mkimage_cmd)),
        ]
        print(f"========")
        print(
            f"Run mkimage inside docker. This will happen next if you didn't pass --whatif:"
        )
        print(" \\\n  ".join(full_cmd))
        print(f"========")

        if not whatif:
            ctx.run(" ".join(full_cmd))

            # name is: alpine-psyopsOS-ALPINETAG-ARCH.iso
            # note sure where the 'payopsOS' comes from, maybe this directory name?
            ctx.run(
                f"mv '{isodir}/alpine-psyopsOS-{alpinetag}-{architecture}.iso' '{isodir}/alpine-psyopsOS-{alpinetag}-{architecture}-{alpine_version}.iso'"
            )

    ctx.run(f"ls -alFh {isodir}*.iso")
