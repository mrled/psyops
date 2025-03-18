#!/usr/bin/env -S uv run

"""Create a new build version for the project from the current second.

The project is versioned as 1.0.unixtime, like
    1.0.1742334398
"""

import time

print(f"1.0.{int(time.time())}")
