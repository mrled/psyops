import io
import sys
import unittest

from progfiguration import cmd


class TestRun(unittest.TestCase):
    def test_run_basic_stdout_stderr(self):
        """Test stdout/err redirection"""
        result = cmd.run(["sh", "-c", "(echo hello); (echo world >&2)"], print_output=False)
        self.assertEqual(result.stdout.read(), "hello\n")
        self.assertEqual(result.stderr.read(), "world\n")

    def test_run_with_print_output(self):
        """Test simultaneous stdout/err redirection and printing to the terminal"""

        # Redirect stdout/err to a buffer so that we can test that it's writing to it correctly
        # This tests our magic print_output=True functionality :)
        outbuf = io.StringIO()
        sys.stdout = outbuf
        errbuf = io.StringIO()
        sys.stderr = errbuf

        result = cmd.run(["sh", "-c", "(echo hello); (echo world >&2)"])

        self.assertEqual(result.stdout.read(), "hello\n")
        self.assertEqual(result.stderr.read(), "world\n")

        terminal_out = outbuf.getvalue()
        terminal_err = errbuf.getvalue()

        # Reset stdout/err
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__

        self.assertEqual(terminal_out, "hello\n")
        self.assertEqual(terminal_err, "world\n")


if __name__ == "__main__":
    unittest.main()
