import datetime
import os
import shutil
import subprocess
import threading
import traceback
from typing import Optional

from neuralupgrade import logger
from neuralupgrade.coginitivedefects import MultiError
from neuralupgrade.filesystems import Filesystem, Filesystems, Mount, sides
from neuralupgrade.grub_cfg import write_grub_cfg_carefully


def minisign_verify(file: str, pubkey: Optional[str] = None) -> None:
    """Verify a file with minisign."""
    pubkey_args = ["-p", pubkey] if pubkey else []
    cmd = ["minisign", "-V", *pubkey_args, "-m", file]
    logger.debug(f"Running minisign: {cmd}")
    result = subprocess.run(cmd, text=True)
    if result.returncode != 0:
        raise Exception(f"minisign returned non-zero exit code {result.returncode}")


def parse_trusted_comment(
    comment: Optional[str] = None, sigcontents: Optional[str] = None, sigfile: Optional[str] = None
) -> dict:
    """Parse a trusted comment from a psyopsOS minisig.

    Can provide just the comment,
    the contents of the minisig file,
    or the path to the minisig file.

    Example file contents:

        untrusted comment: signature from minisign secret key
        RURFlbvwaqbpRv1RGZk6b0TkCUmJZvNRKVqfyveYOicg3g1FR6EUmvwkPGwB8yFJ+m9l/Al6sixSOAUVQDwwsfs23Coa9xEHBwI=
        trusted comment: type=psyopsOS filename=psyopsOS.grubusb.os.20240129-155151.tar version=20240129-155151 kernel=6.1.75-0-lts alpine=3.18
        nISvkyfCnUI6Xjgr0vz+g4VbymHJh8rvPAHKncAm5sXVT9HMyQV5+HhgvMP3NLaRKSCng6VAYkIufXYkCmobCQ==

    Returns a dict of key=value pairs, like:

        {
            "type": "psyopsOS",
            "filename": "psyopsOS.grubusb.os.20240129-155151.tar",
            "version": "20240129-155151",
            "kernel": "6.1.75-0-lts",
            "alpine": "3.18",
        }

    Note that we do NOT verify the signature! This is just a parser.
    """
    trusted_comment_prefix = "trusted comment: "
    argcount = sum([1 for x in [comment, sigcontents, sigfile] if x])
    if argcount != 1:
        raise ValueError(
            f"Must specify exactly one of comment, sigcontents, or sigfile; got {comment}, {sigcontents}, {sigfile}"
        )
    if sigfile:
        sigcontents = open(sigfile).read()
        if not sigcontents:
            raise ValueError(f"Empty file {sigfile}")
    if sigcontents:
        for line in sigcontents.splitlines():
            if line.startswith(trusted_comment_prefix):
                comment = line
                break
        else:
            raise ValueError("No trusted comment in minisig contents")
    logger.debug(f"Parsing trusted comment: {comment}")
    trusted_comment = comment[len(trusted_comment_prefix) - 1 :]

    # Trusted comment fields should be a space-separated list of key=value pairs.
    # Some old versions also included a value that wasn't a key=value pair.
    # Just ignore that if it's there.
    # metadata = {kv[0]: kv[1] for kv in [x.split("=") for x in trusted_comment.split()]}
    kvs = [x.split("=") for x in trusted_comment.split() if "=" in x]
    metadata = {kv[0]: kv[1] for kv in kvs}
    return metadata


def parse_psyopsOS_grub_info_comment(comment: Optional[str] = None, file: Optional[str] = None) -> dict:
    """Parse a trusted comment from a psyopsOS minisig

    The comment comes from grub.cfg, like this:

        #### The next line is used by neuralupgrade to show information about the current configuration.
        # neuralupgrade-info: last_updated={last_updated} default_boot_label={default_boot_label} extra_programs={extra_programs}
        ####

    Can accept either just the "# neuralupgrade-info: " line, or a path to the grub.cfg file.
    """
    argcount = sum([1 for x in [comment, file] if x])
    if argcount != 1:
        raise ValueError("Must specify exactly one of comment or file; got {comment}, {file}")

    prefix = "# neuralupgrade-info: "
    if file:
        with open(file) as f:
            for line in f.readlines():
                if line.startswith(prefix):
                    comment = line
                    break
            else:
                raise ValueError(f"Could not find trusted comment in {file}")

    if not comment.startswith(prefix):
        raise ValueError(f"Invalid grub info comment: {comment}")

    # parse all the key=value pairs in the trusted comment
    metadata = {kv[0]: kv[1] for kv in [x.split("=") for x in comment[len(prefix) :].split()]}
    return metadata


