"""Configuration for telekinetic operations

This is necessarily full of implementation details and local paths.

Secrets should be stored in 1Password, and accessed with the getsecret function.
"""

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


class TelekinesisConfig:
    """Configuration for telekinetic operations"""

    # Configuration node classes

    class PsyopsRepoPaths:
        """Configuration for the psyops repository paths"""

        def __init__(self, root: Path):
            self.root = root
            """The path to the psyops checkout on the host"""
            self.artifacts = root / "artifacts"
            """The path to the artifacts directory on the host, containing build intermediate files and artifacts"""
            self.aports = root.parent / "aports"
            """The path to the aports checkout on the host"""
            self.psyops_aports_scripts = root / "psyopsOS" / "aports-scripts"
            """The path to the psyopsOS aports scripts overlay directory on the host"""
            self.psyopsOS_base = root / "psyopsOS" / "psyopsOS-base"
            """The path to the psyopsOS-base package directory on the host"""
            self.build = root / "psyopsOS" / "build"
            """The path to the psyopsOS build directory on the host"""

    class TelekinesisConfigDeaddropNode:
        """Configuration for the deaddrop config node"""

        def __init__(self, artifacts: Path):
            self.bucketname = "com-micahrl-psyops-http-bucket"
            """The S3 bucket used for psyopsOS and progfiguration_blacksite"""
            self.region = "us-east-2"
            """The S3 region"""
            self.get_credential = lambda: (
                getsecret("op://Personal/AWS_IAM_user_com-micahrl-psyops-http-bucket-deployer", "username"),
                getsecret("op://Personal/AWS_IAM_user_com-micahrl-psyops-http-bucket-deployer", "password"),
            )
            """A function to retrieve the AWS credentials for writing to the bucket from a password store.
            Return a tuple of (username, password)
            """
            self.onepassword_item = "op://Personal/AWS_IAM_user_com-micahrl-psyops-http-bucket-deployer"
            """The 1Password item for the IAM user that has access to the bucket"""
            self.localpath = artifacts / "deaddrop"
            """Path to the local directory that is synced with the bucket"""
            self.isodir = self.localpath / "iso"
            """Path to the directory containing the ISO image"""
            self.apk_repo_root = self.localpath / "apk"
            """Path to the directory containing the APK repositories (one per Alpine version)"""
            self.isofilename = "psyopsOScd-psyboot-x86_64.iso"
            """The filename that our mkimage creates"""
            self.sqfilename = "psyopsOSsq-psysquash-x86_64.iso"
            """The filename that our mkimage creates"""

    class TelekinesisBuildcontainerNode:
        """Configuration for the buildcontainer node"""

        def __init__(self, alpine_version: str):
            self.alpine_version = alpine_version
            """The version of Alpine to use"""
            self.dockertag_prefix = "psyopsos-builder-"
            """The Docker image tag prefix (will be suffixed with the Alpine version)"""
            self.get_signing_key = (lambda: getsecret("op://Personal/psyopsOS_abuild_ssh_key", "notesPlain"),)
            """A function to retrieve the signing key from a password store"""
            self.apk_key_filename = "psyops@micahrl.com-62ca1973.rsa"
            """This is the name to set for the APK signing key in the Alpine builder container.
            It doesn't rely on any file with this name existing on the host."""
            self.apkreponame = "psyopsOS"
            """The APK repo name
            When building a package with abuild, it finds this name by looking in the grandparent directory of the APKBUILD file (../../).
            See also progfiguration_blacksite's buildapk command, which forces this with a tempdir.
            This is just called "repo=" in the abuild sh script, and is not configurable."""
            self.uri = f"https://psyops.micahrl.com/"
            """The URI that is accessible on the public Internet for the APK repository"""
            self.isotag = "psyboot"
            """Alpine ISO image tag for the boot image we build with mkimage.sh"""
            self.sqtag = "psysquash"
            """Alpine squashfs image tag for the boot image we build with mkimage.sh"""
            self.architecture = "x86_64"
            """The architecture for the ISO image"""
            self.mkimage_iso_profile = "psyopsOScd"
            """The Alpine mkimage.sh ISO profile for psyopOS,
            which requires a profile_PROFILENAME file in the aports scripts overlay directory"""
            self.dockertag = f"{self.dockertag_prefix}{self.alpine_version}"
            """The Docker image tag of the build container"""

    class TelekinesisConfigArtifactsNode:
        """Configuration for the artifacts node"""

        def __init__(self, artroot: Path):
            self.root = artroot
            """The path to the artifacts directory on the host, containing build intermediate files and artifacts"""

            self.memtest_zipfile = artroot / "memtest.zip"
            """The path to the memtest86+ zipfile"""
            self.memtest64efi = artroot / "memtest64.efi"
            """The path to the memtest86+ EFI binary"""

            self.ovmf_url = "https://www.kraxel.org/repos/jenkins/edk2/edk2.git-ovmf-x64-0-20220719.209.gf0064ac3af.EOL.no.nore.updates.noarch.rpm"
            """The URL to download the OVMF firmware from"""
            self.ovmf_rpm = artroot / "edk2.git-ovmf-x64-0-20220719.209.gf0064ac3af.EOL.no.nore.updates.noarch.rpm"
            """The path to the downloaded OVMF RPM artifact"""
            self.ovmf_extracted_code = artroot / "ovmf-extracted" / "usr/share/edk2.git/ovmf-x64/OVMF_CODE-pure-efi.fd"
            """The path to the extracted OVMF_CODE-pure-efi.fd file"""
            self.ovmf_extracted_vars = artroot / "ovmf-extracted" / "usr/share/edk2.git/ovmf-x64/OVMF_VARS-pure-efi.fd"
            """The path to the extracted OVMF_VARS-pure-efi.fd file"""

            self.grubusb_img = artroot / "psyopsOS.grubusb.img"
            """The path to the grubusb disk image"""

            self.grubusb_os_dir = artroot / "psyopsOS.grubusb.os"
            """The path to the grubusb OS directory.
            Contains a single psyopsOS version for a grubusb image (either A or B), including
            kernel, initramfs, System.map, config, modloop, and squashfs files,
            and a boot/ directory which may contain DTB files if appropriate for the platform.
            """

    # Class variables

    alpine_version = "3.18"
    """The version of Alpine to use"""

    psyopsroot = Path(__file__).parent.parent.parent.parent
    """The path to the psyops checkout on the host"""

    # Initializer

    def __init__(self):
        self.repopaths = self.PsyopsRepoPaths(root=self.psyopsroot)
        self.deaddrop = self.TelekinesisConfigDeaddropNode(self.repopaths.artifacts)
        self.buildcontainer = self.TelekinesisBuildcontainerNode(self.alpine_version)
        self.artifacts = self.TelekinesisConfigArtifactsNode(self.repopaths.artifacts)


tkconfig = TelekinesisConfig()
