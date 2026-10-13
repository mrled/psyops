"""PVC workload discovery tests; no cluster required."""
import unittest
from unittest.mock import patch

with patch.dict("os.environ", {
    "AWS_DEFAULT_REGION": "test", "AWS_ACCESS_KEY_ID": "test",
    "AWS_SECRET_ACCESS_KEY": "test", "RESTIC_REPOSITORY_BASE": "test",
    "RESTIC_PASSWORD": "test",
}):
    from kvrb import kube


def pod(name, phase="Running", kind="Job"):
    return {
        "metadata": {
            "namespace": "tortuga",
            "name": name,
            "ownerReferences": [{"kind": kind, "name": name}],
        },
        "status": {"phase": phase},
    }


class WorkloadsForPVCTests(unittest.TestCase):
    def test_terminal_jobs_are_ignored(self):
        pods = [pod("dump-ok", "Succeeded"), pod("dump-failed", "Failed")]
        with patch.object(kube, "pods_using_pvc", return_value=pods):
            self.assertEqual(kube.workloads_for_pvc("tortuga", "dump-pvc"), [])

    def test_active_jobs_wait_then_refetch_workloads(self):
        active = [pod("dump"), pod("old-app", kind="StatefulSet")]
        finished = [pod("dump", "Succeeded"), pod("current-app", kind="StatefulSet")]
        with (
            patch.object(kube, "pods_using_pvc", side_effect=[active, finished]) as fetch,
            patch.object(kube.time, "sleep") as sleep,
            patch.object(kube, "kubectl") as command,
        ):
            self.assertEqual(kube.workloads_for_pvc("tortuga", "dump-pvc"), [
                {"api": "statefulset", "namespace": "tortuga", "name": "current-app"},
            ])
            self.assertEqual(fetch.call_count, 2)
            sleep.assert_called_once_with(kube.POLL_SECONDS)
            command.assert_not_called()

    def test_active_job_timeout_is_bounded_and_clear(self):
        with (
            patch.object(kube, "pods_using_pvc", return_value=[pod("dump")]),
            patch.object(kube.time, "monotonic", side_effect=[0, 0, 301]),
            patch.object(kube.time, "sleep"),
            patch.object(kube, "kubectl") as command,
        ):
            with self.assertRaisesRegex(TimeoutError, "active Job pods.*tortuga/dump-pvc.*dump"):
                kube.workloads_for_pvc("tortuga", "dump-pvc")
            command.assert_not_called()

    def test_backup_jobs_do_not_block_planning(self):
        with (
            patch.object(kube, "pods_using_pvc", return_value=[pod("restic-dump-pvc-123")]),
            patch.object(kube.time, "sleep") as sleep,
        ):
            self.assertEqual(kube.workloads_for_pvc("tortuga", "dump-pvc"), [])
            sleep.assert_not_called()

    def test_terminal_pods_do_not_block_release_wait(self):
        pods = [pod("dump-ok", "Succeeded"), pod("dump-failed", "Failed")]
        with (
            patch.object(kube, "pods_using_pvc", return_value=pods),
            patch.object(kube.time, "time", side_effect=[0, 0, 601]),
            patch.object(kube.time, "sleep") as sleep,
        ):
            kube.wait_for_no_pods_using_pvc("tortuga", "dump-pvc", include_backup_jobs=True)
            sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()
