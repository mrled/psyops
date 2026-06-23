import json
import os
import time
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Iterator

from kvrb.config import LOCK_LEASE_NAME, LOCK_LEASE_NAMESPACE, LOCK_LEASE_TTL_SECONDS
from kvrb.kube import JsonMap, kubectl, kubectl_json


class LockHeld(Exception):
    pass


def now_timestamp() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def holder_identity() -> str:
    return os.environ.get("HOSTNAME", f"kvrb-{int(time.time())}")


def lease_is_active(lease: JsonMap, holder: str) -> bool:
    spec = lease.get("spec", {})
    if spec.get("holderIdentity") == holder:
        return False

    renew_time = str(spec.get("renewTime") or spec.get("acquireTime") or "")
    if not renew_time:
        return False

    try:
        renewed = datetime.fromisoformat(renew_time.replace("Z", "+00:00"))
    except ValueError:
        return True
    return (datetime.now(UTC) - renewed).total_seconds() < LOCK_LEASE_TTL_SECONDS


def lease_manifest(holder: str) -> JsonMap:
    timestamp = now_timestamp()
    return {
        "apiVersion": "coordination.k8s.io/v1",
        "kind": "Lease",
        "metadata": {
            "name": LOCK_LEASE_NAME,
            "namespace": LOCK_LEASE_NAMESPACE,
        },
        "spec": {
            "acquireTime": timestamp,
            "holderIdentity": holder,
            "leaseDurationSeconds": LOCK_LEASE_TTL_SECONDS,
            "renewTime": timestamp,
        },
    }


def acquire_lock() -> str:
    holder = holder_identity()
    result = kubectl(
        "-n",
        LOCK_LEASE_NAMESPACE,
        "create",
        "-f",
        "-",
        check=False,
        input_text=json.dumps(lease_manifest(holder)),
        log_output=False,
    )
    if result.returncode == 0:
        print(f"Acquired backup lock {LOCK_LEASE_NAMESPACE}/{LOCK_LEASE_NAME} as {holder}", flush=True)
        return holder

    lease = kubectl_json("-n", LOCK_LEASE_NAMESPACE, "get", "lease", LOCK_LEASE_NAME, "-o", "json")
    if lease_is_active(lease, holder):
        active_holder = lease.get("spec", {}).get("holderIdentity", "unknown")
        raise LockHeld(f"backup lock {LOCK_LEASE_NAMESPACE}/{LOCK_LEASE_NAME} is held by {active_holder}")

    timestamp = now_timestamp()
    lock_patch: JsonMap = {
        "spec": {
            "acquireTime": timestamp,
            "holderIdentity": holder,
            "leaseDurationSeconds": LOCK_LEASE_TTL_SECONDS,
            "renewTime": timestamp,
        }
    }
    kubectl("-n", LOCK_LEASE_NAMESPACE, "patch", "lease", LOCK_LEASE_NAME, "--type=merge", "-p", json.dumps(lock_patch))
    print(f"Acquired stale backup lock {LOCK_LEASE_NAMESPACE}/{LOCK_LEASE_NAME} as {holder}", flush=True)
    return holder


def release_lock(holder: str) -> None:
    lease = kubectl_json("-n", LOCK_LEASE_NAMESPACE, "get", "lease", LOCK_LEASE_NAME, "-o", "json")
    if lease.get("spec", {}).get("holderIdentity") != holder:
        print(f"Not releasing backup lock because it is no longer held by {holder}", flush=True)
        return
    kubectl("-n", LOCK_LEASE_NAMESPACE, "delete", "lease", LOCK_LEASE_NAME, "--ignore-not-found=true", check=False)
    print(f"Released backup lock {LOCK_LEASE_NAMESPACE}/{LOCK_LEASE_NAME}", flush=True)


@contextmanager
def backup_lock() -> Iterator[None]:
    holder = acquire_lock()
    try:
        yield
    finally:
        release_lock(holder)
