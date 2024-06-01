"""General role helpers"""

import hashlib
from importlib.abc import Traversable
import os
import shutil

from progfiguration import logger
from progfiguration.inventory.roles import ProgfigurationRole


def copy_role_dir_recursively(role: ProgfigurationRole, role_dir: Traversable, dest_dir: str, sync: bool = False):
    """Copy a role directory recursively.

    Args:
        role: The role to copy the directory for
        role_dir: The directory to copy
        dest_dir: The destination directory
        sync: If True, delete files in dest_dir that are not in role_dir
    """
    role.localhost.makedirs(dest_dir)
    source_items = set()
    for item in role_dir.iterdir():
        destpath = f"{dest_dir}/{item.name}"
        logger.debug(f"Copying {item} to {destpath}")
        source_items.add(item.name)
        if item.is_dir():
            copy_role_dir_recursively(role, item, destpath, sync=sync)
        else:
            role.localhost.cp(item, destpath, "root", "root", 0o640)

    if sync:
        dest_items = set(os.listdir(dest_dir))
        logger.debug(f"Sync enabled, removing items not in {role_dir} from {dest_dir}. {source_items=}, {dest_items=}")
        for item in dest_items - source_items:
            logger.debug(f"Removing {dest_dir}/{item}")
            if os.path.isdir(f"{dest_dir}/{item}"):
                shutil.rmtree(f"{dest_dir}/{item}")
            else:
                os.unlink(f"{dest_dir}/{item}")
