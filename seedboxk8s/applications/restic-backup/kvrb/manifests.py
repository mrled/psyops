import re
from string import Template

from kvrb.config import (
    AWS_ACCESS_KEY_ID,
    AWS_DEFAULT_REGION,
    AWS_SECRET_ACCESS_KEY,
    BACKUP_JOB_TEMPLATE,
    REPOSITORY_BASE,
    RESTIC_PASSWORD,
    RESTIC_SECRET_TEMPLATE,
    SOURCE_MOUNT,
)
from kvrb.kube import kubectl


def restic_repository(namespace: str, pvc_name: str) -> str:
    return f"{REPOSITORY_BASE}/{namespace}/{pvc_name}"


def create_temp_secret(namespace: str, name: str, repository: str) -> None:
    """Create a temporary Kubernetes secret with the necessary environment variables for the backup job.

    The backup jobs must mount a volume in order to read its contents,
    which means they must reside in the volume's namespace.
    Create a secret with object storage credentials and the encryption passowrd in that namespace
    so that the job can use these values during the backup.
    """

    # Check that the restic password --- the only value here that could contain special characters ---
    # is safe to substitute into a JSON string literal.
    if not re.fullmatch(r"^[A-Za-z0-9._~+=:@%/-]+$", RESTIC_PASSWORD):
        raise ValueError("RESTIC_PASSWORD contains characters that are not allowed for JSON template substitution")

    rendered = Template(RESTIC_SECRET_TEMPLATE.read_text()).substitute(
        AWS_DEFAULT_REGION=AWS_DEFAULT_REGION,
        AWS_ACCESS_KEY_ID=AWS_ACCESS_KEY_ID,
        AWS_SECRET_ACCESS_KEY=AWS_SECRET_ACCESS_KEY,
        NAME=name,
        NAMESPACE=namespace,
        RESTIC_PASSWORD=RESTIC_PASSWORD,
        RESTIC_REPOSITORY=repository,
    )
    kubectl("create", "-f", "-", input_text=rendered)


def backup_job_manifest(
    namespace: str,
    name: str,
    secret_name: str,
    pvc_name: str,
    excludes: list[str] | None = None,
) -> str:
    """Return a rendered Kubernetes Job manifest for backing up the given PVC."""
    exclude_lines = ";".join(excludes or [])
    return Template(BACKUP_JOB_TEMPLATE.read_text()).substitute(
        JOB_NAME=name,
        NAMESPACE=namespace,
        PVC_NAME=pvc_name,
        RESTIC_EXCLUDES=exclude_lines,
        SECRET_NAME=secret_name,
        SOURCE_MOUNT=SOURCE_MOUNT,
    )
