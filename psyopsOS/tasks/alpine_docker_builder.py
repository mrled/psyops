"""The Alpine Docker builder context manager"""

import datetime
import glob
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from tasks.secrets import save_apk_signing_key


def build_docker_container_impl(image_tag: str, docker_builder_dir: str, rebuild=False):
    """Build the docker container that builds the ISO image and Alpine packages"""
    cmd = ["docker", "build", "--progress=plain"]
    if rebuild:
        cmd += ["--no-cache"]
    cmd += ["--tag", image_tag, docker_builder_dir]
    subprocess.run(cmd, check=True)


class AlpineDockerBuilder:
    """A context manager for building Alpine packages and ISO images in a Docker container

    It saves the psyopsOS build key from 1Password to a temp directory so that you can use it to sign packages.
    It has property `tempdir_sshkey` that you can pass to the Docker container to use the key.
    """

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
        # The filename for the SSH key to use for signing packages
        # This is just used internally, and is not the path to the key on the host
        ssh_key_file,
        # The Alpine version to use
        alpine_version,
        # The path to the psyops checkout on the host
        psyopsdir,
        # The Docker image tag prefix (will be suffixed with the Alpine version)
        docker_builder_tag_prefix,
    ) -> None:
        self.aports_checkout_dir = aports_checkout_dir
        self.aports_scripts_overlay_dir = aports_scripts_overlay_dir
        self.workdir = workdir
        self.isodir = isodir
        self.ssh_key_file = ssh_key_file
        self.in_container_ssh_key_path = f"/home/build/.abuild/{ssh_key_file}"
        self.alpine_version = alpine_version
        self.psyopsdir = psyopsdir
        self.docker_builder_tag_prefix = docker_builder_tag_prefix

        # Path to the psyopsOS project within the root psyops repo
        self.psyopsosdir = os.path.join(self.psyopsdir, "psyopsOS")
        # Path to the directory containing the Dockerfile for the Alpine builder
        self.docker_builder_dir = os.path.join(self.psyopsosdir, "build")

    def __enter__(self):

        os.umask(0o022)
        build_docker_container_impl(
            f"{self.docker_builder_tag_prefix}{self.alpine_version}",
            self.docker_builder_dir,
        )

        build_date = datetime.datetime.now()

        revision_result = subprocess.run(
            "git rev-parse HEAD", shell=True, capture_output=True
        )
        build_git_revision = revision_result.stdout.decode("utf-8").strip()

        build_git_dirty = subprocess.run("git diff --quiet", shell=True).returncode != 0

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

        # Save the SSH private key to the temp dir
        self.tempdir = Path(tempfile.mkdtemp())
        tempdir_sshkey = self.tempdir / "sshkey"
        tempdir_sshpubkey = self.tempdir / "sshpubkey"
        save_apk_signing_key(tempdir_sshkey)
        # Generate a public key from the private key
        pubkey_result = subprocess.run(
            ["ssh-keygen", "-f", tempdir_sshkey.as_posix(), "-y"],
            check=True,
            capture_output=True,
        )
        with tempdir_sshpubkey.open("w") as f:
            f.write(pubkey_result.stdout.decode())

        self.docker_cmd = [
            "docker",
            "run",
            "--rm",
            # Give us full access to the psyops dir
            # Mounting this allows the build to access the psyopsOS/os-overlay/ and the public APK packages directory for mkimage.
            # Also gives us access to progfiguration stuff.
            "--volume",
            f"{self.psyopsdir}:/home/build/psyops",
            # I have somehow made it so I can't build psyopsOS-base package without this,
            # but I couldn't tell u why. :(
            # TODO: fucking fix this
            "--volume",
            f"{self.psyopsdir}:/psyops",
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
            f"{tempdir_sshpubkey.as_posix()}:{self.in_container_ssh_key_path}.pub:ro",
            "--env",
            # Environment variables that mkimage.sh (or one of the scripts it calls) uses
            f"PSYOPSOS_BUILD_DATE_ISO8601={build_date.strftime('%Y-%m-%dT%H:%M:%S%z')}",
            "--env",
            f"PSYOPSOS_BUILD_GIT_REVISION={build_git_revision}",
            "--env",
            f"PSYOPSOS_BUILD_GIT_DIRTY={str(build_git_dirty)}",
            self.docker_builder_tag_prefix + self.alpine_version,
        ]

        return self

    def __exit__(self, exc_type, exc_value, traceback):
        shutil.rmtree(self.tempdir)

    @property
    def workdir_volname(self):
        """A volume name for the Docker working directory.

        We create a Docker volume for the workdir - it's not a bind mount because Docker volumes are faster.
        Use this for its name.
        This doesn't need to be configurable, it isn't used anywhere else.
        """
        return f"psyopsos-build-workdir-{self.alpine_version}"

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
