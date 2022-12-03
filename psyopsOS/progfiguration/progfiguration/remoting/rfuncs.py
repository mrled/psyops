"""Functions that mitogen can run remotely"""


import subprocess


def sh(command: str):
    result = subprocess.run(command, capture_output=True, shell=True)
    return {"stdout": result.stdout, "stderr": result.stderr}
