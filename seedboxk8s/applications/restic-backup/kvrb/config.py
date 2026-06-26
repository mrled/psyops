import os
from pathlib import Path

ANNOTATION = "backup.seedboxk8s.micahrl.com/enabled"
EXCLUDE_ANNOTATION = "backup.seedboxk8s.micahrl.com/exclude"
KEEP_DAILY_ANNOTATION = "backup.seedboxk8s.micahrl.com/keep-daily"
KEEP_MONTHLY_ANNOTATION = "backup.seedboxk8s.micahrl.com/keep-monthly"
KEEP_WEEKLY_ANNOTATION = "backup.seedboxk8s.micahrl.com/keep-weekly"
KEEP_YEARLY_ANNOTATION = "backup.seedboxk8s.micahrl.com/keep-yearly"
AWS_DEFAULT_REGION = os.environ["AWS_DEFAULT_REGION"]
AWS_ACCESS_KEY_ID = os.environ["AWS_ACCESS_KEY_ID"]
AWS_SECRET_ACCESS_KEY = os.environ["AWS_SECRET_ACCESS_KEY"]
BACKUP_JOB_TEMPLATE = Path(os.environ.get("BACKUP_JOB_TEMPLATE", "/opt/kvrb/backup-job.yaml"))
BACKUP_PARALLELISM = int(os.environ.get("BACKUP_PARALLELISM", "1"))
DEFAULT_KEEP_DAILY = int(os.environ.get("RESTIC_KEEP_DAILY", "14"))
DEFAULT_KEEP_MONTHLY = int(os.environ.get("RESTIC_KEEP_MONTHLY", "120"))
DEFAULT_KEEP_WEEKLY = int(os.environ.get("RESTIC_KEEP_WEEKLY", "8"))
DEFAULT_KEEP_YEARLY = int(os.environ.get("RESTIC_KEEP_YEARLY", "5"))
JOB_TIMEOUT_SECONDS = int(os.environ.get("BACKUP_JOB_TIMEOUT_SECONDS", "7200"))
LOCK_LEASE_NAME = os.environ.get("BACKUP_LOCK_LEASE_NAME", "restic-backup")
LOCK_LEASE_NAMESPACE = os.environ.get("BACKUP_LOCK_LEASE_NAMESPACE", "restic-backup")
LOCK_LEASE_TTL_SECONDS = int(os.environ.get("BACKUP_LOCK_LEASE_TTL_SECONDS", "21600"))
POLL_SECONDS = int(os.environ.get("BACKUP_POLL_SECONDS", "5"))
REPOSITORY_BASE = os.environ["RESTIC_REPOSITORY_BASE"].rstrip("/")
RESTIC_PASSWORD = os.environ["RESTIC_PASSWORD"]
RESTIC_SECRET_TEMPLATE = Path(os.environ.get("RESTIC_SECRET_TEMPLATE", "/opt/kvrb/restic-secret.json"))
SOURCE_MOUNT = "/source"
