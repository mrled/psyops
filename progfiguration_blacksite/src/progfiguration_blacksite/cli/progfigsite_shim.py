"""The progfigsite command.

This is required.
"""


def ensure_staticinclude():
    """Ensure that the static include directory is in the Python path.

    If progfiguration is installed as a statically included package,
    then it will find it there first.
    This means it will work from inside a progfiguration+progfigsite pip package.

    If it's installed as a system package, then it will find it there as well.
    This means it will work if you `pip install -e '.[development]'`.
    """

    from pathlib import Path
    import sys

    staticinclude_dir = Path(__file__).parent.parent / "builddata" / "static_include"
    if staticinclude_dir.as_posix() not in sys.path:
        sys.path.insert(0, staticinclude_dir.as_posix())


def main():

    ensure_staticinclude()

    from progfiguration.cli import progfiguration_site_cmd

    progfiguration_site_cmd.main()
