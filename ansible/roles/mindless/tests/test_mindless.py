"""Run with: python -m unittest discover -s roles/mindless/tests"""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

import jinja2
import yaml

ROLE = Path(__file__).resolve().parents[1]
QUADLET = Path("/usr/libexec/podman/quadlet")


class QuadletIntegration(unittest.TestCase):
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