def show_booted(filesystems: Filesystems) -> dict:
    """Show information about the grubusb device

    Uses threads to speed up the process of mounting the filesystems and reading the minisig files.
    """
    booted, nonbooted = sides(filesystems)

    result = {
        booted: {
            "mountpoint": filesystems.bylabel(booted).mountpoint,
            "running": True,
            "next_boot": False,
        },
        nonbooted: {
            "mountpoint": filesystems.bylabel(nonbooted).mountpoint,
            "running": False,
            "next_boot": False,
        },
        "efisys": {
            "mountpoint": filesystems.efisys.mountpoint,
        },
    }

    def _get_os_tc(label: str):
        with filesystems.bylabel(label).mount(writable=False) as mountpoint:
            minisig_path = os.path.join(mountpoint, "psyopsOS.grubusb.os.tar.minisig")
            try:
                info = parse_trusted_comment(sigfile=minisig_path)
            except FileNotFoundError:
                info = {f"error": "missing minisig at {minisig_path}"}
            except Exception as exc:
                info = {"error": str(exc), "minisig_path": minisig_path, "traceback": traceback.format_exc()}
        result[label] = {**result[label], **info}

    def _get_grub_info():
        with filesystems.efisys.mount(writable=False) as mountpoint:
            grub_cfg_path = os.path.join(mountpoint, "grub", "grub.cfg")
            try:
                info = parse_psyopsOS_grub_info_comment(file=grub_cfg_path)
            except FileNotFoundError:
                info = {"error": f"missing grub.cfg at {grub_cfg_path}"}
            except Exception as exc:
                info = {"error": str(exc), "grub_cfg_path": grub_cfg_path, "traceback": traceback.format_exc()}
        result["efisys"] = {**result["efisys"], **info}

    nonbooted_thread = threading.Thread(target=_get_os_tc, args=(booted,))
    nonbooted_thread.start()
    booted_thread = threading.Thread(target=_get_os_tc, args=(nonbooted,))
    booted_thread.start()
    efisys_thread = threading.Thread(target=_get_grub_info)
    efisys_thread.start()

    booted_thread.join()
    nonbooted_thread.join()
    efisys_thread.join()

    # Handle these after the threads have joined
    # I'm not sure what happens if the os tc threads and the efi thread tries to write to the same dict at the same time
    try:
        next_boot = result["efisys"]["default_boot_label"]
        result[next_boot]["next_boot"] = True
    except KeyError:
        result["error"] = "Could not determine next boot"

    return result


def apply_ostar(tarball: str, osmount: str, verify: bool = True, verify_pubkey: Optional[str] = None):
    """Apply an ostar to a device"""

    if verify:
        minisign_verify(tarball, pubkey=verify_pubkey)

    cmd = ["tar", "-x", "-f", tarball, "-C", osmount]
    logger.debug(f"Extracting {tarball} to {osmount} with {cmd}")
    subprocess.run(cmd, check=True)
    minisig = tarball + ".minisig"
    try:
        shutil.copy(minisig, os.path.join(osmount, "psyopsOS.grubusb.os.tar.minisig"))
        logger.debug(f"Copied {minisig} to {osmount}/psyopsOS.grubusb.os.tar.minisig")
    except FileNotFoundError:
        logger.warning(f"Could not find {minisig}, partition will not know its version")
    logger.debug(f"Finished applying {tarball} to {osmount}")


# Note to self: we release efisys tarballs containing stuff like memtest, which can be extracted on top of an efisys that has grub-install already run on it
def configure_efisys(filesystems: Filesystems, efisys: str, default_boot_label: str, tarball: Optional[str] = None):
    """Populate the EFI system partition with the necessary files"""

    # I don't understand why I need --boot-directory too, but I do
    cmd = [
        "grub-install",
        "--target=x86_64-efi",
        f"--efi-directory={efisys}",
        f"--boot-directory={efisys}",
        "--removable",
    ]
    logger.debug(f"Running grub-install: {cmd}")
    subprocess.run(cmd, check=True)

    if tarball:
        logger.debug(f"Extracting efisys tarball {tarball} to {efisys}")
        subprocess.run(
            [
                "tar",
                # Ignore permissions as we're extracting to a FAT32 filesystem
                "--no-same-owner",
                "--no-same-permissions",
                "--no-overwrite-dir",
                "-x",
                "-f",
                tarball,
                "-C",
                efisys,
            ],
            check=True,
        )
        logger.debug(f"Finished extracting {tarball} to {efisys}")

    write_grub_cfg_carefully(filesystems, efisys, default_boot_label)
    logger.debug("Done configuring efisys")


