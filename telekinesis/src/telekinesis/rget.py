"""Download files with requests"""

from pathlib import Path

import requests


def rget(url: str, filepath: Path, no_clobber=True):
    """Downloads a file from the given URL and saves it locally.

    If no_clobber is True (default), this function will not redownload an existing file.
    """
    if no_clobber and filepath.exists():
        return
    filepath.parent.mkdir(parents=True, exist_ok=True)
    response = requests.get(url, stream=True)
    if response.status_code == 200:
        with filepath.open("wb") as file:
            for chunk in response.iter_content(chunk_size=128):
                file.write(chunk)
    else:
        raise requests.exceptions.HTTPError(
            f"HTTP Error {response.status_code} trying to download {url} - {response.reason}"
        )
