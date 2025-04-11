"""Tests for update_metadata.py."""

import os
import tempfile
import textwrap
import unittest
from pathlib import Path

from neuralupgrade.update_metadata import parse_trusted_comment, parse_psyopsOS_neuralupgrade_info_comment

# Path to test scenario directories
TESTS_DIR = Path(__file__).parent
SCENARIOS_DIR = TESTS_DIR / "data" / "scenarios"
SCENARIO_AB_SAME = SCENARIOS_DIR / "ab_same"


class TestParseTrustedComment(unittest.TestCase):
    """Tests for parse_trusted_comment function."""

    def test_parse_comment_string(self):
        """Test parsing a trusted comment directly."""
        comment = "trusted comment: type=psyopsOS filename=psyopsOS.20240129-155151.tar version=20240129-155151 kernel=6.1.75-0-lts alpine=3.18"
        result = parse_trusted_comment(comment=comment)
        self.assertEqual(result["type"], "psyopsOS")
        self.assertEqual(result["filename"], "psyopsOS.20240129-155151.tar")
        self.assertEqual(result["version"], "20240129-155151")
        self.assertEqual(result["kernel"], "6.1.75-0-lts")
        self.assertEqual(result["alpine"], "3.18")

    def test_parse_sigfile(self):
        """Test parsing a trusted comment from signature contents."""
        result = parse_trusted_comment(sigfile=SCENARIO_AB_SAME / "a" / "psyopsOS.tar.minisig")
        self.assertEqual(result["type"], "psyopsOS")
        self.assertEqual(result["filename"], "psyopsOS.x86_64.20240705-173840.tar")
        self.assertEqual(result["version"], "20240705-173840")
        self.assertEqual(result["kernel"], "6.6.36-0-lts")
        self.assertEqual(result["alpine"], "3.20")

    def test_invalid_input(self):
        """Test handling of invalid input combinations."""
        with self.assertRaises(ValueError):
            parse_trusted_comment()  # No arguments

        with self.assertRaises(ValueError):
            parse_trusted_comment(comment="test", sigcontents="test")  # Too many arguments

    def test_no_trusted_comment(self):
        """Test handling of signature contents with no trusted comment."""
        sigcontents = textwrap.dedent(
            """\
            untrusted comment: signature from minisign secret key
            RURFlbvwaqbpRv1RGZk6b0TkCUmJZvNRKVqfyveYOicg3g1FR6EUmvwkPGwB8yFJ+m9l/Al6sixSOAUVQDwwsfs23Coa9xEHBwI=
            nISvkyfCnUI6Xjgr0vz+g4VbymHJh8rvPAHKncAm5sXVT9HMyQV5+HhgvMP3NLaRKSCng6VAYkIufXYkCmobCQ=="""
        )
        with self.assertRaises(ValueError):
            parse_trusted_comment(sigcontents=sigcontents)

    def test_malformed_trusted_comment(self):
        """Test handling of malformed trusted comment."""
        comment = "trusted comment: this is not a key-value pair"
        result = parse_trusted_comment(comment=comment)
        self.assertEqual(result, {})  # Should return empty dict for no key-value pairs

    def test_with_sigfile(self):
        """Test with sigfile parameter using the test scenario."""
        sigfile = SCENARIO_AB_SAME / "a" / "psyopsOS.tar.minisig"
        result = parse_trusted_comment(sigfile=sigfile)
        self.assertEqual(result["type"], "psyopsOS")
        self.assertEqual(result["filename"], "psyopsOS.x86_64.20240705-173840.tar")
        self.assertEqual(result["version"], "20240705-173840")
        self.assertEqual(result["kernel"], "6.6.36-0-lts")
        self.assertEqual(result["alpine"], "3.20")

    def test_empty_sigfile(self):
        """Test with an empty sigfile."""
        # Create an empty temporary file
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(b"")
            with self.assertRaises(ValueError):
                parse_trusted_comment(sigfile=tmp.name)


class TestParseNeuralUpgradeInfoComment(unittest.TestCase):
    """Tests for parse_psyopsOS_neuralupgrade_info_comment function."""

    def test_parse_comment_string(self):
        """Test parsing a neural upgrade info comment directly."""
        comment = (
            "# neuralupgrade-info: last_updated=20240401 default_boot_label=psyopsOS-5.0 extra_programs=rescue,memtest"
        )
        result = parse_psyopsOS_neuralupgrade_info_comment(comment=comment)
        self.assertEqual(result["last_updated"], "20240401")
        self.assertEqual(result["default_boot_label"], "psyopsOS-5.0")
        self.assertEqual(result["extra_programs"], "rescue,memtest")

    def test_invalid_input(self):
        """Test handling of invalid input combinations."""
        with self.assertRaises(ValueError):
            parse_psyopsOS_neuralupgrade_info_comment()  # No arguments

        with self.assertRaises(ValueError):
            parse_psyopsOS_neuralupgrade_info_comment(comment="test", file="test")  # Too many arguments

    def test_invalid_comment_format(self):
        """Test handling of invalid comment format."""
        comment = "invalid comment without proper prefix"
        with self.assertRaises(ValueError):
            parse_psyopsOS_neuralupgrade_info_comment(comment=comment)

    def test_with_file(self):
        """Test with file parameter using the test scenario."""
        grub_cfg = SCENARIO_AB_SAME / "efisys" / "grub" / "grub.cfg"
        result = parse_psyopsOS_neuralupgrade_info_comment(file=grub_cfg)
        self.assertEqual(result["last_updated"], "20250308-040402")
        self.assertEqual(result["default_boot_label"], "psyopsOS-A")
        self.assertEqual(result["extra_programs"], "/memtest64.efi,/tcshell.efi")

    def test_file_without_comment(self):
        """Test with a file that doesn't contain a neuralupgrade-info comment."""
        # Create a temporary file without the neuralupgrade-info comment
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(
                textwrap.dedent(
                    """\
                    # This is a GRUB configuration file
                    set timeout=5
                    set default=0
                    """
                ).encode("utf-8")
            )
            tmp.seek(0)
            with self.assertRaises(ValueError):
                parse_psyopsOS_neuralupgrade_info_comment(file=tmp.name)

    def test_empty_file(self):
        """Test with an empty file."""
        # Create an empty temporary file
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(b"")
            tmp.seek(0)
            with self.assertRaises(ValueError):
                parse_psyopsOS_neuralupgrade_info_comment(file=tmp.name)


if __name__ == "__main__":
    unittest.main()
