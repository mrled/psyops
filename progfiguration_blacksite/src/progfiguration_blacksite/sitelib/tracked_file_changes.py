import hashlib

from progfiguration.progfigtypes import AnyPath


def hash_file_nosecurity(path: str):
    """Hash a file quickly, without regard to security concerns"""
    hasher = hashlib.blake2b()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


class TrackedFileChanges:
    """A context manager that tracks changes to a file's data.

    Does not track metadata changes like owner/permissions,
    just changes to the file's contents.

    Example:

    .. code-block:: python

        with TrackedFileChanges(Path("somefile.txt")) as tracker:
            # Set the file contents to "Hello, world!" no matter what they were before
            with tracker.open("w") as f:
                f.write("Hello, world!")
            if tracker.changed:
                print("The original file contents were differej")
            else:
                print("The original file contents were the same")

    """

    def __init__(self, path: AnyPath):
        self.path = path
        self.initial_hash = None

    def __enter__(self):
        if self.path.exists():
            self.initial_hash = hash_file_nosecurity(self.path)
        else:
            self.initial_hash = None
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        pass

    @property
    def changed(self) -> bool:
        return self.initial_hash != hash_file_nosecurity(self.path)

    @property
    def created(self) -> bool:
        return self.initial_hash is None and self.path.exists()
