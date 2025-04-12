"""Tests for osupdates.py."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from neuralupgrade.filesystems import Filesystem, Filesystems
from neuralupgrade.osupdates import get_system_metadata

# Path to test scenario directories
TESTS_DIR = Path(__file__).parent
SCENARIOS_DIR = TESTS_DIR / "data" / "scenarios"
SCENARIO_AB_SAME = SCENARIOS_DIR / "ab_same"


class TestGetSystemVersions(unittest.TestCase):
    """Tests for get_system_versions function."""

    def setUp(self):
        """Set up test environment."""
        # Create a mock Filesystems object that uses our scenario test data
        a_fs = Filesystem("psyopsOS-A", mountpoint=SCENARIO_AB_SAME / "a", mockmount=True)
        b_fs = Filesystem("psyopsOS-B", mountpoint=SCENARIO_AB_SAME / "b", mockmount=True)
        efi_fs = Filesystem("PSYOPSOSEFI", mountpoint=SCENARIO_AB_SAME / "efisys", mockmount=True)
        self.filesystems_ab_same = Filesystems(efisys=efi_fs, a=a_fs, b=b_fs)

        self.temp_emtpy_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_emtpy_dir.cleanup)
        b_empty_fs = Filesystem("psyopsOS-B", mountpoint=self.temp_emtpy_dir.name, mockmount=True)
        self.filesystems_b_side_empty = Filesystems(efisys=efi_fs, a=a_fs, b=b_empty_fs)

    @patch("neuralupgrade.filesystems.activeside")
    def test_get_system_versions(self, mock_activeside: unittest.mock.MagicMock):
        """Test get_system_versions."""
        # Set up mock activeside to return A as the booted side
        mock_activeside.return_value = "psyopsOS-A"

        # Call the function
        result = get_system_metadata(self.filesystems_ab_same)

        # Verify the result
        self.assertEqual(result.booted_label, "psyopsOS-A")
        self.assertEqual(result.nonbooted_label, "psyopsOS-B")
        self.assertEqual(result.nextboot_label, "psyopsOS-A")

        # Check A side metadata
        self.assertEqual(result.a.metadata["type"], "psyopsOS")
        self.assertEqual(result.a.metadata["version"], "20240705-173840")
        self.assertEqual(result.a.metadata["kernel"], "6.6.36-0-lts")
        self.assertEqual(result.a.metadata["alpine"], "3.20")

        # Check B side data
        self.assertEqual(result.b.metadata["type"], "psyopsOS")
        self.assertEqual(result.b.metadata["version"], "20240705-173840")
        self.assertEqual(result.b.metadata["kernel"], "6.6.36-0-lts")
        self.assertEqual(result.b.metadata["alpine"], "3.20")

        # Check EFI data
        self.assertEqual(result.firmware.metadata["type"], "psyopsESP")
        self.assertEqual(result.firmware.metadata["version"], "20240705-173849")
        self.assertEqual(result.firmware.metadata["efi_programs"], "memtest64.efi,tcshell.efi")
        self.assertEqual(result.firmware.neuralupgrade_info["default_boot_label"], "psyopsOS-A")
        self.assertEqual(result.firmware.neuralupgrade_info["last_updated"], "20250308-040402")
        self.assertEqual(result.firmware.neuralupgrade_info["extra_programs"], "/memtest64.efi,/tcshell.efi")

    @patch("neuralupgrade.filesystems.activeside")
    def test_get_system_versions_missing_minisig(self, mock_activeside):
        """Test get_system_versions when a minisig file is missing."""
        # Set up mock activeside to return A as the booted side
        mock_activeside.return_value = "psyopsOS-A"

        # Call the function
        result = get_system_metadata(self.filesystems_b_side_empty)

        # Verify the error is captured in the result for the B side
        self.assertIn("error", result.b.metadata)
        self.assertTrue("missing minisig" in result.b.metadata["error"])


if __name__ == "__main__":
    unittest.main()
