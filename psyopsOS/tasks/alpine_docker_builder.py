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
        # If true, add "--interactive --tty" to the docker run command
        interactive=False,
        # Clean the docker volume before running
        cleandockervol=False,
    ) -> None:
        self.aports_checkout_dir = aports_checkout_dir
        self.aports_scripts_overlay_dir = aports_scripts_overlay_dir
        self.isodir = isodir
        self.ssh_key_file = ssh_key_file
        self.in_container_ssh_key_path = f"/home/build/.abuild/{ssh_key_file}"
        self.alpine_version = alpine_version
        self.psyopsdir = psyopsdir
        self.docker_builder_tag_prefix = docker_builder_tag_prefix
        self.interactive = interactive
        self.cleandockervol = cleandockervol

        # Path to the psyopsOS project within the root psyops repo
        self.psyopsosdir = os.path.join(self.psyopsdir, "psyopsOS")
        # Path to the directory containing the Dockerfile for the Alpine builder
        self.docker_builder_dir = os.path.join(self.psyopsosdir, "build")

        # An in-container path for handling the mkimage working directory.
        # A docker volume will be mounted here.
        # Clean with `invoke dockervolclean`.
        self.in_container_workdir = "/home/build/workdir"

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
        needscreate = False
        if self.cleandockervol:
            subprocess.run(["docker", "volume", "rm", self.workdir_volname])
            needscreate = True
        else:
            inspected = subprocess.run(
                f"docker volume inspect {self.workdir_volname}", shell=True
            )
            needscreate = inspected.returncode != 0
        if needscreate:
            subprocess.run(f"docker volume create {self.workdir_volname}", shell=True)

        self.mkimage_clean(self.in_container_workdir)

        # Save the SSH private key to the temp dir
        self.tempdir = Path(tempfile.mkdtemp())
        tempdir_sshkey = self.tempdir / "sshkey"
        tempdir_sshpubkey = self.tempdir / "sshpubkey"
        save_apk_signing_key(tempdir_sshkey)
        # Generate a public key from the private key
        cmd = [
            "openssl",
            "rsa",
            "-in",
            tempdir_sshkey.as_posix(),
            "-pubout",
            "-out",
            tempdir_sshpubkey.as_posix(),
        ]
        subprocess.run(cmd, check=True)

        self.docker_cmd = [
            "docker",
            "run",
        ]
        if self.interactive:
            self.docker_cmd += ["--interactive", "--tty"]
        self.docker_cmd += [
            "--rm",
        ]

        # Docker volumes
        self.docker_cmd += [
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
            f"{self.workdir_volname}:{self.in_container_workdir}",
            # This is where the iso will be copied after it is built
            "--volume",
            f"{self.isodir}:/home/build/iso",
            # Mount my SSH keys into the container
            "--volume",
            f"{tempdir_sshkey.as_posix()}:{self.in_container_ssh_key_path}:ro",
            "--volume",
            f"{tempdir_sshpubkey.as_posix()}:{self.in_container_ssh_key_path}.pub:ro",
        ]

        # Pass any relevant environment variables to the container
        for envvar in os.environ.keys():
            if (
                envvar.startswith("PSYOPS")
                or envvar.startswith("PROGFIGURATION")
                or envvar.startswith("PROGFIGSITE")
            ):
                self.docker_cmd += [
                    "--env",
                    f"{envvar}={os.environ[envvar]}",
                ]

        self.docker_cmd += [
            # Environment variables that mkimage.sh (or one of the scripts it calls) uses
            "--env",
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

    def mkimage_clean(self, workdir):
        """Clean directories before build

        This should be done before any runs - it doesn't clean apk cache or other large working datasets,
        but it removes some easy to regenerate stuff that sometimes causes problems.
        """
        cleandirs = []
        cleandirs += glob.glob(f"{workdir}/apkovl*")
        cleandirs += glob.glob(f"{workdir}/apkroot*")
        for d in cleandirs:
            print(f"Removing {d}...")
            subprocess.run(f"rm -rf '{d}'", shell=True, check=True)
