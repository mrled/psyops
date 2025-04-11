"""Tests for update_metadata.py."""

import os
import tempfile
import unittest

from neuralupgrade.update_metadata import parse_trusted_comment


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

    def test_parse_sigcontents(self):
        """Test parsing a trusted comment from signature contents."""
        sigcontents = """untrusted comment: signature from minisign secret key
RURFlbvwaqbpRv1RGZk6b0TkCUmJZvNRKVqfyveYOicg3g1FR6EUmvwkPGwB8yFJ+m9l/Al6sixSOAUVQDwwsfs23Coa9xEHBwI=
trusted comment: type=psyopsOS filename=psyopsOS.20240129-155151.tar version=20240129-155151 kernel=6.1.75-0-lts alpine=3.18
nISvkyfCnUI6Xjgr0vz+g4VbymHJh8rvPAHKncAm5sXVT9HMyQV5+HhgvMP3NLaRKSCng6VAYkIufXYkCmobCQ=="""
        result = parse_trusted_comment(sigcontents=sigcontents)
        self.assertEqual(result["type"], "psyopsOS")
        self.assertEqual(result["filename"], "psyopsOS.20240129-155151.tar")
        self.assertEqual(result["version"], "20240129-155151")
        self.assertEqual(result["kernel"], "6.1.75-0-lts")
        self.assertEqual(result["alpine"], "3.18")

    def test_invalid_input(self):
        """Test handling of invalid input combinations."""
        with self.assertRaises(ValueError):
            parse_trusted_comment()  # No arguments

        with self.assertRaises(ValueError):
            parse_trusted_comment(comment="test", sigcontents="test")  # Too many arguments

    def test_no_trusted_comment(self):
        """Test handling of signature contents with no trusted comment."""
        sigcontents = """untrusted comment: signature from minisign secret key
RURFlbvwaqbpRv1RGZk6b0TkCUmJZvNRKVqfyveYOicg3g1FR6EUmvwkPGwB8yFJ+m9l/Al6sixSOAUVQDwwsfs23Coa9xEHBwI=
nISvkyfCnUI6Xjgr0vz+g4VbymHJh8rvPAHKncAm5sXVT9HMyQV5+HhgvMP3NLaRKSCng6VAYkIufXYkCmobCQ=="""
        with self.assertRaises(ValueError):
            parse_trusted_comment(sigcontents=sigcontents)

    def test_malformed_trusted_comment(self):
        """Test handling of malformed trusted comment."""
        comment = "trusted comment: this is not a key-value pair"
        result = parse_trusted_comment(comment=comment)
        self.assertEqual(result, {})  # Should return empty dict for no key-value pairs

    def test_with_sigfile(self):
        """Test with sigfile parameter using a mock."""
        # Create a temporary file with test content
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(
                b"""untrusted comment: signature from minisign secret key
RURFlbvwaqbpRv1RGZk6b0TkCUmJZvNRKVqfyveYOicg3g1FR6EUmvwkPGwB8yFJ+m9l/Al6sixSOAUVQDwwsfs23Coa9xEHBwI=
trusted comment: type=psyopsOS filename=test.tar version=20240101 kernel=6.1.75 alpine=3.18
nISvkyfCnUI6Xjgr0vz+g4VbymHJh8rvPAHKncAm5sXVT9HMyQV5+HhgvMP3NLaRKSCng6VAYkIufXYkCmobCQ=="""
            )

        try:
            result = parse_trusted_comment(sigfile=tmp.name)
            self.assertEqual(result["type"], "psyopsOS")
            self.assertEqual(result["filename"], "test.tar")
            self.assertEqual(result["version"], "20240101")
            self.assertEqual(result["kernel"], "6.1.75")
            self.assertEqual(result["alpine"], "3.18")
        finally:
            os.unlink(tmp.name)  # Clean up the temporary file

    def test_empty_sigfile(self):
        """Test with an empty sigfile."""
        # Create an empty temporary file
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(b"")

        try:
            with self.assertRaises(ValueError):
                parse_trusted_comment(sigfile=tmp.name)
        finally:
            os.unlink(tmp.name)  # Clean up the temporary file


if __name__ == "__main__":
    unittest.main()
