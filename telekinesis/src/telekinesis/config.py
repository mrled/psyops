"""Configuration for telekinetic operations

This is necessarily full of implementation details and local paths.

Secrets should be stored in 1Password, and accessed with the getsecret function.
"""

from pathlib import Path
import pprint

from telekinesis.tksecrets import gopass_get


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
            """The path to the aports checkout on the host... assumed to be a sibling of ths psyops checkout."""
            self.psyops_aports_scripts = root / "psyopsOS" / "aports-scripts"
            """The path to the psyopsOS aports scripts overlay directory on the host"""
            self.psyopsOS_base = root / "psyopsOS" / "psyopsOS-base"
            """The path to the psyopsOS-base package directory on the host"""
            self.buildcontainer = root / "psyopsOS" / "buildcontainer"
            """The path to the psyopsOS build directory on the host"""
            self.minisign_seckey = root / "psyopsOS" / "minisign.seckey"
            """The path to the minisign secret key on the host"""
            self.minisign_pubkey = root / "psyopsOS" / "minisign.pubkey"
            """The path to the minisign public key on the host"""
            self.neuralupgrade = root / "psyopsOS" / "neuralupgrade"

    class TelekinesisConfigDeaddropNode:
        """Configuration for the deaddrop config node"""

        def __init__(self, artifacts: Path):
            self.bucketname = "com-micahrl-psyops-http-bucket"
            """The S3 bucket used for psyopsOS and progfiguration_blacksite"""
            self.region = "us-east-2"
            """The S3 region"""
            self.localpath = artifacts / "deaddrop"
            """Path to the local directory that is synced with the bucket"""
            self.osdir = self.localpath / "os"
            """Path to the directory containing OS images"""
            self.apk_repo_root = self.localpath / "apk"
            """Path to the directory containing the APK repositories (one per Alpine version)"""
            self.isofilename = "psyopsOScd-psyboot-x86_64.iso"
            """The filename that our mkimage creates"""
            self.sqfilename = "psyopsOSsq-psysquash-x86_64.iso"
            """The filename that our mkimage creates"""
            self.isopath = self.osdir / self.isofilename
            """The path to the ISO image"""

        def get_credential(self) -> tuple[str, str]:
            """Get the AWS credentials from 1Password, and return them as a tuple of (username, password)"""
            return (
                gopass_get("psyopsOS/deaddrop.keyid"),
                gopass_get("psyopsOS/deaddrop.secretkey"),
            )

    class TelekinesisBuildcontainerNode:
        """Configuration for the buildcontainer node"""

        def __init__(self, alpine_version: str):
            self.alpine_version = alpine_version
            """The version of Alpine to use"""
            self.dockertag_prefix = "psyopsos-builder-"
            """The Docker image tag prefix (will be suffixed with the Alpine version)"""
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
            """The Alpine mkimage.sh ISO profile for psyopsOS,
            which requires a profile_PROFILENAME file in the aports scripts overlay directory"""
            self.dockertag = f"{self.dockertag_prefix}{self.alpine_version}"
            """The Docker image tag of the build container"""

        def get_signing_key(self) -> str:
            """Get the signing key from 1Password"""
            return gopass_get("psyopsOS/abuild.rsa.key")

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
            self.ovmf_extracted_path = artroot / "ovmf-extracted"
            """The path to the extracted OVMF files"""
            self.ovmf_extracted_code = self.ovmf_extracted_path / "usr/share/edk2.git/ovmf-x64/OVMF_CODE-pure-efi.fd"
            """The path to the extracted OVMF_CODE-pure-efi.fd file"""
            self.ovmf_extracted_vars = self.ovmf_extracted_path / "usr/share/edk2.git/ovmf-x64/OVMF_VARS-pure-efi.fd"
            """The path to the extracted OVMF_VARS-pure-efi.fd file"""
            self.uefishell_iso_relpath = "usr/share/edk2.git/ovmf-x64/UefiShell.iso"
            """The path to the UEFI shell ISO, relative to the extracted OVMF root"""
            self.uefishell_img_relpath = "uefi_shell_X64.img"
            """The path to the UEFI shell image relative to the root of the UefiShell.iso file"""
            self.uefishell_extracted_bin = self.ovmf_extracted_path / "efi/boot/bootx64.efi"
            """The path to the extracted UEFI shell binary from the image inside ISO"""

            self.osdir_path = artroot / "psyopsOS.dir"
            """The path to the OS directory.
            Contains a single psyopsOS version, including
            kernel, initramfs, System.map, config, modloop, and squashfs files,
            and a boot/ directory which may contain DTB files if appropriate for the platform.
            """
            self.ostar_path = artroot / "psyopsOS.tar"
            """The path to the OS tarfile.
            The osdir_path in a tarball.
            """
            self.ostar_versioned_fmt = "psyopsOS.{version}.tar"
            """The format string for the versioned OS tarfile.
            Used as the base for the filename in S3, and also of the signature file.
            """
            self.esptar_path = artroot / "psyopsESP.tar"
            """The path to the EFI system partition tarball"""
            self.esptar_manifest = artroot / "psyopsESP.manifest.json"
            """The path to the JSON manifest for the EFI system partition tarball"""
            self.esptar_versioned_fmt = "psyopsESP.{version}.tar"
            """The format string for the versioned EFI system partition tarfile.
            Used as the base for the filename in S3, and also of the signature file.
            """

            self.node_secrets_filename_fmt = "psyops-secret.{nodename}.tar"
            """Format string for building the name of psyops-secret tarball files"""
            self.node_image_filename_fmt = "psyopsOS.{nodename}.img"
            """Format string for building the name of psyopsOS image files"""

            self.neuralupgrade = artroot / "neuralupgrade.pyz"

        def node_secrets(self, nodename: str) -> Path:
            """Get the path to the node secrets tarball"""
            return self.root / self.node_secrets_filename_fmt.format(nodename=nodename)

        def node_image(self, nodename: None | str = None) -> Path:
            """Get the path to the node image. If nodename is None, return the path to the generic image."""
            if nodename is None:
                nodename = "generic"
            return self.root / self.node_image_filename_fmt.format(nodename=nodename)

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

    def pformat(self, **kwargs) -> str:
        """Return a pretty-printed string representation of the config"""
        return pprint.pformat(
            dict(
                repopaths=self.repopaths.__dict__,
                deaddrop=self.deaddrop.__dict__,
                buildcontainer=self.buildcontainer.__dict__,
                artifacts=self.artifacts.__dict__,
            ),
            **kwargs,
        )


tkconfig = TelekinesisConfig()
