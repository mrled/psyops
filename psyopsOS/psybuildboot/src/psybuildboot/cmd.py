"""The psybuildboot command"""

import argparse
import hashlib
from io import BytesIO
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
import tarfile

import requests

from psybuildboot import logger
from psybuildboot.constants import filesystems


class MountManager:
    """Context manager to mount a filesystem and unmount it when exiting the context

    If the filesystem is already mounted, do nothing.
    """

    def __init__(self, source: str, target: str):
        self.source = source
        self.target = target

    def __enter__(self):
        # Mount the filesystem with the specified options
        subprocess.run(["mount", self.source, self.target, "-o", "ro"], check=True)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Unmount the filesystem when exiting the context
        subprocess.run(["umount", self.target], check=True)

    def remount_rw(self):
        """Remount the filesystem rw"""
        subprocess.run(["mount", "-o", "remount,rw", self.target], check=True)


class Manifest:
    """A manifest for psyopsOS boot data"""

    def __init__(self, version: str, manifest_type: str, files: dict[str, dict[str, str]]):
        self.version = version
        """The version of the manifest"""
        self.type = manifest_type
        """The type of the manifest, either 'efisys' or 'os'"""
        self.files = files
        """A dict of files in the manifest, mapping filenames to dicts of {"uri": <uri>, "sha256": <sha256>}}"""

    @classmethod
    def from_json(cls, json_str: dict[str, str]) -> 'Manifest':
        """Construct a manifest from a JSON object"""
        data = json.loads(json_str)
        return cls(**data)

    def to_json(self, **kwargs) -> dict[str, str]:
        """Serialize the manifest to a JSON object"""
        return json.dumps({
            "version": self.version,
            "type": self.type,
            "files": self.files,
        }, **kwargs)


def get_remote_manifest(imgtype: str, version: str = "latest") -> Manifest:
    """Get the manifest for the given image type and version"""
    r = requests.get(f"https://psyops.micahrl.com/img/{imgtype}/{version}/manifest.json")
    r.raise_for_status()
    return Manifest.from_json(r.text)


def get_local_manifest(imgtype: str) -> Manifest:
    """Get the manifest for the given image type from the local filesystem"""
    if imgtype == "efisys":
        subprocess.run(["mount", filesystems["efisys"]["mountpoint"]], check=True)
        manifest = os.path.join(filesystems["efisys"]["mountpoint"], "manifest.json")
    elif imgtype == "os":
        nonbooted_label, nonbooted_mountpoint = get_nonbooted_partition()
        subprocess.run(["mount", f"LABEL={nonbooted_label}"], check=True)
        manifest = os.path.join(nonbooted_mountpoint, "manifest.json")
    else:
        raise ValueError(f"Unknown image type {imgtype}")
    with open(manifest) as fp:
        return Manifest.from_json(fp.read())


def get_nonbooted_partition() -> dict[str, str]:
    """Get the label and mountpoint for the non-booted psyopsOS partition"""
    with open("/proc/cmdline") as fp:
        cmdline = fp.read()
        if f" psyopsos={filesystems["a"]["label"]} " in cmdline and f" psyopsos={filesystems["b"]["label"]} " in cmdline:
            raise ValueError("Invalid kernel cmdline - both psyopsOS-A and psyopsOS-B are specified")
        elif f" psyopsos={filesystems["a"]["label"]} " in cmdline:
            return filesystems["b"]
        elif f" psyopsos={filesystems["b"]["label"]} " in cmdline:
            return filesystems["a"]
        else:
            raise ValueError("Could not determine nonbooted psyopsOS partition")


