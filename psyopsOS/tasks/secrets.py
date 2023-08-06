"""Retrieving secrets in the build process"""

from pathlib import Path
import subprocess


def save_apk_signing_key(path: Path):
    """Save the APK signing key to a file, by reading 1password vault"""
    print("Retrieving APK signing key from 1Password, may require authentication...")
    subprocess.run(
        f"op read op://Personal/psyopsOS_abuild_ssh_key/notesPlain --out-file {path.as_posix()}",
        shell=True,
        check=True,
    )
