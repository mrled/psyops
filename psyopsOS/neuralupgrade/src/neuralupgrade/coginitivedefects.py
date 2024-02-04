"""Errors"""


class MultiError(Exception):
    """A wrapper for multiple exceptions"""

    def __init__(self, message_prefix, exceptions):
        self.exceptions = exceptions
        super().__init__(f"MultiError: {message_prefix}: {exceptions}")
