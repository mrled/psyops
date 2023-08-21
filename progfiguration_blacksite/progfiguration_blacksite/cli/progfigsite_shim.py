"""The progfigsite command.

This is required.
"""


def ensure_staticinclude():
    """Ensure that the static include directory is in the Python path."""

    from pathlib import Path
    import sys

    staticinclude_dir = Path(__file__).parent.parent / "builddata" / "static_include"
    if staticinclude_dir.as_posix() not in sys.path:
        sys.path.insert(0, staticinclude_dir.as_posix())


def main():

    ensure_staticinclude()

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
