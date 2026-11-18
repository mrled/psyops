"""Run with Python and Ansible available on PYTHONPATH; no real accounts are modified."""

import base64
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import yaml


MODULE = Path(__file__).resolve().parents[1] / "roles/ssh_authorized_keys/library/ssh_authorized_keys_batch.py"
SPEC = importlib.util.spec_from_file_location("batch", MODULE)
batch = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(batch)
KEY = "ssh-ed25519 " + base64.b64encode(b"\0\0\0\x0bssh-ed25519\0\0\0\x20" + b"a" * 32).decode()


class BatchTests(unittest.TestCase):
    def run_module(self, homes, keys, check=False, header=None, diff=False):
        # Fake passwd lookups only; exercise the real AnsibleModule and filesystem helpers.
        script = f"""
import importlib.util, pwd
from types import SimpleNamespace
spec = importlib.util.spec_from_file_location('batch', {str(MODULE)!r})
batch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(batch)
homes = {homes!r}
pwd.getpwnam = lambda user: SimpleNamespace(pw_dir=homes[user], pw_uid={os.getuid()}, pw_gid={os.getgid()})
batch.main()
"""
        args = {"users": [{"user": name, "keys": value} for name, value in keys.items()], "_ansible_check_mode": check, "_ansible_diff": diff}
        if header is not None:
            args["header"] = header
        result = subprocess.run([sys.executable, "-c", script], input=json.dumps({"ANSIBLE_MODULE_ARGS": args}),
                                text=True, capture_output=True)
        self.assertTrue(result.stdout, result.stderr)
        return json.loads(result.stdout)

    def test_batch_idempotency_permissions_empty_and_check_mode(self):
        with tempfile.TemporaryDirectory() as root:
            homes = {name: str(Path(root) / name) for name in ("alice", "bob")}
            keys = {"alice": [KEY], "bob": []}
            self.assertTrue(self.run_module(homes, keys, check=True)["changed"])
            self.assertFalse(Path(homes["alice"]).exists())
            result = self.run_module(homes, keys)
            self.assertNotIn("failed", result, result)
            self.assertTrue(result["changed"])
            for name, values in keys.items():
                directory = Path(homes[name]) / ".ssh"
                path = directory / "authorized_keys"
                self.assertEqual(path.read_text(), "# Ansible managed\n" + "".join(k + "\n" for k in values))
                self.assertEqual(directory.stat().st_mode & 0o777, 0o700)
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertFalse(self.run_module(homes, keys)["changed"])
            keys["alice"] = []
            self.assertTrue(self.run_module(homes, keys, check=True)["changed"])
            self.assertIn(KEY, (Path(homes["alice"]) / ".ssh/authorized_keys").read_text())
            self.assertTrue(self.run_module(homes, keys)["changed"])

    def test_diff_mode(self):
        with tempfile.TemporaryDirectory() as root:
            homes = {name: str(Path(root) / name) for name in ("alice", "bob")}
            keys = {name: [KEY] for name in homes}
            result = self.run_module(homes, keys, check=True, diff=True)
            self.assertNotIn("failed", result, result)
            self.assertEqual(len(result["diff"]), 2)
            for change, home in zip(result["diff"], homes.values()):
                self.assertEqual(change["before_header"], str(Path(home) / ".ssh/authorized_keys"))
                self.assertEqual(change["before"], "")
                self.assertEqual(change["after"], "# Ansible managed\n" + KEY + "\n")
                self.assertFalse(Path(home).exists())
            applied = self.run_module(homes, keys, diff=True)
            self.assertEqual(applied["diff"], result["diff"])
            self.assertEqual(self.run_module(homes, keys, diff=True)["diff"], [])
            self.assertNotIn("diff", self.run_module(homes, keys))
            path = Path(homes["alice"]) / ".ssh/authorized_keys"
            path.chmod(0o644)
            permissions = self.run_module(homes, keys, check=True, diff=True)
            self.assertTrue(permissions["changed"])
            self.assertEqual(permissions["diff"][0]["before"]["mode"], "0644")
            self.assertEqual(permissions["diff"][0]["after"]["mode"], "0600")
            self.assertEqual(path.stat().st_mode & 0o777, 0o644)
            keys["alice"] = []
            removed = self.run_module(homes, keys, check=True, diff=True)
            self.assertEqual(removed["diff"][0]["before"], "# Ansible managed\n" + KEY + "\n")
            self.assertEqual(removed["diff"][0]["after"], "# Ansible managed\n")
            self.assertIn(KEY, path.read_text())

    def test_custom_and_empty_headers(self):
        with tempfile.TemporaryDirectory() as home:
            path = Path(home) / ".ssh/authorized_keys"
            for header, expected in (("Custom header\nSecond line", "# Custom header\n# Second line\n"), ("", "")):
                with self.subTest(header=header):
                    result = self.run_module({"alice": home}, {"alice": [KEY]}, header=header)
                    self.assertNotIn("failed", result, result)
                    self.assertEqual(path.read_text(), expected + KEY + "\n")
                    self.assertFalse(self.run_module({"alice": home}, {"alice": [KEY]}, header=header)["changed"])

    def test_invalid_batch_writes_nothing(self):
        with tempfile.TemporaryDirectory() as home:
            result = self.run_module({"alice": home, "bob": home}, {"alice": [KEY], "bob": ["bad key"]})
            self.assertTrue(result["failed"])
            self.assertIn("Invalid key 1 for bob", result["msg"])
            self.assertFalse((Path(home) / ".ssh").exists())

    def test_symlinks_are_rejected(self):
        for link_directory in (True, False):
            with self.subTest(directory=link_directory), tempfile.TemporaryDirectory() as home:
                directory = Path(home) / ".ssh"
                target = Path(home) / "target"
                if link_directory:
                    target.mkdir()
                    directory.symlink_to(target)
                else:
                    directory.mkdir()
                    target.write_text("untouched")
                    (directory / "authorized_keys").symlink_to(target)
                result = self.run_module({"alice": home}, {"alice": [KEY]})
                self.assertTrue(result["failed"])
                if link_directory:
                    self.assertEqual(list(target.iterdir()), [])
                else:
                    self.assertEqual(target.read_text(), "untouched")

    def test_inventory_keys_including_security_keys(self):
        inventory = MODULE.parents[3] / "group_vars/all/main.yml"
        keys = yaml.safe_load(inventory.read_text())["global_personal_ssh_keys"]
        for key in keys:
            with self.subTest(key_type=key.split()[0]):
                batch.validate_key(key)
        with tempfile.TemporaryDirectory() as home:
            result = self.run_module({"alice": home}, {"alice": keys}, check=True)
            self.assertNotIn("failed", result, result)
            self.assertTrue(result["changed"])
            self.assertFalse((Path(home) / ".ssh").exists())
            result = self.run_module({"alice": home}, {"alice": keys})
            self.assertNotIn("failed", result, result)
            self.assertEqual((Path(home) / ".ssh/authorized_keys").read_text(),
                             "# Ansible managed\n" + "".join(key + "\n" for key in keys))

    def test_validation(self):
        batch.validate_key(KEY + " user@example")
        for key in ("bad", "ssh-ed25519 !!!", KEY.replace("ssh-ed25519", "ssh-rsa", 1), KEY + "\n", 'restrict ' + KEY):
            with self.subTest(key=key), self.assertRaises(ValueError):
                batch.validate_key(key)


if __name__ == "__main__":
    unittest.main()
