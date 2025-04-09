"""Helpers for dealing with aports"""

from pathlib import Path
import subprocess


def validate_alpine_version(docker_builder_dir: Path, aportsdir: Path, alpine_version: str):
    """Validate that the alpine version matches what we check out in aports and what is in build/Dockerfile."""

    dockerfile = docker_builder_dir / "Dockerfile"
    dockerfile_alpine_version = None
    with dockerfile.open("r") as f:
        for line in f.readlines():
            if line.startswith("FROM alpine:"):
                dockerfile_alpine_version = line.split(":")[1]
                break
    if dockerfile_alpine_version is None:
        raise Exception(f"Could not find alpine version in Dockerfile: {dockerfile}")

    cmd = ["git", "name-rev", "--name-only", "HEAD"]
    gitresult = subprocess.run(cmd, cwd=aportsdir.as_posix(), capture_output=True)
    if gitresult.returncode != 0:
        cmdstr = " ".join(cmd)
        err = f"Trying to get version of aports repository at {aportsdir}, with '{cmdstr}' but got an error: {gitresult.stderr.decode('utf-8')}"
        raise Exception(err)
    aports_alpine_version = gitresult.stdout.decode("utf-8").strip()

    errors = []

    if alpine_version not in dockerfile_alpine_version:
        errors.append(
            f"Alpine version in Dockerfile ({dockerfile_alpine_version}) does not match alpine_version ({alpine_version})"
        )
    if alpine_version not in aports_alpine_version:
        errors.append(
            f"Alpine version in aports ({aports_alpine_version}) does not match alpine_version ({alpine_version})"
        )

    if errors:
        raise Exception("Alpine version mismatch: " + "\n".join(errors))
    print(f"Validated that the Dockerfile and the aports checkout are both Alpine v{alpine_version}")
