"""Focused tests for TPM-sealed credentials without a local TPM."""

import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from roles.urestic.library import urestic_credentials as credentials


class FakeModule:
    """Model Ansible file operations and record calls without requiring root."""

    def __init__(self, params: credentials.Parameters, check_mode: bool = False):
        """Store module inputs and initialize file-operation records."""
        self.params = params
        self.check_mode = check_mode
        self.moves: list[tuple[str, str, bool, bool]] = []
        self.attributes: list[dict[str, object]] = []

    def load_file_common_arguments(self, params):
        """Record requested file attributes and return them unchanged."""
        self.attributes.append(params)
        return params

    def set_fs_attributes_if_different(self, file_args, changed):
        """Detect mode changes and apply them only outside check mode."""
        path = file_args["path"]
        different = stat.S_IMODE(os.stat(path).st_mode) != 0o600
        # Stand in for root ownership on unprivileged test hosts.
        if different and not self.check_mode:
            os.chmod(path, 0o600)
        return changed or different

    def atomic_move(self, src, dest, *, unsafe_writes, keep_dest_attrs):
        """Record and perform atomic replacement, rejecting check-mode writes."""
        assert not self.check_mode
        self.moves.append((src, dest, unsafe_writes, keep_dest_attrs))
        os.replace(src, dest)


