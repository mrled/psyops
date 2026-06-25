#!/usr/bin/env python3
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from threading import Lock

from kvrb.config import BACKUP_PARALLELISM, EXCLUDE_ANNOTATION
from kvrb.kube import (
    JsonMap,
    Workload,
    delete_stale_backup_jobs,
    eligible_pvcs,
    get_replicas,
    job_logs,
    kubectl,
    scale,
    short_name,
    wait_for_job,
    wait_for_no_pods_using_pvc,
    workloads_for_pvc,
)
from kvrb.manifests import backup_job_manifest, create_temp_secret, restic_repository


class BackupFailures(Exception):
    def __init__(self, failures: list[str]) -> None:
        super().__init__("one or more PVC backups failed")
        self.failures = failures


@dataclass(frozen=True)
class BackupPlan:
    pvc: JsonMap
    workloads: list[Workload]


def pvc_excludes(pvc: JsonMap) -> list[str]:
    """Return non-empty restic exclusion lines from a PVC annotation."""
    annotations = pvc.get("metadata", {}).get("annotations", {})
    raw_excludes = annotations.get(EXCLUDE_ANNOTATION, "")
    return [line.strip() for line in raw_excludes.splitlines() if line.strip()]


def workload_key(workload: Workload) -> tuple[str, str, str]:
    return (workload["api"], workload["namespace"], workload["name"])


def backup_pvc(pvc: JsonMap, workloads: list[Workload] | None = None) -> None:
    """Back up the given PVC to the configured repository.

    - Scale down any workloads using the PVC to zero replicas.
    - Wait for all pods using the PVC to terminate.
    - Create a temporary secret with the necessary environment variables for the backup job.
    - Create a Kubernetes Job to perform the backup.
    - Wait for the Job to complete successfully.
    - Clean up the Job and temporary secret.
    - Scale the workloads back to their original replica counts.
    """

    namespace = pvc["metadata"]["namespace"]
    pvc_name = pvc["metadata"]["name"]
    repository = restic_repository(namespace, pvc_name)
    excludes = pvc_excludes(pvc)
    temp_secret = short_name("restic", pvc_name, "env")
    job_name = short_name("restic", pvc_name)
    delete_stale_backup_jobs(namespace, pvc_name, job_name)
    if workloads is None:
        workloads = workloads_for_pvc(namespace, pvc_name)
    original_replicas: dict[tuple[str, str, str], tuple[Workload, int]] = {}
    job_created = False

    print(f"Backing up {namespace}/{pvc_name} to {repository}", flush=True)
    if excludes:
        print(f"Using {len(excludes)} restic exclude pattern(s): {', '.join(excludes)}", flush=True)
    if not workloads:
        print(
            f"No active workload currently uses {namespace}/{pvc_name}; backing up without scaling",
            flush=True,
        )

    try:
        for workload in workloads:
            key = (workload["api"], workload["namespace"], workload["name"])
            original_replicas[key] = (workload, get_replicas(workload))
            scale(workload, 0)

        wait_for_no_pods_using_pvc(namespace, pvc_name)
        create_temp_secret(namespace, temp_secret, repository)
        kubectl(
            "create",
            "-f",
            "-",
            input_text=backup_job_manifest(namespace, job_name, temp_secret, pvc_name, excludes),
        )
        job_created = True
        wait_for_job(namespace, job_name)
    finally:
        if job_created:
            job_logs(namespace, job_name)
        kubectl("-n", namespace, "delete", "job", job_name, "--ignore-not-found=true", check=False)
        kubectl("-n", namespace, "delete", "secret", temp_secret, "--ignore-not-found=true", check=False)
        for workload, replicas in reversed(list(original_replicas.values())):
            scale(workload, replicas)


def backup_annotated_pvcs() -> None:
    """Enumerate and back up all PVCs that have opted in to backups."""
    pvcs = eligible_pvcs()
    if not pvcs:
        print("No opted-in PVCs found", flush=True)
        return

    plans: list[BackupPlan] = [
        BackupPlan(pvc=pvc, workloads=workloads_for_pvc(pvc["metadata"]["namespace"], pvc["metadata"]["name"]))
        for pvc in pvcs
    ]

    max_workers = max(1, min(BACKUP_PARALLELISM, len(plans)))
    print(f"Running PVC backups with parallelism {max_workers}", flush=True)
    workload_locks = {workload_key(workload): Lock() for plan in plans for workload in plan.workloads}

    def run_plan(plan: BackupPlan) -> None:
        keys = sorted({workload_key(workload) for workload in plan.workloads})
        locks = [workload_locks[key] for key in keys]
        for lock in locks:
            lock.acquire()
        try:
            backup_pvc(plan.pvc, plan.workloads)
        finally:
            for lock in reversed(locks):
                lock.release()

    failures: list[str] = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(run_plan, plan): plan for plan in plans}
        for future in as_completed(futures):
            pvc = futures[future].pvc
            try:
                future.result()
            except Exception as exc:
                failures.append(f"{pvc['metadata']['namespace']}/{pvc['metadata']['name']}: {exc}")
                print(f"ERROR: {failures[-1]}", flush=True)

    if failures:
        raise BackupFailures(failures)
