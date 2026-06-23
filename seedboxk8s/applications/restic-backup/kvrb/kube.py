import json
import re
import subprocess
import time
from typing import Any, TypedDict, cast

from kvrb.config import ANNOTATION, JOB_TIMEOUT_SECONDS, POLL_SECONDS

JsonMap = dict[str, Any]


class Workload(TypedDict):
    api: str
    namespace: str
    name: str


def kubectl(*args: str, check: bool = True, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    """Run kubectl, logging the command and its output."""

    command = ["kubectl", *args]
    print("+ " + " ".join(command), flush=True)
    result = subprocess.run(
        command,
        check=False,
        text=True,
        input=input_text,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if result.stdout:
        print(result.stdout, end="", flush=True)
    if check and result.returncode != 0:
        raise RuntimeError(f"command failed with exit code {result.returncode}: {' '.join(command)}")
    return result


def kubectl_json(*args: str) -> JsonMap:
    return cast(JsonMap, json.loads(kubectl(*args).stdout))


def sanitize_name(value: str) -> str:
    """Sanitize a string to be a valid Kubernetes resource name (DNS-1123 label)."""
    value = re.sub(r"[^a-z0-9.-]+", "-", value.lower())
    value = value.strip("-.")
    return value or "backup"


def short_name(*parts: str) -> str:
    """Generate a short name by joining the given parts and appending a timestamp suffix to ensure uniqueness."""
    suffix = str(int(time.time()))
    base = sanitize_name("-".join(parts))
    max_base = 63 - len(suffix) - 1
    return f"{base[:max_base].rstrip('-')}-{suffix}"


def eligible_pvcs() -> list[JsonMap]:
    """Return PVCs that explicitly opt in to backups."""
    pvcs = kubectl_json("get", "pvc", "--all-namespaces", "-o", "json")["items"]
    selected: list[JsonMap] = []
    for pvc in pvcs:
        annotations = pvc.get("metadata", {}).get("annotations", {})
        if annotations.get(ANNOTATION, "").lower() != "true":
            continue
        if pvc.get("status", {}).get("phase") != "Bound":
            print(f"Skipping {pvc['metadata']['namespace']}/{pvc['metadata']['name']}: PVC is not Bound", flush=True)
            continue
        selected.append(pvc)
    return selected


def pods_using_pvc(namespace: str, pvc_name: str) -> list[JsonMap]:
    """Return pods in the given namespace that use the specified PVC."""
    pods = kubectl_json("-n", namespace, "get", "pods", "-o", "json")["items"]
    return [
        pod
        for pod in pods
        if any(
            volume.get("persistentVolumeClaim", {}).get("claimName") == pvc_name
            for volume in pod.get("spec", {}).get("volumes", [])
        )
    ]


def owner_ref(obj: JsonMap, kind: str) -> JsonMap | None:
    """Return the owner reference of the given kind from the object's metadata, or None if not found.

    Used to find the owning workload (StatefulSet, ReplicaSet, Deployment) of a pod.
    """
    metadata = cast(JsonMap, obj.get("metadata", {}))
    owner_refs = cast(list[object], metadata.get("ownerReferences", []))
    for ref_obj in owner_refs:
        ref = cast(JsonMap, ref_obj)
        if ref.get("kind") == kind:
            return ref
    return None


def backup_job_prefix(pvc_name: str) -> str:
    return sanitize_name(f"restic-{pvc_name}")


def is_backup_job_pod(pod: JsonMap, pvc_name: str) -> bool:
    job = owner_ref(pod, "Job")
    if not job:
        return False
    job_name = str(job.get("name", ""))
    return job_name.startswith(f"{backup_job_prefix(pvc_name)}-")


def workload_for_pod(pod: JsonMap) -> Workload:
    """Return the owning workload (StatefulSet, ReplicaSet, Deployment) for the given pod.

    Finds the workload that manages a given pod.
    Used to determine which workloads need to be scaled down before backing up a PVC.
    """

    namespace = pod["metadata"]["namespace"]
    statefulset = owner_ref(pod, "StatefulSet")
    if statefulset:
        return {
            "api": "statefulset",
            "namespace": namespace,
            "name": statefulset["name"],
        }

    replicaset = owner_ref(pod, "ReplicaSet")
    if replicaset:
        rs = kubectl_json("-n", namespace, "get", "replicaset", replicaset["name"], "-o", "json")  # fmt: skip
        deployment = owner_ref(rs, "Deployment")
        if deployment:
            return {
                "api": "deployment",
                "namespace": namespace,
                "name": deployment["name"],
            }
        return {
            "api": "replicaset",
            "namespace": namespace,
            "name": replicaset["name"],
        }

    raise RuntimeError(f"pod {namespace}/{pod['metadata']['name']} has no supported scalable owner")


def workloads_for_pvc(namespace: str, pvc_name: str) -> list[Workload]:
    """Return the unique workloads that use the given PVC."""
    workloads: dict[tuple[str, str, str], Workload] = {}
    for pod in pods_using_pvc(namespace, pvc_name):
        if pod.get("metadata", {}).get("deletionTimestamp"):
            continue
        if is_backup_job_pod(pod, pvc_name):
            continue
        workload = workload_for_pod(pod)
        workloads[(workload["api"], workload["namespace"], workload["name"])] = workload
    return list(workloads.values())


def delete_stale_backup_jobs(namespace: str, pvc_name: str, current_job_name: str) -> None:
    """Delete previous backup Jobs for this PVC before starting another one."""
    jobs = kubectl_json("-n", namespace, "get", "jobs", "-o", "json")["items"]
    prefix = f"{backup_job_prefix(pvc_name)}-"
    for job in jobs:
        job_name = job["metadata"]["name"]
        if job_name == current_job_name or not str(job_name).startswith(prefix):
            continue
        print(f"Deleting stale backup job {namespace}/{job_name}", flush=True)
        kubectl("-n", namespace, "delete", "job", job_name, "--ignore-not-found=true", check=False)


def get_replicas(workload: Workload) -> int:
    """Return the number of replicas for the given workload (StatefulSet, ReplicaSet, Deployment)."""
    obj = kubectl_json("-n", workload["namespace"], "get", workload["api"], workload["name"], "-o", "json")  # fmt: skip
    return int(obj.get("spec", {}).get("replicas", 1))


def scale(workload: Workload, replicas: int) -> None:
    """Scale the given workload (StatefulSet, ReplicaSet, Deployment) to the specified number of replicas."""
    kubectl("-n", workload["namespace"], "scale", workload["api"], workload["name"], f"--replicas={replicas}")


def wait_for_no_pods_using_pvc(namespace: str, pvc_name: str, timeout: int = 600) -> None:
    """Wait for all pods using the given PVC to terminate, or raise a TimeoutError after the specified timeout."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        pods = pods_using_pvc(namespace, pvc_name)
        active = [
            pod
            for pod in pods
            if not pod.get("metadata", {}).get("deletionTimestamp") and not is_backup_job_pod(pod, pvc_name)
        ]
        if not active:
            return
        print(f"Waiting for {len(active)} pod(s) using {namespace}/{pvc_name} to terminate", flush=True)
        time.sleep(POLL_SECONDS)
    raise TimeoutError(f"timed out waiting for pods using {namespace}/{pvc_name} to terminate")


def wait_for_job(namespace: str, name: str) -> None:
    """Wait for the given Kubernetes Job to complete successfully, or raise an error if it fails or times out."""
    deadline = time.time() + JOB_TIMEOUT_SECONDS
    while time.time() < deadline:
        job = kubectl_json("-n", namespace, "get", "job", name, "-o", "json")
        status = job.get("status", {})
        if status.get("succeeded", 0) >= 1:
            return
        if status.get("failed", 0) >= 1:
            raise RuntimeError(f"backup job {namespace}/{name} failed")
        time.sleep(POLL_SECONDS)
    raise TimeoutError(f"backup job {namespace}/{name} timed out")
