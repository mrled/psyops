"""PyInvoke tasks file for psyopsOS"""

import os
from pathlib import Path
import shlex
import shutil
import string
import subprocess
import sys
import time

import invoke

from tasks.alpine_docker_builder import AlpineDockerBuilder, build_docker_container_impl
from tasks.constants import (
    aportsdir,
    alpine_version,
    docker_builder_dir,
    isodir,
    psyopsdir,
    ssh_key_file,
    workdir,
    site_public_dir,
    docker_builder_volname_workdir,
    docker_builder_tag_prefix,
    staticdir,
    site_bucket,
    incontainer_apks_path,
    mkimage_profile,
    architecture,
    psyopsOS_base_dir,
    aportsscriptsdir,
    progfigsite_dir,
    mkimage_profile,
)
from tasks.util import idb_excepthook


sys.excepthook = idb_excepthook


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
def validate_alpine_version(ctx, alpine_version=alpine_version):
    """Validate that the alpine version matches what we check out in aports and what is in build/Dockerfile."""

    dockerfile = Path(docker_builder_dir) / "Dockerfile"
    with dockerfile.open("r") as f:
        for line in f.readlines():
            if line.startswith("FROM alpine:"):
                dockerfile_alpine_version = line.split(":")[1]
                break

    cmd = ["git", "name-rev", "--name-only", "HEAD"]
    gitresult = subprocess.run(cmd, cwd=aportsdir, check=True, capture_output=True)
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
        shutil.rmtree(site_public_dir)
    except FileNotFoundError:
        pass


@invoke.task
def cleandockervol(
    ctx,
    volname_workdir=docker_builder_volname_workdir,
):
    """Remove the Docker volume used for the mkimage.sh working directory"""
    ctx.run(f"docker volume rm {volname_workdir}")


@invoke.task
def deploy(ctx):
    """Deploy the site dir to S3. First copies files from the static dir to the deploy dir."""
    shutil.copytree(staticdir, site_public_dir, dirs_exist_ok=True)
    s3_upload_directory(site_public_dir, site_bucket)


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

    with ctx.cd(progfigsite_dir):
        if not skipinstall:
            ctx.run("pip install -e .")
        cmd = "progfiguration-blacksite-buildapk"
        if clean:
            cmd += " --clean"
        ctx.run(cmd)


@invoke.task
def build_docker_container(ctx, rebuild=False, alpine_version=alpine_version):
    """Build the docker container that builds the ISO image and Alpine packages"""
    build_docker_container_impl(
        docker_builder_tag_prefix + alpine_version, docker_builder_dir, rebuild
    )


@invoke.task
def progfigsite_abuild_docker(
    ctx,
    aportsdir=os.path.expanduser("~/Documents/Repositories/aports"),
    workdir=os.path.expanduser("~/Scratch/psyopsOS-build-tmp"),
    isodir=os.path.expanduser("~/Downloads/"),
    ssh_key_file="psyops@micahrl.com-62ca1973.rsa",
    alpine_version=alpine_version,
):
    """Build the progfiguration psyops blacksite Python package as an Alpine package. Use the mkimage docker container."""

    with AlpineDockerBuilder(
        aportsdir,
        aportsscriptsdir,
        workdir,
        isodir,
        ssh_key_file,
        alpine_version,
        psyopsdir,
        docker_builder_tag_prefix,
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
def psyopsOS_base_abuild_docker(ctx, alpine_version=alpine_version):
    """Build the psyopsOS-base Python package as an Alpine package. Use the mkimage docker container.

    Sign with the psyopsOS key.
    """
    epochsecs = int(time.time())
    version = f"1.0.{epochsecs}"

    with open(f"{psyopsOS_base_dir}/APKBUILD.template") as fp:
        apkbuild_template = string.Template(fp.read())
    apkbuild_contents = apkbuild_template.substitute(version=version)
    apkbuild_path = os.path.join(psyopsOS_base_dir, "APKBUILD")

    # Place the apk repo inside the public dir
    # This means that 'invoke deploy' will copy it
    build_cmd = f"abuild -r -P {incontainer_apks_path} -D psyopsOS"

    try:
        with open(apkbuild_path, "w") as afd:
            afd.write(apkbuild_contents)
        print("Running build in progfiguration directory...")
        with AlpineDockerBuilder(
            aports_checkout_dir=aportsdir,
            aports_scripts_overlay_dir=aportsscriptsdir,
            workdir=workdir,
            isodir=isodir,
            ssh_key_file=ssh_key_file,
            alpine_version=alpine_version,
            psyopsdir=psyopsdir,
            docker_builder_tag_prefix=docker_builder_tag_prefix,
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

    with open(f"{psyopsOS_base_dir}/APKBUILD.template") as fp:
        apkbuild_template = string.Template(fp.read())
    apkbuild_contents = apkbuild_template.substitute(version=version)
    apkbuild_path = os.path.join(psyopsOS_base_dir, "APKBUILD")

    # Place the apk repo inside the public dir
    # This means that 'invoke deploy' will copy it
    build_cmd = f"abuild -r -P {incontainer_apks_path} -D psyopsOS"

    try:
        with open(apkbuild_path, "w") as afd:
            afd.write(apkbuild_contents)
        print("Running build in progfiguration directory...")
        with ctx.cd(psyopsOS_base_dir):
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


@invoke.task
def mkimage(
    ctx,
    alpinetag="psyopsos-boot",
    aportsdir=aportsdir,
    workdir=workdir,
    isodir=isodir,
    ssh_key_file=ssh_key_file,
    docker_builder_tag_prefix=docker_builder_tag_prefix,
    alpine_version=alpine_version,
    docker_builder_dir=docker_builder_dir,
    mkimage_profile=mkimage_profile,
    architecture=architecture,
    whatif=False,
):
    """Run Alpine mkimage.sh inside a Docker container. The alpine_version must match the version of the host's aports checkout and the version in build/Dockerfile. (Note that this is different from the psyops container at ../docker/Dockerfile.)"""

    validate_alpine_version(ctx, alpine_version)

    # Make sure we have an up-to-date Docker builder
    build_docker_container_impl(
        docker_builder_tag_prefix + alpine_version, docker_builder_dir
    )

    # Build the APKs that are also included in the ISO
    # Building them here makes sure that they are up-to-date
    # and especially that they're built on the right Python version
    # (Different Alpine versions use different Python versions,
    # and if the latest APK doesn't match what's installed on the new ISO,
    # it will fail.)
    progfigsite_abuild_docker(ctx, alpine_version)
    psyopsOS_base_abuild_docker(ctx, alpine_version)

    with AlpineDockerBuilder(
        aportsdir,
        aportsscriptsdir,
        workdir,
        isodir,
        ssh_key_file,
        alpine_version,
        psyopsdir,
        docker_builder_tag_prefix,
    ) as builder:
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

            # We move from the name generated by mkimage to a name that includes the Alpine version,
            # e.g. alpine-psyopsOS-psyopsos-boot-x86_64.iso => alpine-psyopsOS-psyopsos-boot-x86_64-3.16.iso
            ctx.run(
                f"mv '{isodir}/alpine-{mkimage_profile}-{alpinetag}-{architecture}.iso' '{isodir}/alpine-{mkimage_profile}-{alpinetag}-{architecture}-{alpine_version}.iso'"
            )

    ctx.run(f"ls -alFh {isodir}*.iso")