def apply_updates(
    filesystems: Filesystems,
    targets: list[str],
    ostar: str = "",
    esptar: str = "",
    verify: bool = True,
    pubkey: str = "",
    no_update_default_boot_label: bool = False,
    default_boot_label: str = "",
):
    """Apply updates to the filesystems.

    Handles any valid combination of updates to the a, b, nonbooted, and efisys filesystems.
    Properly ensures filesystems are mounted at most once,
    and at the end tries to return them to their original state.
    (See the Mount context manager for more details on how this works.)
    """

    mounts: dict[str, tuple[str, Mount]] = {}
    """A dictionary of name: (mountpoints, Mount).

    The name is a string like "a", "b", "nonbooted", or "efisys".
    The mountpoint is a string path.
    The Mount object is a context manager.

    About our use of the Mount context managers:
    Each Filesystem has a .mount() which returns a Mount context manager,
    which mounts the filesystem on entry and unmounts it on exit.
    We call the __enter__ and __exit__ methods of the Mount context manager manually
    and keep track of which are mounted in this dict
    so that we can mount what we need when we need,
    never mount the same filesystem more than once to avoid slowdowns,
    and unmount everything at the end.
    """

    def idempotently_mount(name: str, fs: Filesystem, writable: bool = False):
        if name not in mounts:
            mount = fs.mount(writable=writable)
            mountpoint = mount.__enter__()
            mounts[name] = (mountpoint, mount)
        return mounts[name]

    def unmount_all_returning_exceptions():
        exceptions = []
        for _, mount in mounts.values():
            try:
                mount.__exit__(None, None, None)
            except Exception as exc:
                exceptions.append(exc)
        return exceptions

    # The default boot label is the partition label to use the next time the system boots (A or B).
    # When updating nonbooted, it is assumed to be the nonbooted side and cannot be passed explicitly,
    # although updating it can be skipped if no_update_default_boot_label is passed.
    # When installing a new psyopsESP on a partition without a grub.cfg file, it must be passed explicitly.
    # When updating an existing psyopsESP, it may be omitted to read the existing value from the existing grub.cfg file,
    # or passed explicitly.
    # When updating a or b, it will be omitted unless passed explicitly.
    # If it is passed explicitly, it must be one of the A/B labels (taking into account any overrides).
    detect_existing_default_boot_label = False
    if default_boot_label:
        if default_boot_label not in [filesystems.a.label, filesystems.b.label]:
            # If default_boot_label is passed, it has to be one of theaA/B labels
            raise Exception(
                f"Invalid default boot label '{default_boot_label}', must be one of the A/B labels '{filesystems.a.label}'/'{filesystems.b.label}'"
            )
    else:
        if "efisys" in targets and "nonbooted" not in targets:
            detect_existing_default_boot_label = True

    try:
        if detect_existing_default_boot_label:
            # We need to get the default boot label from the existing grub.cfg file.
            # We mount as writable because we might need to write a new grub.cfg file later,
            # but we can't know that until we check whether what's there matches the new value.
            efisys_mountpoint, _ = idempotently_mount("efisys", filesystems.efisys, writable=True)
            if not os.path.exists(os.path.join(efisys_mountpoint, "grub", "grub.cfg")):
                raise Exception(
                    f"--default-boot-label not passed and no existing GRUB configuration found at {efisys_mountpoint}/grub/grub.cfg file; if the ESP is empty, you need to pass --default-boot-label"
                )
            try:
                grub_cfg_info = parse_psyopsOS_grub_info_comment(
                    file=os.path.join(efisys_mountpoint, "grub", "grub.cfg")
                )
                default_boot_label = grub_cfg_info["default_boot_label"]
            except FileNotFoundError:
                default_boot_label = filesystems.a.label
            except Exception as exc:
                raise Exception(
                    f"Could not find default boot label from existing {efisys_mountpoint}/grub/grub.cfg file"
                ) from exc

        # Handle actions
        if "nonbooted" in targets:
            targets.remove("nonbooted")
            updated = datetime.datetime.now()
            booted, nonbooted = sides(filesystems)
            nonbooted_mountpoint, _ = idempotently_mount("nonbooted", filesystems.bylabel(nonbooted), writable=True)
            apply_ostar(ostar, nonbooted_mountpoint, verify=verify, verify_pubkey=pubkey)
            if not no_update_default_boot_label:
                default_boot_label = nonbooted

        for side in ["a", "b"]:
            if side in targets:
                targets.remove(side)
                this_ab_mountpoint, _ = idempotently_mount(side, filesystems[side], writable=True)
                apply_ostar(ostar, this_ab_mountpoint, verify=verify, verify_pubkey=pubkey)

        if "efisys" in targets:
            targets.remove("efisys")
            efisys_mountpoint, _ = idempotently_mount("efisys", filesystems.efisys, writable=True)
            # This handles any updates to the default_boot_label in grub.cfg.
            configure_efisys(filesystems, efisys_mountpoint, default_boot_label, tarball=esptar)
        elif default_boot_label:
            # If we didn't handle updates to default_boot_label in grub.cfg above, do so here.
            efisys_mountpoint, _ = idempotently_mount("efisys", filesystems.efisys, writable=True)
            write_grub_cfg_carefully(filesystems, efisys_mountpoint, default_boot_label, updated=updated)

        if targets:
            raise Exception(f"Unknown targets argument(s): {targets}")

    except Exception as exc:
        exceptions = unmount_all_returning_exceptions()
        if exceptions:
            exceptions.append(exc)
            raise MultiError(
                f"Encountered exception when applying updates to {filesystems} with targets {targets}, and exceptions unmounting filesystems to clean up",
                exceptions,
            )
        else:
            raise

    finally:
        exceptions = unmount_all_returning_exceptions()
        if exceptions:
            raise MultiError(
                f"Encountered exceptions when exiting Mount context managers for {filesystems} with targets {targets}",
                exceptions,
            )
