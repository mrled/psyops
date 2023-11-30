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

    @dataclass
    class TelekinesisConfigDeaddropNode:
        """Configuration for the deaddrop config node"""

        bucketname: str
        """The S3 bucket used for psyopsOS and progfiguration_blacksite"""
        region: str
        """The S3 region"""
        onepassword_item: str
        """The 1Password item for the IAM user that has access to the bucket"""
        localpath: Path
        """Path to the local directory that is synced with the bucket"""
        isodir: Path
        """Path to the directory containing the ISO image"""
        isofilename: str
        """The filename that our mkimage creates"""
        sqfilename: str
        """The filename that our mkimage creates"""

    @dataclass
    class TelekinesisBuildcontainerNode:
        """Configuration for the buildcontainer node"""

        alpine_version: str
        """The version of Alpine to use"""
        dockertag_prefix: str
        """The Docker image tag prefix (will be suffixed with the Alpine version)"""
        onepassword_signing_key: str
        """The 1Password item for the APK signing key"""
        apk_key_filename: str
        """This is the name to set for the APK signing key in the Alpine builder container.
        It doesn't rely on any file with this name existing on the host."""
        apkreponame: str
        """The APK repo name
        When building a package with abuild, it finds this name by looking in the grandparent directory of the APKBUILD file (../../).
        See also progfiguration_blacksite's buildapk command, which forces this with a tempdir.
        This is just called "repo=" in the abuild sh script, and is not configurable."""
        uri: str
        """The URI that is accessible on the"""
        isotag: str
        """Alpine ISO image tag for the boot image we build with mkimage.sh"""
        sqtag: str
        """Alpine squashfs image tag for the boot image we build with mkimage.sh"""
        architecture: str
        """The architecture for the ISO image"""
        mkimage_iso_profile: str
        """The Alpine mkimage.sh ISO profile for psyopOS,
        which requires a profile_PROFILENAME file in the aports scripts overlay directory"""
        mkimage_squashfs_profile: str
        """The Alpine mkimage.sh ISO profile for psyopOS,
        which requires a profile_PROFILENAME file in the aports scripts overlay directory"""

        @property
        def dockertag(self):
            """The Docker image tag of the build container"""
            return f"{self.dockertag_prefix}{self.alpine_version}"

    @dataclass
    class TelekinesisConfigOVMFNode:
        """Configuration for the OVMF node"""

        url: str
        """The URL to download the OVMF firmware from"""
        artifact: Path
        """The path to the downloaded RPM artifact"""
        extracted_code: Path
        """The path to the extracted OVMF_CODE-pure-efi.fd file"""
        extracted_vars: Path
        """The path to the extracted OVMF_VARS-pure-efi.fd file"""

    class TelekinesisConfigArtifactsNode:
        """Configuration for the artifacts node"""

        def __init__(self, artroot: Path):
            self.memtest_zipfile = artroot / "memtest.zip"
            """The path to the memtest86+ zipfile"""
            self.memtest64efi = artroot / "memtest64.efi"
            """The path to the memtest86+ EFI binary"""

            self.grubusbsq_img = artroot / "psyopsOS.grubusbsq.img"
            """The path to the grubusbsq disk image"""
            self.grubusbsq_initramfs = artroot / "psyopsOS.grubusbsq.initramfs"
            """The path to the grubusbsq initramfs"""
            self.grubusbsq_squashfs = artroot / "psyopsOS.grubusbsq.squashfs"
            """The path to the grubusbsq squashfs image"""

            self.grubusb_img = artroot / "psyopsOS.grubusb.img"
            """The path to the grubusb disk image"""
            self.grubusb_initramfs = artroot / "psyopsOS.grubusb.initramfs"
            """The path to the grubusb initramfs"""
            self.grubusb_squashfs = artroot / "psyopsOS.grubusb.squashfs"
            """The path to the grubusb squashfs image"""

    # Class variables

    alpine_version = "3.18"
    """The version of Alpine to use"""

    psyopsroot = Path(__file__).parent.parent.parent.parent
    """The path to the psyops checkout on the host"""

    # Initializer

    def __init__(self):
        self.repopaths = self.PsyopsRepoPaths(root=self.psyopsroot)
        artdir = self.repopaths.artifacts
        self.deaddrop = self.TelekinesisConfigDeaddropNode(
            bucketname="com-micahrl-psyops-http-bucket",
            region="us-east-2",
            onepassword_item="op://Personal/AWS_IAM_user_com-micahrl-psyops-http-bucket-deployer",
            localpath=self.psyopsroot / "psyopsOS" / "deaddrop" / "replica",
            isodir=self.psyopsroot / "psyopsOS" / "deaddrop" / "replica" / "iso",
            isofilename="psyopsOScd-psyboot-x86_64.iso",
            sqfilename="psyopsOSsq-psysquash-x86_64.iso",
        )
        self.buildcontainer = self.TelekinesisBuildcontainerNode(
            alpine_version=self.alpine_version,
            dockertag_prefix="psyopsos-builder-",
            onepassword_signing_key="op://Personal/psyopsOS_abuild_ssh_key",
            apk_key_filename="psyops@micahrl.com-62ca1973.rsa",
            apkreponame="psyopsOS",
            uri=f"https://psyops.micahrl.com/",
            isotag="psyboot",
            sqtag="psysquash",
            architecture="x86_64",
            mkimage_iso_profile="psyopsOScd",
            mkimage_squashfs_profile="psyopsOSsq",
        )
        self.ovmf = self.TelekinesisConfigOVMFNode(
            url="https://www.kraxel.org/repos/jenkins/edk2/edk2.git-ovmf-x64-0-20220719.209.gf0064ac3af.EOL.no.nore.updates.noarch.rpm",
            artifact=artdir / "edk2.git-ovmf-x64-0-20220719.209.gf0064ac3af.EOL.no.nore.updates.noarch.rpm",
            extracted_code=artdir / "ovmf-extracted/usr/share/edk2.git/ovmf-x64/OVMF_CODE-pure-efi.fd",
            extracted_vars=artdir / "ovmf-extracted/usr/share/edk2.git/ovmf-x64/OVMF_VARS-pure-efi.fd",
        )
        self.artifacts = self.TelekinesisConfigArtifactsNode(self.repopaths.artifacts)


tkconfig = TelekinesisConfig()
