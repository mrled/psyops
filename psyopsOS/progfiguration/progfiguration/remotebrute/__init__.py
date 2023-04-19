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
import subprocess
from typing import List, Union


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
    subprocess.run(cmd, check=True)


def ssh(host: str, command: str):
    """Use ssh to run a remote command

    Note that we do not run the command inside a shell;
    if you want to do that, you'll have to pass the command as
    "sh -c 'your command here'".
    (This means this function doesn't have to deal with nested quoting.)
    """

    # sshcmd = ["ssh", "-tt", host, command]
    sshcmd = ["ssh", host, command]
    result = subprocess.run(sshcmd, capture_output=True)
    if result.returncode != 0:
        print("Failed to run command:", sshcmd)
        print("stdout:", result.stdout.decode())
        print("stderr:", result.stderr.decode())
        raise subprocess.CalledProcessError(result.returncode, sshcmd, output=result.stdout, stderr=result.stderr)
    print("Ran command:", sshcmd)
    print("stdout:", result.stdout.decode())
    print("stderr:", result.stderr.decode())
    return result


def cpexec(
    host: str,
    source: str,
    args: List[str] = None,
    dest: str = "",
    interpreter: str = "",
    keep_remote_file: bool = False,
):
    """Copy a file to a remote host, then execute and delete the remote copy"""

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
            command_list.append(interpreter)
        command_list += [dest] + args
        command = " ".join(shlex.quote(arg) for arg in command_list)
        execresult = ssh(host, command)
    finally:
        if keep_remote_file:
            print(f"Kept the remote file at {dest}")
        else:
            ssh(host, f"rm -f {dest}")

    return execresult
