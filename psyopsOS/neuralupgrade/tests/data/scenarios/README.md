# Test Scenarios

This directory contains realistic test scenarios that can be used for multiple tests as a way to document the behavior of the system. These scenarios contain actual files with realistic content that matches what would be found in a real system.

## Scenarios

### psyopsos_x86_64_efi_working

A working psyopsOS installation on an x86_64 system using EFI boot. This scenario includes:

- `minisig.txt`: A valid minisign signature file with a trusted comment
- `grub.cfg`: A valid GRUB configuration file with a neuralupgrade-info comment

### psyopsos_dual_boot_system

A complete dual boot psyopsOS system with A and B partitions and an EFI partition. This scenario includes:

- `a_minisig.txt`: A valid minisign signature file for partition A with OS version 20240129-155151
- `b_minisig.txt`: A valid minisign signature file for partition B with OS version 20240201-123456
- `efi_minisig.txt`: A valid minisign signature file for the EFI partition
- `grub.cfg`: A valid GRUB configuration file with psyopsOS-B set as the default boot

## Usage

To use these scenarios in your tests:

```python
from pathlib import Path

# Path to test scenario directories
TESTS_DIR = Path(__file__).parent
SCENARIOS_DIR = TESTS_DIR / "data" / "scenarios"
WORKING_SCENARIO = SCENARIOS_DIR / "psyopsos_x86_64_efi_working"

def test_example():
    """Example test using the working scenario."""
    grub_cfg = WORKING_SCENARIO / "grub.cfg"
    # Use the file in your test...
```

## Guidelines

1. Use scenarios for realistic, working configurations that can be reused across multiple tests
2. For invalid or edge cases, continue to use in-line test data in the test files
3. When adding a new scenario, update this README with information about what the scenario contains
4. Try to make scenarios as complete as possible, including all files that would be needed in a real system