def download_manifest_files(manifest: Manifest, destination: Path, clean_other: bool = False) -> None:
    """Download the files in the manifest to the destination directory

    If clean_other is True, delete any files in the destination directory that are not in the manifest.
    """
    for filename, fileinfo in manifest.files.items():
        filepath = destination / filename
        filepath.parent.mkdir(parents=True, exist_ok=True)
        r = requests.get(fileinfo["uri"], stream=True)
        r.raise_for_status()
        with filepath.open("wb") as fp:
            for chunk in r.iter_content(chunk_size=8192):
                fp.write(chunk)
    if clean_other:
        for root, dirs, files in os.walk(destination):
            for file in files:
                # The path relative to the destination directory
                rel_path = os.path.relpath(os.path.join(root, file), destination)
                if rel_path not in manifest.files:
                    os.remove(os.path.join(root, file))


def download_and_extract_tarball(url, target_dir, checksum_type='sha256') -> tuple[str, list[tarfile.TarInfo]]:
    """
    Download a tarball from a URL, calculate its checksum, and extract it.

    Args:
    url (str): The URL of the tarball.
    target_dir (str): The directory to extract the tarball to.
    checksum_type (str): Type of checksum to calculate (default is 'sha256').

    Returns:
    str: The calculated checksum.
    list[tarfile.TarInfo]: A list of the members of the tarball.
    """
    if checksum_type not in hashlib.algorithms_available:
        raise ValueError(f"Unsupported checksum type: {checksum_type}")
    hasher = hashlib.new(checksum_type)
    members=[]
    with requests.get(url, stream=True) as response:
        response.raise_for_status()
        for chunk in response.iter_content(chunk_size=8192):
            hasher.update(chunk)
            with tarfile.open(fileobj=BytesIO(chunk), mode='r|*') as tar:
                for member in tar:
                    if member not in members:
                        members.append(member)
                    tar.extract(member, path=target_dir)
    return hasher.hexdigest(), members


def makeparser() -> argparse.ArgumentParser:
    """Make the argument parser for the psybuildboot command"""

    parser = argparse.ArgumentParser(
        description="Build or update the psyopsOS boot image",
    )
    parser.add_argument(
        "--verbose", "-b", action="store_true", help="Verbose output"
    )

    subparsers = parser.add_subparsers(
        dest="subcommand",
        required=True,
    )

    # Build the boot image
    buildparser = subparsers.add_parser(
        "build",
        help="Build the boot image",
    )
    required_files = ["kernel", "initramfs", "squashfs", "modloop"]
    optional_files = ["System.map", "config", "boot/"]
    buildparser.add_argument(
        "--files",
        nargs="+",
        help=f"Files to add to the boot image - should contain at least {required_files} and we also suggest {optional_files}. Some platforms (ARM...) require DTB files in a boot/ directory.",
    )
    buildparser.add_argument(
        "--loopdev",
        default="/dev/loop0",
        help="The loop device to use for the image, which must currently not be used. Default: %(default)s",
    )
    buildparser.add_argument(
        "--efi-size",
        default="128",
        help="The size in MB of the EFI system partition. Default: %(default)s",
    )
    buildparser.add_argument(
        "--ab-size",
        default="1536",
        help="The size in MB of the A/B partition. Default: %(default)s",
    )
    buildparser.add_argument(
        "--secrets-tarball",
        help="The path to a tarball containing psyops-secrets for a single node. If not passed, a generic image with an empty psyops-secrets partition will be created.",
    )
    buildparser.add_argument(
        "--secrets-size",
        default="128",
        help="The size in MB of the psyops-secrets partition. Default: %(default)s",
    )
    buildparser.add_argument(
        "--memtest-bin",
        help="The path to the memtest86+ binary. If not passed, memtest will not be included in the image.",
    )
    buildparser.add_argument(
        "outimg",
        help="The path to the output image.",
    )

    # Options used by more than one subparser
    efiostypeopt = argparse.ArgumentParser(add_help=False)
    efiostypeopt.add_argument(
        "type",
        choices=["efisys", "os"],
        help="The type of update, either 'efisys' for the EFI system partition containing GRUB etc, or 'os' for the psyopsOS A/B partition",
    )
    efiabtypeopt = argparse.ArgumentParser(add_help=False)
    efiabtypeopt.add_argument(
        "type",
        choices=["efisys", "a", "b"],
        help="The type of update, either 'efisys' for the EFI system partition containing GRUB etc, or 'a'/'b' for the 'psyopsOS-A'/'psyopsOS-B' partitions",
    )
    versopt = argparse.ArgumentParser(add_help=False)
    versopt.add_argument(
        "--version", default="latest", help="The version, or 'latest' for the latest version (default)"
    )
    verspathopts = argparse.ArgumentParser(add_help=False)
    verspathgrp = verspathopts.add_mutually_exclusive_group()
    verspathgrp.add_argument(
        "--version",
        default="latest",
        help="The version, or 'latest' for the latest version (default)",
    )
    verspathgrp.add_argument(
        "--path",
        help="The path to a local copy of the update to apply",
    )

    # Show a remote version
    showparser = subparsers.add_parser(
        "show",
        parents=[efiostypeopt, verspathopts],
        help="Show a version",
    )

    # Download an update from the deaddrop
    dlparser = subparsers.add_parser(
        "download",
        parents=[efiostypeopt, versopt],
        help="Download an update from the deaddrop",
    )
    dlparser.add_argument(
        "destination",
        help="The directory to download the update to",
    )

    # Check installed version
    checkparser = subparsers.add_parser(
        "check",
        parents=[efiabtypeopt, verspathopts],
        help="Check the installed version",
    )

    # Update the running boot disk
    updateparser = subparsers.add_parser(
        "update",
        parents=[efiostypeopt, verspathopts],
        help="Update the running boot disk",
    )
    updateparser.add_argument(
        "--force",
        action="store_true",
        help="Force the update to run even if the version is already applied",
    )

    return parser


