"""The Alpine Docker builder context manager"""

import datetime
import glob
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from telekinesis import config


def build_container(builder_tag: str, builder_dir: str, rebuild: bool = False):
    cmd = ["docker", "build", "--platform", "linux/amd64", "--progress=plain"]
    if rebuild:
        cmd += ["--no-cache"]
    cmd += ["--tag", builder_tag, builder_dir]
    subprocess.run(cmd, check=True)


class AlpineDockerBuilder:
    """A context manager for building Alpine packages and ISO images in a Docker container

    It saves the psyopsOS build key from 1Password to a temp directory so that you can use it to sign packages.
    It has property `tempdir_apkkey` that you can pass to the Docker container to use the key.
    """

    def __init__(
        self,
        # The path to the psyops checkout on the host
        psyops_checkout_dir,
        # The path to the aports checkout directory on the host
        aports_checkout_dir,
        # The path to the directory containing the aports scripts overlay files on the host
        aports_scripts_overlay_dir,
        # The place to put the ISO image when its done on the host
        isodir,
        # The key to use for signing APK packages (as a string)
        apk_key_value,
        # The filename for the APK key - just used in the Docker container, not the path to the key on the host.
        apk_key_filename,
        # The Alpine version to use
        alpine_version,
        # The path to the Dockerfile directory for the Alpine builder
        docker_builder_dir,
        # The Docker image tag prefix (will be suffixed with the Alpine version)
        docker_builder_tag_prefix,
        # If true, add "--interactive --tty" to the docker run command
        interactive=False,
        # Clean the docker volume before running
        cleandockervol=False,
        # If true, don't clean the temporary directory containing the APK key
        dangerous_no_clean_tmp_dir=False,
    ):
        self.psyopsdir = psyops_checkout_dir
        self.aports_checkout_dir = aports_checkout_dir
        self.aports_scripts_overlay_dir = aports_scripts_overlay_dir
        self.isodir = isodir
        self.apk_key_value = apk_key_value
        self.apk_key_filename = apk_key_filename
        self.in_container_apk_key_path = f"/home/build/.abuild/{apk_key_filename}"
        self.alpine_version = alpine_version
        self.docker_builder_tag_prefix = docker_builder_tag_prefix
        self.interactive = interactive
        self.cleandockervol = cleandockervol
        self.dangerous_no_clean_tmp_dir = dangerous_no_clean_tmp_dir
        self.docker_builder_dir = docker_builder_dir

        # An in-container path for handling the mkimage working directory.
        # A docker volume will be mounted here.
        # Clean with `invoke dockervolclean`.
        self.in_container_workdir = "/home/build/workdir"

        # The location the iso will be copied after it is built in the container.
        # isodir will be mounted here.
        self.in_container_isodir = "/home/build/iso"

        # The location of the psyops repository mount in the container.
        # psyops_checkout_dir willbe mounted here.
        self.in_container_psyops_checkout = "/home/build/psyops"

        # The location of APK repositories in the container (inside to the psyops checkout).
        self.in_container_apks_repo_root = f"{self.in_container_psyops_checkout}/psyopsOS/public/apk"

        # The tag for the Docker image, including the Alpine version suffix
        self.docker_builder_tag = f"{self.docker_builder_tag_prefix}{self.alpine_version}"

    def __enter__(self):
        os.umask(0o022)
        build_container(self.docker_builder_tag, self.docker_builder_dir)

        os.makedirs(self.isodir, exist_ok=True)

        build_date = datetime.datetime.now()

        revision_result = subprocess.run("git rev-parse HEAD", shell=True, capture_output=True)
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
            inspected = subprocess.run(f"docker volume inspect {self.workdir_volname}", shell=True)
            needscreate = inspected.returncode != 0
        if needscreate:
            subprocess.run(f"docker volume create {self.workdir_volname}", shell=True)

        self.mkimage_clean(self.in_container_workdir)

        # Save the APK private key to the temp dir
        self.tempdir = Path(tempfile.mkdtemp())
        tempdir_apkkey = self.tempdir / "apkkey"
        tempdir_apkpub = self.tempdir / "apkpub"
        with tempdir_apkkey.open("w") as f:
            f.write(self.apk_key_value)
        # Generate a public key from the private key
        cmd = [
            "openssl",
            "rsa",
            "-in",
            tempdir_apkkey.as_posix(),
            "-pubout",
            "-out",
            tempdir_apkpub.as_posix(),
        ]
        subprocess.run(cmd, check=True)

        self.docker_cmd = [
            "docker",
            "run",
            "--rm",
            # Make sure we're building x86_64 even if we're running on something else like an ARM Mac
            "--platform",
            "linux/amd64",
            # Give us full access to the psyops dir
            # Mounting this allows the build to access the psyopsOS/os-overlay/ and the public APK packages directory for mkimage.
            # Also gives us access to progfiguration stuff.
            "--volume",
            f"{self.psyopsdir}:/home/build/psyops",
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
            f"{self.isodir}:{self.in_container_isodir}",
            # Mount my APK keys into the container
            "--volume",
            f"{tempdir_apkkey.as_posix()}:{self.in_container_apk_key_path}:ro",
            "--volume",
            f"{tempdir_apkpub.as_posix()}:{self.in_container_apk_key_path}.pub:ro",
            # Environment variables that mkimage.sh (or one of the scripts it calls) uses
            "--env",
            f"PSYOPSOS_BUILD_DATE_ISO8601={build_date.strftime('%Y-%m-%dT%H:%M:%S%z')}",
            "--env",
            f"PSYOPSOS_BUILD_GIT_REVISION={build_git_revision}",
            "--env",
            f"PSYOPSOS_BUILD_GIT_DIRTY={str(build_git_dirty)}",
        ]

        if self.interactive:
            self.docker_cmd += ["--interactive", "--tty"]

        # Pass any relevant environment variables to the container
        for envvar in os.environ.keys():
            if envvar.startswith("PSYOPS") or envvar.startswith("PROGFIGURATION") or envvar.startswith("PROGFIGSITE"):
                self.docker_cmd += [
                    "--env",
                    f"{envvar}={os.environ[envvar]}",
                ]

        # Specify the container tag to run at the very end
        self.docker_cmd += [self.docker_builder_tag]

        # Commands to pass to the shell to run in the container, used in self.run_docker()
        self.docker_shell_commands = [
            "set -e",
            "export PATH=$PATH:$HOME/.local/bin",
            f"echo 'PACKAGER_PRIVKEY=\"{self.in_container_apk_key_path}\"' > $HOME/.abuild/abuild.conf",
            "ls -alF $HOME/.abuild",
            "uname -a",
        ]

        return self

    def run_docker(self, commands: list[str]):
        """Run commands in a shell inside the Docker container

        Prepends self.docker_shell_commands to the command list.
        """
        in_container_cmds = self.docker_shell_commands + commands
        docker_run_cmd = self.docker_cmd + ["sh", "-c", " && ".join(in_container_cmds)]
        if self.interactive:
            print(f"In interactive mode. Running docker with:")
            print(" \\\n  ".join(self.docker_cmd))
            print(f"Would have run the following inside the container")
            print("\n\t" + "\n\t".join(in_container_cmds))
            print(f"Instead, running a bash shell inside the container. Type 'exit' to exit.")
            subprocess.run(self.docker_cmd + ["/bin/bash"], stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr)
        else:
            print("Running Docker with:")
            print(" \\\n  ".join(docker_run_cmd))
            subprocess.run(docker_run_cmd, check=True)

    def run_docker_raw(self, commands: list[str]):
        """Run commands inside the Docker container directly (without a shell)"""
        subprocess.run(self.docker_cmd + commands)

    def __exit__(self, exc_type, exc_value, traceback):
        if not self.dangerous_no_clean_tmp_dir:
            shutil.rmtree(self.tempdir)
        else:
            print(
                f"WARNING: not cleaning temporary directory {self.tempdir}. It contains the APK key without a password, make sure to delete it manually!"
            )

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


def get_configured_docker_builder(
    interactive: bool = False, cleandockervol: bool = False, dangerous_no_clean_tmp_dir: bool = False
):
    """Make an AlpineDockerBuilder from the configuration"""
    return AlpineDockerBuilder(
        psyops_checkout_dir=config.tkconfig["psyopsroot"],
        aports_checkout_dir=config.tkconfig["buildcontainer"]["aportsrepo"],
        aports_scripts_overlay_dir=config.tkconfig["buildcontainer"]["psyopsscripts"],
        isodir=config.tkconfig["deaddrop"]["isodir"],
        apk_key_value=config.getsecret(config.tkconfig["buildcontainer"]["onepassword_signing_key"], "notesPlain"),
        apk_key_filename=config.tkconfig["buildcontainer"]["apk_key_filename"],
        alpine_version=config.tkconfig["alpine_version"],
        docker_builder_dir=config.tkconfig["buildcontainer"]["builddir"],
        docker_builder_tag_prefix=config.tkconfig["buildcontainer"]["tag_prefix"],
        interactive=interactive,
        cleandockervol=cleandockervol,
        dangerous_no_clean_tmp_dir=dangerous_no_clean_tmp_dir,
    )
