"""Functions for parsing and verifying trusted comments in minisigs and comments in the GRUB config file."""

import subprocess
from typing import Optional

from neuralupgrade import logger


def minisign_verify(file: str, pubkey: Optional[str] = None) -> None:
    """Verify a file with minisign."""
    pubkey_args = ["-p", pubkey] if pubkey else []
    cmd = ["minisign", "-V", *pubkey_args, "-m", file]
    logger.debug(f"Running minisign: {cmd}")
    result = subprocess.run(cmd, text=True, capture_output=True)
    stdout = result.stdout.strip()
    stderr = result.stderr.strip()
    logger.debug(f"minisign stdout: {stdout}")
    logger.debug(f"minisign stderr: {stderr}")
    if result.returncode != 0:
        raise Exception(
            f"minisign returned non-zero exit code {result.returncode} with stdout '{stdout}' and stderr '{stderr}'"
        )


def parse_trusted_comment(
    comment: Optional[str] = None, sigcontents: Optional[str] = None, sigfile: Optional[str] = None
) -> dict[str, str]:
    """Parse a trusted comment from a psyopsOS minisig.

    Can provide just the comment,
    the contents of the minisig file,
    or the path to the minisig file.

    Example file contents:

        untrusted comment: signature from minisign secret key
        RURFlbvwaqbpRv1RGZk6b0TkCUmJZvNRKVqfyveYOicg3g1FR6EUmvwkPGwB8yFJ+m9l/Al6sixSOAUVQDwwsfs23Coa9xEHBwI=
        trusted comment: type=psyopsOS filename=psyopsOS.20240129-155151.tar version=20240129-155151 kernel=6.1.75-0-lts alpine=3.18
        nISvkyfCnUI6Xjgr0vz+g4VbymHJh8rvPAHKncAm5sXVT9HMyQV5+HhgvMP3NLaRKSCng6VAYkIufXYkCmobCQ==

    Returns a dict of key=value pairs, like:

        {
            "type": "psyopsOS",
            "filename": "psyopsOS.20240129-155151.tar",
            "version": "20240129-155151",
            "kernel": "6.1.75-0-lts",
            "alpine": "3.18",
        }

    Note that we do NOT verify the signature! This is just a parser.
    """
    if comment is None:
        comment = ""

    trusted_comment_prefix = "trusted comment: "
    argcount = sum([1 for x in [comment, sigcontents, sigfile] if x])
    if argcount != 1:
        raise ValueError(
            f"Must specify exactly one of comment, sigcontents, or sigfile; got {comment}, {sigcontents}, {sigfile}"
        )
    if sigfile:
        with open(sigfile, "r") as f:
            sigcontents = f.read()
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


def parse_psyopsOS_neuralupgrade_info_comment(comment: Optional[str] = None, file: Optional[str] = None) -> dict:
    """Parse a trusted comment from a psyopsOS minisig

    The comment comes from the boot file (grub.cfg or similar), like this:

        #### The next line is used by neuralupgrade to show information about the current configuration.
        # neuralupgrade-info: last_updated={last_updated} default_boot_label={default_boot_label} extra_programs={extra_programs}
        ####

    Can accept either just the "# neuralupgrade-info: " line, or a path to the file containing the comment
    """
    if comment is None:
        comment = ""

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
        raise ValueError(f"Invalid neuralupgrade-info comment: {comment}")

    # parse all the key=value pairs in the trusted comment
    metadata = {kv[0]: kv[1] for kv in [x.split("=") for x in comment[len(prefix) :].split()]}
    return metadata
