# CLAUDE.md - Coding Guidelines for Neural Upgrade

## Commands
- Make sure a venv exists at `./.venv`;
  if it doesn't exist create it with `uv venv .venv`,
  and once it does exist enter it and use the following commands from inside the venv
- Install for development: `pip install -e .`
- Format code: `black .` (line length 120)
- Type check: `mypy .` (add `types-requests` for development)
- Build zipapp: `python3 -m zipapp --main neuralupgrade.cmd:main --output neuralupgrade.pyz --python "/usr/bin/env python3" src`
- Run cog for docs: `cog` (updates readme.md with latest command help)

## Code Style
- Use Black formatter with 120 character line limit
- Use type hints and docstrings for all functions
- Import order: standard library, then third-party, then local modules
- Name variables using snake_case, classes using PascalCase
- Use f-strings for string formatting
- Proper exception handling with specific exceptions
- Logging via the module logger (from neuralupgrade import logger)
- Prefer context managers for resource management (e.g., file handling, mounts)

## Error Handling
- Use specific exception types when possible (see UmountError example)
- Consider using MultiError pattern for aggregating errors
- Use logging appropriately with debug/info/warning/error levels
