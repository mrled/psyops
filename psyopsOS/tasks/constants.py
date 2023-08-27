"""Constants for tasks"""

from dataclasses import dataclass
import os


psyopsdir = os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
psyopsosdir = os.path.join(psyopsdir, "psyopsOS")
aportsscriptsdir = os.path.join(psyopsosdir, "aports-scripts")
staticdir = os.path.join(psyopsosdir, "static")
progfigsite_dir = os.path.join(psyopsdir, "progfiguration_blacksite")
psyopsOS_base_dir = os.path.join(psyopsosdir, "psyopsOS-base")
docker_builder_dir = os.path.join(psyopsosdir, "build")
site_public_dir = os.path.join(psyopsosdir, "public")
isodir = os.path.join(psyopsosdir, "iso")

docker_builder_volname_workdir = "psyopsos-build-workdir"

aportsdir = os.path.expanduser("~/Documents/Repositories/aports")
docker_builder_tag_prefix = "psyopsos-builder-"
mkimage_profile = "psyopsOS"
architecture = "x86_64"

# This is the name to set for the SSH key in the Alpine builder container.
# It doesn't rely on any file with this name existing on the host,
# but it should be the right name for the key that comes out of secrets.save_apk_signing_key()
ssh_key_file = "psyops@micahrl.com-62ca1973.rsa"

# TODO: Accept an exact version here, and update aports checkout to that version, and rebuild the Docker container if necessary.
# One problem with multiple Alpine base versions is different Python versions,
# which means the progfiguration_blacksite package is being built with different Python version requirements
# dependong on what's on the builder container.
# Might need to split the APK repo by Alpine base version.
alpine_version = "3.18"

site_bucket = "com-micahrl-psyops-http-bucket"


@dataclass
class ApkPaths:
    """Paths to the APK repository"""

    alpine_version: str

    # The APK repo name
    # When building a package with abuild, it finds this name by looking in the grandparent directory of the APKBUILD file (../../).
    # See also progfiguration_blacksite's buildapk command, which forces this with a tempdir.
    # This is just called "repo=" in the abuild sh script, and is not configurable.
    reponame = "psyopsOS"

    # When inside the psyops container, the path to the public/ directory's apk repository.
    # It will create a subdirectory for the Alpine version and then the reponame,
    # leading to a full path like /psyops/psyopsOS/public/apk/3.16/psyopsOS.
    # This should match the path in build/Dockerfile.
    _incontainer_apks_path_prefix = "/psyops/psyopsOS/public/apk"

    # The URI to the public/ directory's apk repository.
    _apks_public_uri = "https://psyops.micahrl.com/apk"

    # The path to the repository inside the container
    incontainer = f"{_incontainer_apks_path_prefix}/v{alpine_version}/{reponame}"

    # The parent to the incontainer path
    incontainer_repo_parent = f"{_incontainer_apks_path_prefix}/v{alpine_version}"

    # The URI that is accessible on the web
    uri = f"{_apks_public_uri}/v{alpine_version}/{reponame}"
