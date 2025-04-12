from dataclasses import dataclass
import os

import requests

from neuralupgrade import logger
from neuralupgrade.firmware import Firmware
from neuralupgrade.update_metadata import minisign_verify, parse_trusted_comment


def is_folder(path: str) -> bool:
    """Check if a path is a folder by checking if it ends with a slash.

    Rely on the user and/or logic in cmd.py
    to append a / if the path must be folder and a / isn't present.

    This has to work even for paths that don't exist yet.
    """
    return path.endswith("/")


def download_repository_file(repository_url: str, filename: str) -> str:
    """Download a repository file and return its contents

    Not suitable for large files which should be streamed.
    """
    url = f"{repository_url}/{filename}"
    logger.debug(f"Downloading file from {url}")
    response = requests.get(url)
    response.raise_for_status()
    text_content = response.text
    logger.debug(f"Item retrieved from {url}: {response.text}")
    return text_content


@dataclass
class DownloadedSignatureResult:
    url: str
    text: str
    unverified_metadata: dict


def download_update_signature(
    firmware: Firmware, repository_url: str, filename_format: str, version: str
) -> DownloadedSignatureResult:
    """Download a psyopsOS update signature

    The signature isn't verified here --
    that only happens when the update is downloaded.

    Return a DownloadedSignatureResult.
    """
    minisig_filename = filename_format.format(fwtype=firmware.fwtype, version=version) + ".minisig"
    minisig_url = f"{repository_url}/{minisig_filename}"

    logger.debug(f"Downloading update minisig from {minisig_url}")
    response = requests.get(minisig_url)
    response.raise_for_status()
    text_content = response.text
    logger.debug(f"Update minisig retrieved from {minisig_url}: {response.text}")
    unverified_metadata = parse_trusted_comment(sigcontents=text_content)
    logger.debug(f"Parsed UNVERIFIED metadata from minisig: {unverified_metadata}")

    return DownloadedSignatureResult(minisig_url, text_content, unverified_metadata)


def download_update(
    firmware: Firmware,
    repository_url: str,
    filename_format: str,
    version: str,
    output: str,
    pubkey: str = "",
    verify: bool = True,
):
    """Download a psyopsOS update to the specified output location.

    If the output is a directory, the file will be saved with the default filename.

    First download the minisig file,
    then find the tarball filename from the minisig,
    download that from the repo,
    and finally verify that the signature matches the tarball.
    """

    downloaded = download_update_signature(firmware, repository_url, filename_format, version)

    update_filename = downloaded.unverified_metadata["filename"]
    update_url = f"{repository_url}/{update_filename}"

    if is_folder(output):
        update_local_path = f"{output}{update_filename}"
        # If the output is a directory,
        # and the tarball filename is different from the minisig filename,
        # which might happen if the minisig was downloaded as "latest" version,
        # the minisig file shoudl always be saved with its tarball's filename + .minisig.
        minisig_filename = downloaded.unverified_metadata["filename"] + ".minisig"
        minisig_filepath = f"{output}{minisig_filename}"
    else:
        # If the output is a file, that file represents the update tarball,
        # and the minisig file should be saved with the same name + .minisig.
        update_local_path = output
        minisig_filepath = os.path.basename(output) + ".minisig"
    with open(minisig_filepath, "w") as file:
        file.write(downloaded.text)

    logger.debug(f"Downloading update from {update_url} to {update_local_path}")
    with requests.get(update_url, stream=True) as response:
        response.raise_for_status()
        with open(update_local_path, "wb") as file:
            for chunk in response.iter_content(chunk_size=8192):
                if not chunk:
                    continue
                file.write(chunk)
    logger.debug(f"Update downloaded to {update_local_path}")

    if verify:
        minisign_verify(update_local_path, pubkey)

    return update_local_path