def main() -> None:
    parser = makeparser()
    parsed = parser.parse_args()

    logfmt = logging.Formatter("%(message)s")
    loghandler = logging.StreamHandler()
    loghandler.setFormatter(logfmt)
    logger.addHandler(loghandler)

    if parsed.verbose:
        logger.setLevel("DEBUG")

    def get_parsed_path_or_remote_manifest() -> Manifest:
        """Retrieve a manifest from a local file path or the remote deaddrop by version"""
        if parsed.path:
            with open(parsed.path) as fp:
                return Manifest.from_json(fp.read())
        else:
            return get_remote_manifest(parsed.type, parsed.version)

    def get_parsed_fslabel_mountpoint() -> tuple[str, str]:
        """Get the filesystem label and mountpoint for the parsed image type"""
        try:
            partition = filesystems[parsed.type]
        except KeyError:
            if parsed.type == "os":
                partition = get_nonbooted_partition()
            else:
                parser.error(f"Unknown image type {parsed.type}")
        return partition["label"], partition["mountpoint"]

    if parsed.subcommand == "build":
        raise NotImplementedError()
    elif parsed.subcommand == "show":
        manifest = get_parsed_path_or_remote_manifest()
        print(manifest.to_json(indent=4))
    elif parsed.subcommand == "download":
        manifest = get_remote_manifest(parsed.type, parsed.version)
        download_manifest_files(manifest, Path(parsed.destination), clean_other=True)
        logger.verbose(f"Downloaded version {manifest.version} to {parsed.destination}")
    elif parsed.subcommand == "check":
        manifest_tocheck = get_parsed_path_or_remote_manifest()
        fslabel, mountpoint = get_parsed_fslabel_mountpoint()
        with MountManager(fslabel, mountpoint):
            manifest_ondisk = get_local_manifest(parsed.type)
            if manifest_tocheck.version == manifest_ondisk.version and not parsed.force:
                logger.verbose(f"Version {manifest_tocheck.version} is already installed to {mountpoint}")
                sys.exit(0)
            else:
                logger.verbose(f"Checked version {manifest_tocheck.version}, but found version {manifest_ondisk.version} installed to {mountpoint}")
                sys.exit(1)
    elif parsed.subcommand == "update":
        manifest_tocheck = get_parsed_path_or_remote_manifest()
        raise NotImplementedError()
    else:
        parser.error(f"Unknown subcommand {parsed.subcommand}")
