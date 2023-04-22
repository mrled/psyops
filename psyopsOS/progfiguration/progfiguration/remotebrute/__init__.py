"""A dumbfuck remoting module

It is something to fear.
It contains the "danger of violent death".
We endeavor to keep it "nasty, brutish, and short".

TODO:
* Wrapper of scp for multi-host scp
* Use a thread pool for multi-host execution
* Wrapper of scp that will mkdir the destination parent
* Make sure dest is always clear/consistent. Does it make a new dest directory?
* Implement ControlMaster for faster repeated copies/commands
"""

import os.path
import secrets
import shlex
import string
from typing import Any, List, Union

from progfiguration import logger
from progfiguration.cmd import run


def generate_random_string(length):
    """Generate a secure random string of the specified length."""
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for i in range(length))


def scp(host: str, sources: Union[str, List[str]], dest: str):
    """Use scp to copy a file, directory, or list"""

    if isinstance(sources, str):
        sources = [sources]

    cmd = ["scp", "-r"]
    cmd += sources
    cmd += [f"{host}:{dest}"]
    run(cmd)


def cpexec(
    host: str,
    source: str,
    args: List[str] = None,
    dest: str = "",
    interpreter: list[str] = None,
    ssh_tty: bool = True,
    ssh_stdin: Any = None,
    keep_remote_file: bool = False,
):
    """Copy a file to a remote host, then execute and delete the remote copy

    host: the remote host to connect to
    source: the local file to copy
    args: arguments to pass to the command
    dest: the destination path on the remote host. If not specified, a random name will be generated.
    interpreter: arguments to prepend to the command, like ["python3"] or ["python3", "-u"]
    ssh_tty: whether to allocate a tty for the ssh connection
    ssh_stdin: a file-like object which we pass to run() as stdin (e.g. subprocess.DEVNULL)
    keep_remote_file: if True, the remote file will not be deleted after execution
    """

    if args is None:
        args = []

    if dest == "":
        bname = os.path.basename(source)
        dstname = f"{generate_random_string(16)}-{bname}"
        dest = f"/tmp/{dstname}"

    scp(host, [source], dest)

    try:
        command_list = []
        if interpreter:
            command_list += interpreter
        command_list += [dest] + args
        remote_cmd = " ".join(shlex.quote(arg) for arg in command_list)
        logger.debug(f"Will connect to {host} and execute command: {remote_cmd}")

        ssh_cmd_run_args = {}
        if ssh_stdin is not None:
            ssh_cmd_run_args["stdin"] = ssh_stdin

        ssh_cmd = ["ssh"]
        if ssh_tty:
            ssh_cmd += ["-tt"]
        ssh_cmd += [host, remote_cmd]

        execresult = run(ssh_cmd, **ssh_cmd_run_args)

        logger.debug(f"Finished ssh command to {host}")
    finally:
        if keep_remote_file:
            print(f"Kept the remote file at {dest}")
        else:
            # We don't need to fuck with ttys/fds here because rm is simple
            run(["ssh", host, f"rm -f {dest}"])

    return execresult
