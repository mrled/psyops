"""Constants for tasks"""

import os


psyopsdir = os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
psyopsosdir = os.path.join(psyopsdir, "psyopsOS")
aportsscriptsdir = os.path.join(psyopsosdir, "aports-scripts")
staticdir = os.path.join(psyopsosdir, "static")
progfigsite_dir = os.path.join(psyopsdir, "progfiguration_blacksite")
psyopsOS_base_dir = os.path.join(psyopsosdir, "psyopsOS-base")
docker_builder_dir = os.path.join(psyopsosdir, "build")
site_public_dir = os.path.join(psyopsosdir, "public")

docker_builder_volname_workdir = "psyopsos-build-workdir"

aportsdir = os.path.expanduser("~/Documents/Repositories/aports")
workdir = os.path.expanduser("~/Scratch/psyopsOS-build-tmp")
isodir = os.path.expanduser("~/Downloads/")
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
alpine_version = "3.16"

site_bucket = "com-micahrl-psyops-http-bucket"

# When inside the psyops container, the path to the public/ directory's apk repository
incontainer_apks_path = "/psyops/psyopsOS/public/apk"
