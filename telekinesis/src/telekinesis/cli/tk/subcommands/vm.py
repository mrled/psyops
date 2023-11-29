"""The vm subcommand"""

import subprocess
import sys

from telekinesis.config import tkconfig
from telekinesis.rget import rget


def get_ovmf():
    """Download the OVMF firmware image for qemu

    This is somewhat annoying as the project only provides outdated RPM files.

    TODO: we probably need to build this ourselves, unless Alpine packages it in some normal way in the future.
    """
    rget(tkconfig.ovmf.url, tkconfig.ovmf.artifact)
    if not tkconfig.ovmf.extracted_code.exists() or not tkconfig.ovmf.extracted_vars.exists():
        in_container_rpm_path = f"/work/{tkconfig.ovmf.artifact.name}"
        extract_rpm_script = " && ".join(
            [
                "apk add rpm2cpio",
                "mkdir -p /work/ovmf-extracted",
                "cd /work/ovmf-extracted",
                f"rpm2cpio {in_container_rpm_path} | cpio -idmv",
            ]
        )
        docker_run_cmd = [
            "docker",
            "run",
            "--rm",
            "--volume",
            f"{tkconfig.repopaths.artifacts}:/work",
            "alpine:3.18",
            "sh",
            "-c",
            extract_rpm_script,
        ]
        subprocess.run(docker_run_cmd, check=True)


def vm_grubusb():
    """Run the grubusb image in qemu"""
    get_ovmf()
    subprocess.run(
        [
            "qemu-system-x86_64",
            "-nic",
            "user",
            "-serial",
            "stdio",
            # "-display",
            # "none",
            "-m",
            "2048",
            "-drive",
            f"if=pflash,format=raw,readonly=on,file={tkconfig.ovmf.extracted_code.as_posix()}",
            "-drive",
            f"if=pflash,format=raw,file={tkconfig.ovmf.extracted_vars.as_posix()}",
            "-drive",
            f"format=raw,file={tkconfig.artifacts.grubusbimg.as_posix()}",
        ],
        check=True,
        stdin=sys.stdin,
        stdout=sys.stdout,
        stderr=sys.stderr,
    )
