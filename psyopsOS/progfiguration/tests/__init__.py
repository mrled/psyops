import os
import pdb
import unittest


class PdbTestCase(unittest.TestCase):
    def run(self, result=None):
        """A test runner that runs the debugger if an exception is raised and PROGFIGURATION_TEST_DEBUG is set

        This catches failed tests.
        """
        if result is None:
            result = self.defaultTestResult()

        # Run the test inside a pdb session
        try:
            super(PdbTestCase, self).run(result)
        except Exception:
            if os.environ.get("PROGFIGURATION_TEST_DEBUG"):
                pdb.post_mortem(result.failures[-1][0])
            else:
                raise


def pdbexc(test_method):
    """Decorator that runs the debugger if an exception is raised and PROGFIGURATION_TEST_DEBUG is set

    This catches exceptions in code that isn't a failed test --
    exceptions in code in a test_ method, or in code that it calls.
    """

    def wrapper(*args, **kwargs):
        try:
            test_method(*args, **kwargs)
        except Exception:
            if os.environ.get("PROGFIGURATION_TEST_DEBUG"):
                pdb.post_mortem()
            else:
                raise

    return wrapper
