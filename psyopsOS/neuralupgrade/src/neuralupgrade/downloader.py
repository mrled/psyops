import os

import requests

from neuralupgrade import logger
from neuralupgrade.osupdates import parse_psyopsOS_minisig_trusted_comment, minisign_verify


def download_update(
    repository_url: str, filename_format: str, version: str, output: str, pubkey: str = "", verify: bool = True
):
    """Download a psyopsOS update to the specified output location.

    If the output is a directory, the file will be saved with the default filename.

    First download the minisig file,
    then find the tarball filename from the minisig,
    download that from the repo,
    and finally verify that the signature matches the tarball.
    """
    minisig_filename = filename_format.format(version=version) + ".minisig"
    minisig_url = f"{repository_url}/{minisig_filename}"
    output_is_dir = output.endswith("/")
    if output_is_dir:
        os.makedirs(output, exist_ok=True)
        minisig_local_path = f"{output}{minisig_filename}"
    else:
        os.makedirs(os.path.dirname(output), exist_ok=True)
        minisig_local_path = output + ".minisig"

    logger.debug(f"Downloading update minisig from {minisig_url} to {minisig_local_path}")
    with requests.get(minisig_url, stream=True) as response:
        response.raise_for_status()
        with open(minisig_local_path, "wb") as file:
            for chunk in response.iter_content(chunk_size=8192):
                if not chunk:
                    continue
                file.write(chunk)
    logger.debug(f"Update minisig downloaded to {minisig_local_path}")

    unverified_metadata = parse_psyopsOS_minisig_trusted_comment(file=minisig_local_path)
    logger.debug(f"Parsed UNVERIFIED metadata from minisig: {unverified_metadata}")

    update_filename = unverified_metadata["filename"]
    update_url = f"{repository_url}/{update_filename}"

    if output_is_dir:
        update_local_path = f"{output}{update_filename}"
        if unverified_metadata["filename"] + ".minisig" != minisig_filename:
            # If the output is a directory,
            # and the minisig filename doesn't match the metadata, rename it to match.
            # This might happen if the minisig was downloaded as "latest" version.
            old_minisig_filename = minisig_filename
            minisig_filename = unverified_metadata["filename"] + ".minisig"
            logger.debug(f"Renaming minisig file to match metadata: {old_minisig_filename} -> {minisig_filename}")
            os.rename(minisig_local_path, f"{output}{minisig_filename}")
    else:
        # If the output is a file, that file represents the update tarball.
        update_local_path = output

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
        verified_metadata = minisign_verify(update_local_path, pubkey)
        logger.debug(f"Update verified with minisign pubkey {pubkey}, VERIFIED metadata: {verified_metadata}")
