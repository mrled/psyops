"""Command execution"""

import subprocess

from progfiguration import logger


def sh(*args, **kwargs) -> subprocess.CompletedProcess:
    """Run and log a command

    This is just a wrapper around subprocess.run()

    * Capture output
    * Log the command and its output
    * Check the result by default
    * Return the process object
    """
    check = True
    if "check" in args:
        check = args["check"]
        del args["check"]
    logger.debug(f"Running command: {args[0]}")
    result = subprocess.run(*args, **kwargs, capture_output=True)
    logger.info(f"Command completed with return code {result.returncode}: {args[0]}")
    logger.info(f"stdout: {result.stdout.decode()}")
    logger.info(f"stderr: {result.stderr.decode()}")
    if check and result.returncode != 0:
        raise Exception(f"Command failed: {args[0]}")
    return result
