#!/usr/bin/python
"""Compare and TPM-seal credentials, leaving directory management to Ansible."""

import os
import pwd
import subprocess
import tempfile
from collections.abc import Mapping
from typing import Any, Protocol, TypedDict, cast

from ansible.module_utils.basic import AnsibleModule

DOCUMENTATION = r"""
---
module: urestic_credentials
short_description: Seal changed credentials with the local TPM
author: Psyops maintainers
description:
  - Runs as root and requires systemd-creds 256 or newer and a usable TPM2 device.
  - User-scoped credentials require the credential broker systemd-creds.socket
    for an unprivileged service manager; the role handles this prerequisite.
  - Encryption requires both the host key and TPM2; there is no non-TPM fallback.
  - The caller must create mode 0700 parent directories owned by the specified
    user with ansible.builtin.file before invoking this module.
  - Existing credentials are decrypted and compared as exact UTF-8 bytes.
    A decryption failure is fatal and never triggers replacement.
  - Only ciphertext is written to disk, in a mode 0600 temporary file in the
    destination directory, then atomically moved into place with mode 0600,
    owned by the specified user and their primary group.
  - Replacements are atomic per credential, not transactional across jobs.
  - Check mode decrypts existing credentials and predicts changes without writes.
    Absent credentials need neither an existing parent nor systemd-creds in check mode.
options:
  user:
    description: User whose scope, ownership, and primary group the credentials use.
    type: str
    required: true
  jobs:
    description: Jobs with existing private credential directories.
    type: list
    elements: dict
    default: []
    suboptions:
      credential_directory:
        description: Existing absolute mode 0700 directory owned by the specified user.
        type: str
        required: true
      credentials:
        description: Mapping of single-basename credential names to secret strings.
        type: dict
        required: true
  tpm2_pcrs:
    description: PCR selection passed to systemd-creds encrypt.
    type: str
    default: '7'
attributes:
  check_mode:
    support: full
    description: Reads and decrypts but never writes or encrypts.
"""

EXAMPLES = r"""
- name: Seal backup credentials in an already provisioned directory
  urestic_credentials:
    user: alice
    jobs:
      - credential_directory: /home/alice/.config/psyops/backup/home/credentials
        credentials:
          restic-password: "{{ vault_restic_password }}"
    tpm2_pcrs: '7'
"""

RETURN = r"""
changed:
  description: Whether ciphertext or its metadata changed (or would change).
  type: bool
  returned: success
"""


class CredentialError(Exception):
    """A sanitized error safe to return to Ansible."""


class Job(TypedDict):
    """A provisioned credential directory and the plaintext secrets to seal there."""

    credential_directory: str
    credentials: dict[str, str]


class Parameters(TypedDict):
    """Validated Ansible arguments for the credential batch and its TPM PCR policy."""

    user: str
    jobs: list[Job]
    tpm2_pcrs: str


class AnsibleModuleSubset(Protocol):
    """The subset of AnsibleModule used to manage encrypted credential outputs."""

    @property
    def params(self) -> Mapping[str, object]:
        """Return arguments validated by Ansible's argument specification."""
        ...

    check_mode: bool

    def load_file_common_arguments(self, params: dict[str, Any]) -> dict[str, Any]:
        """Prepare file metadata arguments using Ansible's standard handling."""
        ...

    def set_fs_attributes_if_different(self, file_args: dict[str, Any], changed: bool) -> bool:
        """Reconcile metadata, honoring check mode and preserving earlier changes."""
        ...

    def atomic_move(
        self, src: str, dest: str, *, unsafe_writes: bool, keep_dest_attrs: bool
    ) -> None:
        """Atomically install a ciphertext file using Ansible's file replacement API."""
        ...