class CredentialsTests(unittest.TestCase):
    """Verify credential updates, check mode, and failure safety with fake sealing."""

    def setUp(self):
        """Create an isolated credential directory and intercept sealing commands."""
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)
        self.path = self.directory / "password"
        self.params: credentials.Parameters = {
            "jobs": [
                {"credential_directory": str(self.directory), "credentials": {"password": "secret"}}
            ],
            "tpm2_pcrs": "7",
        }
        self.calls: list[tuple[list[str], dict]] = []
        self.failure: str | None = None
        runner = patch.object(credentials.subprocess, "run", side_effect=self.run_command)
        runner.start()
        self.addCleanup(runner.stop)

    def run_command(self, args, **kwargs):
        """Simulate sealing commands, checking temporary-file modes and injecting failures."""
        self.calls.append((args, kwargs))
        if args[1] == "decrypt":
            output = Path(args[-2]).read_bytes().removeprefix(b"sealed:")
        else:
            self.assertEqual(stat.S_IMODE(Path(args[-1]).stat().st_mode), 0o600)
            Path(args[-1]).write_bytes(b"sealed:" + kwargs["input"])
            output = b""
        return subprocess.CompletedProcess(
            args, 1 if args[1] == self.failure else 0, stdout=output, stderr=b"secret"
        )

    def apply(self, check=False):
        """Apply the current parameters and return the result and fake module."""
        module = FakeModule(self.params, check)
        return credentials.Credentials(module).apply(), module

    def test_idempotence_and_atomic_ciphertext(self):
        """Initial sealing uses a private atomic move; unchanged secrets only decrypt."""
        result, module = self.apply()
        self.assertEqual(result, {"changed": True})
        self.assertEqual(self.path.read_bytes(), b"sealed:secret")
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o600)
        src, dest, unsafe, keep = module.moves[0]
        self.assertEqual(Path(src).parent, self.directory)
        self.assertEqual(dest, str(self.path))
        self.assertFalse(unsafe)
        self.assertFalse(keep)
        self.calls.clear()
        self.assertEqual(self.apply()[0], {"changed": False})
        self.assertEqual([args[1] for args, _ in self.calls], ["decrypt"])
        self.assertEqual(list(self.directory.iterdir()), [self.path])

    def test_changed_secret_pcr_and_stdin(self):
        """Changed secrets use stdin and the requested TPM options without exposing stderr."""
        self.apply()
        self.params["jobs"][0]["credentials"]["password"] = "new-secret"
        self.params["tpm2_pcrs"] = "7+11"
        self.assertTrue(self.apply()[0]["changed"])
        args, kwargs = self.calls[-1]
        for option in (
            "--name=password",
            "--with-key=tpm2",
            "--tpm2-device=auto",
            "--tpm2-pcrs=7+11",
        ):
            self.assertIn(option, args)
        self.assertNotIn("new-secret", " ".join(args))
        self.assertEqual(kwargs["input"], b"new-secret")
        self.assertEqual(kwargs["stderr"], subprocess.DEVNULL)

    def test_check_absent_needs_no_command_or_parent_directory(self):
        """Check mode reports missing credentials without commands or filesystem writes."""
        missing = self.directory / "missing"
        self.params["jobs"][0]["credential_directory"] = str(missing)
        with (
            patch.object(credentials.subprocess, "run", side_effect=FileNotFoundError("secret")),
            patch.object(credentials.tempfile, "mkstemp", side_effect=AssertionError("write")),
        ):
            self.assertTrue(self.apply(check=True)[0]["changed"])
        self.assertFalse(missing.exists())
        self.assertEqual(self.calls, [])

    def test_check_existing_compares_without_writing(self):
        """Check mode decrypts existing credentials to detect changes without writing."""
        self.apply()
        self.calls.clear()
        with patch.object(credentials.tempfile, "mkstemp", side_effect=AssertionError("write")):
            self.assertFalse(self.apply(check=True)[0]["changed"])
            self.params["jobs"][0]["credentials"]["password"] = "other"
            self.assertTrue(self.apply(check=True)[0]["changed"])
        self.assertEqual(self.path.read_bytes(), b"sealed:secret")
        self.assertEqual([args[1] for args, _ in self.calls], ["decrypt", "decrypt"])

    def test_undecryptable_never_overwrites_even_in_check_mode(self):
        """Decryption failures preserve ciphertext and hide secrets in both modes."""
        self.apply()
        self.failure = "decrypt"
        self.params["jobs"][0]["credentials"]["password"] = "other"
        for check in (False, True):
            with self.assertRaises(credentials.CredentialError) as error:
                self.apply(check)
            self.assertNotIn("secret", str(error.exception))
            self.assertEqual(self.path.read_bytes(), b"sealed:secret")
        self.assertEqual(list(self.directory.iterdir()), [self.path])

    def test_failed_encryption_cleans_partial_ciphertext(self):
        """Encryption failures remove partial files and preserve any existing credential."""
        self.failure = "encrypt"
        with self.assertRaises(credentials.CredentialError):
            self.apply()
        self.assertEqual(list(self.directory.iterdir()), [])
        self.failure = None
        self.apply()
        self.failure = "encrypt"
        self.params["jobs"][0]["credentials"]["password"] = "other"
        with self.assertRaises(credentials.CredentialError):
            self.apply()
        self.assertEqual(self.path.read_bytes(), b"sealed:secret")
        self.assertEqual(list(self.directory.iterdir()), [self.path])

    def test_atomic_move_failure_cleans_temp_and_preserves_existing(self):
        """Failed replacement preserves ciphertext, removes temporary files, and hides secrets."""
        self.apply()
        self.params["jobs"][0]["credentials"]["password"] = "other"
        with patch.object(FakeModule, "atomic_move", side_effect=Exception("secret")):
            with self.assertRaises(credentials.CredentialError) as error:
                self.apply()
        self.assertNotIn("secret", str(error.exception))
        self.assertEqual(self.path.read_bytes(), b"sealed:secret")
        self.assertEqual(list(self.directory.iterdir()), [self.path])

    def test_command_exceptions_are_sanitized(self):
        """Command exceptions hide secret details and causes, leaving no temporary files."""
        for error in (FileNotFoundError("secret"), subprocess.CalledProcessError(1, "secret")):
            with patch.object(credentials.subprocess, "run", side_effect=error):
                with self.assertRaises(credentials.CredentialError) as caught:
                    self.apply()
            self.assertNotIn("secret", str(caught.exception))
            self.assertIsNone(caught.exception.__cause__)
            self.assertEqual(list(self.directory.iterdir()), [])
        self.apply()
        with patch.object(credentials.subprocess, "run", side_effect=FileNotFoundError("secret")):
            with self.assertRaises(credentials.CredentialError):
                self.apply(check=True)

    def test_multiple_jobs_accumulate_changes(self):
        """A new job contributes a change even when an earlier job is unchanged."""
        self.apply()
        self.params["jobs"].append(
            {"credential_directory": str(self.directory), "credentials": {"token": "second"}}
        )
        self.assertTrue(self.apply()[0]["changed"])
        self.assertFalse(self.apply()[0]["changed"])
        self.assertEqual((self.directory / "token").read_bytes(), b"sealed:second")
        self.params["jobs"][0]["credentials"]["password"] = "rotated"
        self.assertTrue(self.apply()[0]["changed"])

    def test_secret_redaction(self):
        """Credential arguments are marked no_log without inspecting the rest of the schema."""
        with patch.object(credentials, "AnsibleModule") as constructor:
            module = constructor.return_value
            module.params = {"jobs": [], "tpm2_pcrs": "7"}
            module.check_mode = False
            credentials.main()
        spec = constructor.call_args.kwargs["argument_spec"]
        self.assertTrue(spec["jobs"]["options"]["credentials"]["no_log"])
        module.exit_json.assert_called_once_with(changed=False)


if __name__ == "__main__":
    unittest.main()
