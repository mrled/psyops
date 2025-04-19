"""Artifact prerequisites"""

import subprocess
import tarfile
import zipfile

from telekinesis.config import tkconfig
from telekinesis.rget import rget


def get_x64_ovmf():
    """Download the OVMF firmware image for qemu

    This is somewhat annoying as the project only provides outdated RPM files.

    TODO: we probably need to build this ourselves, unless Alpine packages it in some normal way in the future.
    """
    artifacts = tkconfig.arch_artifacts["x86_64"]
    rget(artifacts.ovmf_url, artifacts.ovmf_rpm)
    results = [
        artifacts.ovmf_extracted_code,
        artifacts.ovmf_extracted_vars,
        artifacts.uefishell_extracted_bin,
    ]
    if not all(result.exists() for result in results):
        in_container_rpm_path = f"/work/{artifacts.ovmf_rpm.name}"
        in_container_ovmf_extracted_path = f"/work/{artifacts.ovmf_extracted_path.name}"
        in_container_uefishell_iso_path = f"{in_container_ovmf_extracted_path}/{artifacts.uefishell_iso_relpath}"
        extract_rpm_script = " && ".join(
            [
                "apk add rpm2cpio 7zip",
                "mkdir -p /work/ovmf-extracted",
                "cd /work/ovmf-extracted",
                f"rpm2cpio {in_container_rpm_path} | cpio -idmv",
                f"7z x {in_container_uefishell_iso_path}",
                f"7z x {artifacts.uefishell_img_relpath}",
            ]
        )
        docker_run_cmd = [
            "docker",
            "run",
            "--rm",
            "--volume",
            f"{artifacts.archroot}:/work",
            "alpine:3.18",
            "sh",
            "-c",
            extract_rpm_script,
        ]
        subprocess.run(docker_run_cmd, check=True)


def get_x64_memtest():
    """Download and extract memtest binaries"""
    artifacts = tkconfig.arch_artifacts["x86_64"]
    # code to download memtest from memtest.org with requestslibrary:
    rget(
        "https://memtest.org/download/v6.20/mt86plus_6.20.binaries.zip",
        artifacts.memtest_zipfile,
    )
    if not artifacts.memtest64efi.exists():
        with zipfile.ZipFile(artifacts.memtest_zipfile, "r") as zip_ref:
            zip_ref.extract("memtest64.efi", artifacts.archroot)


def get_rpi_firmware():
    """Download the Raspberry Pi firmware"""
    artifacts = tkconfig.arch_artifacts["aarch64"]

    rget(artifacts.rpi_firmware_url, artifacts.rpi_firmware_tarball)
    with tarfile.open(artifacts.rpi_firmware_tarball, "r:xz") as tar:
        tar.extractall(artifacts.archroot)
