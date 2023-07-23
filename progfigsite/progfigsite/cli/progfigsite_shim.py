"""The progfigsite command.

This is required.
"""


def ensure_autovendor():
    """Ensure that the vendor directory is in the Python path."""

    from pathlib import Path
    import sys

    vendor_dir = Path(__file__).parent.parent / "autovendor"
    if vendor_dir.as_posix() not in sys.path:
        sys.path.insert(0, vendor_dir.as_posix())


def main():

    ensure_autovendor()

    # If progfiguration is installed as a vendor pacakge, then it will find it there first.
    # This means the following will work from inside a progfiguration+progfigsite pip package.
    # If it's installed as a system package, then it will find it there as well.
    # This means the following will work if you `pip install -e '.[development]'`.

    from progfiguration.cli import progfiguration_site_cmd

    root_package = __package__.split(".")[0] if __package__ else None
    if root_package is None:
        raise RuntimeError(
            "Cannot find name of the running package. Are you calling this as a script from a package installed from pip?"
        )

    progfiguration_site_cmd.main(root_package)
