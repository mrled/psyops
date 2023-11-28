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


# Static configuration; other config may rely on these
_psyopsroot = Path(__file__).parent.parent.parent.parent
_workdir = _psyopsroot / "work"


# Configuration for the telekinesis CLI and build process
tkconfig = dict(
    # The version of Alpine to use
    alpine_version="3.18",
    # The path to the psyops checkout on the host
    psyopsroot=_psyopsroot,
    # The psyops workdir on the host, containing build intermediate files and artifacts
    workdir=_workdir,
    # The S3 bucket used for psyopsOS and progfiguration_blacksite
    deaddrop=dict(
        bucketname="com-micahrl-psyops-http-bucket",
        region="us-east-2",
        onepassword_item="op://Personal/AWS_IAM_user_com-micahrl-psyops-http-bucket-deployer",
        localpath=_psyopsroot / "psyopsOS" / "deaddrop" / "replica",
        isodir=_psyopsroot / "psyopsOS" / "deaddrop" / "replica" / "iso",
        # The filename that our mkimage creates
        isofilename="psyopsOScd-psyboot-x86_64.iso",
        sqfilename="psyopsOSsq-psysquash-x86_64.iso",
    ),
    # The container we use for building APK packages and ISO images
    buildcontainer=dict(
        # The path to the Dockerfile directory for the Alpine builder
        builddir=_psyopsroot / "psyopsOS" / "build",
        # The Docker image tag prefix (will be suffixed with the Alpine version)
        tag_prefix="psyopsos-builder-",
        # The 1Password item for the APK signing key
        onepassword_signing_key="op://Personal/psyopsOS_abuild_ssh_key",
        # Path to the full checkout of the Alpine aports repository
        aportsrepo=_psyopsroot.parent / "aports",
        # Path to the directory containing the psyopsOS aports scripts overlay files
        psyopsscripts=_psyopsroot / "psyopsOS" / "aports-scripts",
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
        psyopsosbasedir=_psyopsroot / "psyopsOS" / "psyopsOS-base",
        # Alpine ISO image tag for the boot image we build with mkimage.sh
        isotag="psyboot",
        # Alpine squashfs image tag for the boot image we build with mkimage.sh
        sqtag="psysquash",
        # The architecture for the ISO image
        architecture="x86_64",
        # The Alpine mkimage.sh ISO profile for psyopOS,
        # which requires a profile_PROFILENAME file in the aports scripts overlay directory
        mkimage_iso_profile="psyopsOScd",
        # The Alpine mkimage.sh ISO profile for psyopOS,
        # which requires a profile_PROFILENAME file in the aports scripts overlay directory
        mkimage_squashfs_profile="psyopsOSsq",
    ),
    # OVMF firmware for QEMU
    ovmf=dict(
        url="https://www.kraxel.org/repos/jenkins/edk2/edk2.git-ovmf-x64-0-20220719.209.gf0064ac3af.EOL.no.nore.updates.noarch.rpm",
        artifact=_workdir / "edk2.git-ovmf-x64-0-20220719.209.gf0064ac3af.EOL.no.nore.updates.noarch.rpm",
        extracted_code=_workdir / "ovmf-extracted/usr/share/edk2.git/ovmf-x64/OVMF_CODE-pure-efi.fd",
        extracted_vars=_workdir / "ovmf-extracted/usr/share/edk2.git/ovmf-x64/OVMF_VARS-pure-efi.fd",
    ),
)
