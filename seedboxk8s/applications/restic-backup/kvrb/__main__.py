import sys

from kvrb.backup import BackupFailures, backup_annotated_pvcs


def main() -> int:
    try:
        backup_annotated_pvcs()
    except BackupFailures as exc:
        print("One or more PVC backups failed:", flush=True)
        for failure in exc.failures:
            print(f"- {failure}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
