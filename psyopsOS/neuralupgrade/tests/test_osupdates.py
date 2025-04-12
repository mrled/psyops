"""Tests for osupdates.py."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from neuralupgrade.filesystems import Filesystem, Filesystems
from neuralupgrade.osupdates import get_system_versions

# Path to test scenario directories
TESTS_DIR = Path(__file__).parent
SCENARIOS_DIR = TESTS_DIR / "data" / "scenarios"
SCENARIO_AB_SAME = SCENARIOS_DIR / "ab_same"


class MockMount:
    """Mock Mount context manager."""

    def __init__(self, path):
        self.path = path

    def __enter__(self):
        return self.path

    def __exit__(self, exc_type, exc_value, traceback):
        pass


class MockFilesystem(Filesystem):
    """Mock Filesystem for testing."""

    def __init__(self, label, scenario_path):
        super().__init__(label=label, device=f"/dev/fake/{label}", mountpoint=f"/mnt/{label}")
        self.scenario_path = scenario_path

    def mount(self, writable=False):
        """Override mount to return a context manager that returns the scenario path."""
        return MockMount(self.scenario_path)


class TestGetSystemVersions(unittest.TestCase):
    """Tests for get_system_versions function."""

    def setUp(self):
        """Set up test environment."""
        # Create a mock Filesystems object that uses our scenario test data
        a_fs = MockFilesystem("psyopsOS-A", SCENARIO_AB_SAME / "a")
        b_fs = MockFilesystem("psyopsOS-B", SCENARIO_AB_SAME / "b")
        efi_fs = MockFilesystem("PSYOPSOSEFI", SCENARIO_AB_SAME / "efisys")
        self.filesystems_ab_same = Filesystems(efisys=efi_fs, a=a_fs, b=b_fs)

        self.temp_emtpy_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_emtpy_dir.cleanup)
        b_empty_fs = MockFilesystem("psyopsOS-B", self.temp_emtpy_dir.name)
        self.filesystems_b_side_empty = Filesystems(efisys=efi_fs, a=a_fs, b=b_empty_fs)

    @patch("neuralupgrade.filesystems.activeside")
    def test_get_system_versions(self, mock_activeside):
        """Test get_system_versions."""
        # Set up mock activeside to return A as the booted side
        mock_activeside.return_value = "psyopsOS-A"

        # Call the function
        result = get_system_versions(self.filesystems_ab_same)

        # Verify the result
        self.assertEqual(result["booted"], "psyopsOS-A")
        self.assertEqual(result["nonbooted"], "psyopsOS-B")

        # Check A side data
        self.assertTrue(result["psyopsOS-A"]["running"])
        self.assertEqual(result["psyopsOS-A"]["type"], "psyopsOS")
        self.assertEqual(result["psyopsOS-A"]["version"], "20240705-173840")
        self.assertEqual(result["psyopsOS-A"]["kernel"], "6.6.36-0-lts")
        self.assertEqual(result["psyopsOS-A"]["alpine"], "3.20")

        # Check B side data
        self.assertFalse(result["psyopsOS-B"]["running"])
        self.assertEqual(result["psyopsOS-B"]["type"], "psyopsOS")
        self.assertEqual(result["psyopsOS-B"]["version"], "20240705-173840")
        self.assertEqual(result["psyopsOS-B"]["kernel"], "6.6.36-0-lts")
        self.assertEqual(result["psyopsOS-B"]["alpine"], "3.20")

        import pprint

        pprint.pprint(result)

        # Check EFI data
        self.assertEqual(result["efisys"]["default_boot_label"], "psyopsOS-A")
        self.assertEqual(result["efisys"]["last_updated"], "20250308-040402")
        self.assertEqual(result["efisys"]["extra_programs"], "/memtest64.efi,/tcshell.efi")

        # Since default_boot_label is psyopsOS-A, it should be marked as next_boot
        self.assertTrue(result["psyopsOS-A"]["next_boot"])
        self.assertFalse(result["psyopsOS-B"]["next_boot"])

    @patch("neuralupgrade.filesystems.activeside")
    def test_get_system_versions_missing_minisig(self, mock_activeside):
        """Test get_system_versions when a minisig file is missing."""
        # Set up mock activeside to return A as the booted side
        mock_activeside.return_value = "psyopsOS-A"

        # Call the function
        result = get_system_versions(self.filesystems_b_side_empty)

        # Verify the error is captured in the result for the B side
        self.assertIn("error", result["psyopsOS-B"])
        self.assertTrue("missing minisig" in result["psyopsOS-B"]["error"])


if __name__ == "__main__":
    unittest.main()
