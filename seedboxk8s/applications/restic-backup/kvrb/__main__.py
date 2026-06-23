import sys

from kvrb.backup import BackupFailures, backup_annotated_pvcs
from kvrb.lock import LockHeld, backup_lock


def main() -> int:
    try:
        with backup_lock():
            backup_annotated_pvcs()
    except LockHeld as exc:
        print(exc, flush=True)
        return 1
    except BackupFailures as exc:
        print("One or more PVC backups failed:", flush=True)
        for failure in exc.failures:
            print(f"- {failure}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