class Credentials:
    """Compare and seal a batch of credentials without staging plaintext on disk."""

    def __init__(self, module: AnsibleModuleSubset):
        """Bind the Ansible filesystem interface, validated arguments, and check mode."""
        self.module = module
        self.params = cast(Parameters, module.params)

    @staticmethod
    def run(args: list[str], *, input: bytes | None = None) -> bytes:
        """Return command stdout or raise a sanitized error without leaking secrets."""
        try:
            result = subprocess.run(
                args, input=input, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False
            )
        except (OSError, subprocess.SubprocessError):
            raise CredentialError(
                "Credential command could not run; diagnostics suppressed."
            ) from None
        if result.returncode:
            raise CredentialError("Credential command failed; diagnostics suppressed.")
        return result.stdout

    def encrypt(self, path: str, name: str, secret: bytes) -> None:
        """TPM-seal secret bytes through stdin and atomically install the ciphertext.

        The destination directory must already exist. Temporary ciphertext is
        removed on failure; existing output is replaced only after sealing succeeds.
        """
        fd, temporary = tempfile.mkstemp(prefix=".urestic-", dir=os.path.dirname(path))
        os.close(fd)
        try:
            self.run(
                [
                    "systemd-creds",
                    "encrypt",
                    "--name=" + name,
                    "--uid=" + self.params["user"],
                    "--with-key=host+tpm2",
                    "--tpm2-device=auto",
                    "--tpm2-pcrs=" + self.params["tpm2_pcrs"],
                    "-",
                    temporary,
                ],
                input=secret,
            )
            # systemd-creds writes only ciphertext; never stage plaintext on disk.
            os.chmod(temporary, 0o600)
            try:
                self.module.atomic_move(temporary, path, unsafe_writes=False, keep_dest_attrs=False)
            except Exception:
                # Ansible's atomic_move can raise plain Exception on rename failures.
                raise CredentialError("Atomic credential replacement failed.") from None
        finally:
            if os.path.lexists(temporary):
                os.unlink(temporary)

    def apply(self) -> dict[str, bool]:
        """Reconcile credentials while translating operational errors to safe messages."""
        try:
            return self._apply()
        except (OSError, ValueError, KeyError):
            raise CredentialError("Credential operation failed; diagnostics suppressed.") from None

    def _apply(self) -> dict[str, bool]:
        """Compare plaintext, seal differences, and enforce user-private ciphertext metadata.

        Check mode predicts changes without writing. Existing ciphertext must
        decrypt successfully before comparison; a decryption failure stops the batch.
        """
        group = str(pwd.getpwnam(self.params["user"]).pw_gid)
        changed = False
        for job in self.params["jobs"]:
            for name, secret in job["credentials"].items():
                path = os.path.join(job["credential_directory"], name)
                different = True
                if os.path.lexists(path):
                    plaintext = self.run(
                        [
                            "systemd-creds",
                            "decrypt",
                            "--name=" + name,
                            "--uid=" + self.params["user"],
                            path,
                            "-",
                        ]
                    )
                    different = plaintext != secret.encode("utf-8")
                if different:
                    changed = True
                    if self.module.check_mode:
                        continue
                    self.encrypt(path, name, secret.encode("utf-8"))
                file_args = self.module.load_file_common_arguments(
                    dict(
                        path=path, owner=self.params["user"], group=group, mode="0600", follow=False
                    )
                )
                changed = self.module.set_fs_attributes_if_different(file_args, changed)
        return dict(changed=changed)


def main() -> None:
    """Define Ansible arguments, protect secret values, and return the batch result."""
    module = AnsibleModule(
        argument_spec=dict(
            user=dict(type="str", required=True),
            jobs=dict(
                type="list",
                elements="dict",
                default=[],
                options=dict(
                    credential_directory=dict(type="str", required=True),
                    credentials=dict(type="dict", required=True, no_log=True),
                ),
            ),
            tpm2_pcrs=dict(type="str", default="7"),
        ),
        supports_check_mode=True,
    )
    try:
        result = Credentials(module).apply()
    except CredentialError as error:
        module.fail_json(msg=str(error))
        return
    module.exit_json(**result)


if __name__ == "__main__":
    main()
