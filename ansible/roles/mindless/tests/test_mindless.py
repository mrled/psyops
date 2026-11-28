"""Run with: python -m unittest discover -s roles/mindless/tests"""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

import jinja2
import yaml

ROLE = Path(__file__).resolve().parents[1]
QUADLET = Path("/usr/libexec/podman/quadlet")


class SecretConfiguration(unittest.TestCase):
    def render(self, token):
        values = yaml.safe_load((ROLE / "defaults/main.yml").read_text())
        values.update(
            mindless_1password_service_account_token=token,
            mindless_container_uid="1234",
            mindless_container_gid="2345",
        )
        return jinja2.Environment(undefined=jinja2.StrictUndefined).from_string(
            (ROLE / "templates/mindless.container.j2").read_text()
        ).render(**values)

    def test_secret_uses_image_identity_and_is_not_a_bind_mount(self):
        rendered = self.render("sensitive-token")
        self.assertIn(
            "Secret=mindless-1password-service-account-token,"
            "target=/etc/mindless/secrets/1password-service-account-token,"
            "uid=1234,gid=2345,mode=0400", rendered
        )
        self.assertNotIn("Volume=/etc/mindless/secrets", rendered)
        self.assertNotIn("sensitive-token", rendered)

    def test_empty_token_omits_secret(self):
        rendered = self.render("")
        self.assertNotIn("Secret=", rendered)
        self.assertNotIn("Volume=/etc/mindless/secrets", rendered)

    def test_secret_update_is_private_and_only_runs_for_new_or_changed_data(self):
        tasks = yaml.safe_load((ROLE / "tasks/main.yml").read_text())
        build = next(task for task in tasks if task["name"] == "Build rootless container image")
        secret = next(task for task in build["block"]
                      if task["name"] == "Configure rootless container secret")
        inspect = next(task for task in secret["block"]
                       if task["name"] == "Inspect managed secret data")
        update = next(task for task in secret["block"]
                      if task["name"] == "Create or rotate managed secret")
        for task in (inspect, update):
            self.assertTrue(task["no_log"])
            self.assertFalse(task["diff"])
        command = update["ansible.builtin.command"]
        self.assertEqual(command["argv"], [
            "podman", "secret", "create", "--replace",
            "mindless-1password-service-account-token", "-",
        ])
        self.assertEqual(command["stdin"], "{{ mindless_1password_service_account_token }}")
        self.assertFalse(command["stdin_add_newline"])
        env = jinja2.Environment(undefined=jinja2.StrictUndefined)
        env.filters["from_json"] = json.loads
        condition = env.compile_expression(update["when"])
        for rc, current, desired, expected in (
            (1, None, "new", True),
            (0, "same", "same", False),
            (0, "old", "new", True),
            (0, "new\\n", "new", True),
        ):
            with self.subTest(rc=rc, current=current):
                self.assertEqual(condition(
                    mindless_secret_exists={"rc": rc},
                    mindless_secret_inspect={} if rc else {
                        "stdout": json.dumps([{"SecretData": current}])
                    },
                    mindless_1password_service_account_token=desired,
                ), expected)

    def test_legacy_cleanup_follows_service_start_and_only_removes_managed_files(self):
        tasks = yaml.safe_load((ROLE / "tasks/main.yml").read_text())
        start = next(i for i, task in enumerate(tasks)
                     if task["name"] == "Start developer container")
        cleanup = next(i for i, task in enumerate(tasks)
                       if task["name"] == "Remove legacy managed secret files")
        self.assertGreater(cleanup, start)
        self.assertEqual(tasks[cleanup]["ansible.builtin.file"]["state"], "absent")
        self.assertEqual(tasks[cleanup]["loop"], [
            "/etc/mindless/secrets/README",
            "/etc/mindless/secrets/1password-service-account-token",
        ])


class QuadletIntegration(unittest.TestCase):
    @unittest.skipUnless(QUADLET.is_file(), "Podman Quadlet generator unavailable")
    def test_generates_secret_mount_with_container_ids(self):
        rendered = SecretConfiguration().render("sensitive-token")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "source", root / "output"
            source.mkdir()
            output.mkdir()
            (source / "mindless.container").write_text(rendered)
            subprocess.run(
                [str(QUADLET), "--user", str(output)],
                env=dict(os.environ, QUADLET_UNIT_DIRS=str(source)),
                check=True, capture_output=True, text=True,
            )
            unit = (output / "mindless.service").read_text()
            self.assertIn(
                "--secret mindless-1password-service-account-token,"
                "target=/etc/mindless/secrets/1password-service-account-token,"
                "uid=1234,gid=2345,mode=0400", unit
            )
            self.assertNotIn("sensitive-token", unit)

    @unittest.skipUnless(QUADLET.is_file(), "Podman Quadlet generator unavailable")
    def test_generates_boot_service_with_firewall_dependency(self):
        values = yaml.safe_load((ROLE / "defaults/main.yml").read_text())
        template = jinja2.Environment(undefined=jinja2.StrictUndefined).from_string(
            (ROLE / "templates/mindless.container.j2").read_text()
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "source", root / "output"
            source.mkdir()
            output.mkdir()
            (source / "mindless.container").write_text(template.render(**values))
            subprocess.run(
                [str(QUADLET), "--user", str(output)],
                env=dict(os.environ, QUADLET_UNIT_DIRS=str(source)),
                check=True,
                capture_output=True,
                text=True,
            )
            unit = (output / "mindless.service").read_text()
            # Both edges are needed: stop propagation alone does not order teardown.
            for relation in ("BindsTo", "After"):
                dependencies = " ".join(
                    line.partition("=")[2]
                    for line in unit.splitlines()
                    if line.startswith(relation + "=")
                ).split()
                self.assertIn("mindless-firewall.service", dependencies)
            self.assertEqual(
                (output / "default.target.wants/mindless.service").resolve(),
                output / "mindless.service",
            )


if __name__ == "__main__":
    unittest.main()
