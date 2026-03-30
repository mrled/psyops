"""Entry point shim that delegates to the bundled pull-from-github.py script."""
import subprocess
import sys
from pathlib import Path


def main():
    script = Path(__file__).parent / "scripts" / "pull-from-github.py"
    sys.exit(subprocess.call([sys.executable, str(script)] + sys.argv[1:]))
