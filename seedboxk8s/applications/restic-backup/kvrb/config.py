import os
from pathlib import Path

ANNOTATION = "backup.seedboxk8s.micahrl.com/enabled"
EXCLUDE_ANNOTATION = "backup.seedboxk8s.micahrl.com/exclude"
AWS_DEFAULT_REGION = os.environ["AWS_DEFAULT_REGION"]
AWS_ACCESS_KEY_ID = os.environ["AWS_ACCESS_KEY_ID"]
AWS_SECRET_ACCESS_KEY = os.environ["AWS_SECRET_ACCESS_KEY"]
BACKUP_JOB_TEMPLATE = Path(os.environ.get("BACKUP_JOB_TEMPLATE", "/opt/kvrb/backup-job.json"))
JOB_TIMEOUT_SECONDS = int(os.environ.get("BACKUP_JOB_TIMEOUT_SECONDS", "7200"))
LOCK_LEASE_NAME = os.environ.get("BACKUP_LOCK_LEASE_NAME", "restic-backup")
LOCK_LEASE_NAMESPACE = os.environ.get("BACKUP_LOCK_LEASE_NAMESPACE", "restic-backup")
LOCK_LEASE_TTL_SECONDS = int(os.environ.get("BACKUP_LOCK_LEASE_TTL_SECONDS", "21600"))
POLL_SECONDS = int(os.environ.get("BACKUP_POLL_SECONDS", "5"))
REPOSITORY_BASE = os.environ["RESTIC_REPOSITORY_BASE"].rstrip("/")
RESTIC_PASSWORD = os.environ["RESTIC_PASSWORD"]
RESTIC_SECRET_TEMPLATE = Path(os.environ.get("RESTIC_SECRET_TEMPLATE", "/opt/kvrb/restic-secret.json"))
SOURCE_MOUNT = "/source"
