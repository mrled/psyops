"""Configuration for telekinetic operations

This is necessarily full of implementation details and local paths.

Secrets should be stored in 1Password, and accessed with the getsecret function.
"""

from dataclasses import dataclass
from pathlib import Path
import subprocess


def getsecret(item: str, field: str) -> str:
    """Get a secret from 1Password"""
    proc = subprocess.run(
        ["op", "read", f"{item}/{field}"],
        capture_output=True,
        check=True,
        text=True,
    )
    return proc.stdout.strip()


psyopsroot = Path(__file__).parent.parent.parent.parent

tkconfig = dict(
    # The version of Alpine to use
    alpine_version="3.18",
    # The path to the psyops checkout on the host
    psyopsroot=psyopsroot,
    # The S3 bucket used for psyopsOS and progfiguration_blacksite
    deaddrop=dict(
        bucketname="com-micahrl-psyops-http-bucket",
        region="us-east-2",
        onepassword_item="op://Personal/AWS_IAM_user_com-micahrl-psyops-http-bucket-deployer",
        localpath=psyopsroot / "psyopsOS" / "deaddrop" / "replica",
        isodir=psyopsroot / "psyopsOS" / "deaddrop" / "replica" / "iso",
        # The filename that our mkimage creates
        isofilename="psyopsOS-psyopsos-boot-x86_64.iso",
    ),
    # The container we use for building APK packages and ISO images
    buildcontainer=dict(
        # The path to the Dockerfile directory for the Alpine builder
        builddir=psyopsroot / "psyopsOS" / "build",
        # The Docker image tag prefix (will be suffixed with the Alpine version)
        tag_prefix="psyopsos-builder-",
        # The 1Password item for the APK signing key
        onepassword_signing_key="op://Personal/psyopsOS_abuild_ssh_key",
        # Path to the full checkout of the Alpine aports repository
        aportsrepo=psyopsroot.parent / "aports",
        # Path to the directory containing the psyopsOS aports scripts overlay files
        psyopsscripts=psyopsroot / "psyopsOS" / "aports-scripts",
        # This is the name to set for the APK signing key in the Alpine builder container.
        # It doesn't rely on any file with this name existing on the host.
        apk_key_filename="psyops@micahrl.com-62ca1973.rsa",
        # The APK repo name
        # When building a package with abuild, it finds this name by looking in the grandparent directory of the APKBUILD file (../../).
        # See also progfiguration_blacksite's buildapk command, which forces this with a tempdir.
        # This is just called "repo=" in the abuild sh script, and is not configurable.
        apkreponame="psyopsOS",
        # The URI that is accessible on the
        uri=f"https://psyops.micahrl.com/",
        # Path to the psyopsOS-base package directory on the host
        psyopsosbasedir=psyopsroot / "psyopsOS" / "psyopsOS-base",
        # Alpine ISO image tag for the boot image we build with mkimage.sh
        isotag="psyboot",
        # The architecture for the ISO image
        architecture="x86_64",
        # The profile for mkimage, which requires a mkimg.PROFILE.sh file in the aports scripts overlay directory
        mkimage_profile="psyopsOS",
    ),
)
