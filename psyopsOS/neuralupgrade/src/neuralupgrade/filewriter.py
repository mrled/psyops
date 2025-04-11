import datetime
import glob
import os
import shutil
import subprocess
from typing import Union

from neuralupgrade import logger


def write_file_carefully(
    filepath: str,
    contents: Union[str, bytes],
    updated: datetime.datetime,
    binary: bool = False,
    max_old_files: int = 10,
    max_old_days: int = 30,
):
    """Write a new file carefully, and keep old versions

    - Write new contents to a temporary file
    - Copy the old file to a backup location
    - Move the new one into place
    - Keep backups, but remove more than max_old_files backups that are older than max_old_days days

    We create backup files with a timestamp in the filename,
    but when we remove them we only look at the modification time.
    On FAT32, the modification time is only accurate to 2 seconds.
    Whatever.
    """
    stampfmt = "%Y%m%d-%H%M%S.%f"
    nowstamp = updated.strftime(stampfmt)
    filepath_tmp = f"{filepath}.new.{nowstamp}"
    this_backup = f"{filepath}.old.{nowstamp}"

    readmode = "rb" if binary else "r"
    writemode = "wb" if binary else "w"

    with open(filepath, readmode) as f:
        existing_contents = f.read()
        if existing_contents == contents:
            logger.debug(f"File {filepath} already has the same contents, not writing")
            return

    logger.debug(f"Writing new file contents to {filepath_tmp}")
    with open(filepath_tmp, writemode) as f:
        f.write(contents)

    if os.path.exists(filepath):
        logger.debug(f"Backing up old {filepath} to {this_backup}")
        shutil.copy(filepath, this_backup)
        subprocess.run(["sync"], check=True)
    else:
        logger.debug(f"No old {filepath} to back up")

    logger.debug(f"Moving new {filepath_tmp} to {filepath}")
    shutil.move(filepath_tmp, filepath)
    subprocess.run(["sync"], check=True)

    oldfiles = glob.glob(f"{filepath}.old.*")
    for idx, oldfile in enumerate(oldfiles):
        if idx < max_old_files:
            logger.debug(f"Keeping {oldfile} because it's one of the {max_old_files} most recent")
            continue
        olddate = datetime.datetime.fromtimestamp(os.path.getmtime(oldfile))
        if (datetime.datetime.now() - olddate).days > max_old_days:
            logger.debug(
                f"Removing {oldfile} because it's older than {max_old_days} days and there are more than {max_old_files} backups"
            )
            os.remove(oldfile)
        else:
            logger.debug(f"Keeping {oldfile} because it's newer than {max_old_days} days")
    subprocess.run(["sync"], check=True)
