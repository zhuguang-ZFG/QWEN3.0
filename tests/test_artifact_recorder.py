"""Tests for device_gateway.artifact_recorder."""

import json
import tempfile
import time
import unittest
from pathlib import Path

# Allow running from repo root
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from device_gateway.artifact_recorder import (
    _STORAGE_BASE,
    record_route_evidence,
    shutdown,
)


class TestArtifactRecorder(unittest.TestCase):
    def setUp(self):
        # Reset state by shutting down any active executor
        shutdown(wait=True)
        # Use a temporary directory for evidence files
        self._orig_base = _STORAGE_BASE
        self._tmpdir = tempfile.mkdtemp(prefix="artifact_test_")
        import device_gateway.artifact_recorder as mod

        mod._STORAGE_BASE = Path(self._tmpdir)

    def tearDown(self):
        shutdown(wait=True)
        import device_gateway.artifact_recorder as mod

        mod._STORAGE_BASE = self._orig_base
        import shutil

        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def _log_path(self, device_id: str) -> Path:
        return Path(self._tmpdir) / f"route_evidence_{device_id}.log"

    def test_record_writes_json_line(self):
        """record_route_evidence should write a JSON line to the log file."""
        record_route_evidence(
            device_id="dev-001",
            task_id="task-123",
            route_policy={"route_role": "device_write", "model_required": False},
            selected_model="gpt-4o",
            backend="openai",
            reason="svg path detected",
            alternatives=[{"model": "gpt-4o-mini", "reason": "fallback"}],
        )
        # Give the async write a moment
        time.sleep(0.5)
        log_path = self._log_path("dev-001")
        self.assertTrue(log_path.exists(), f"Log file not created at {log_path}")
        lines = log_path.read_text(encoding="utf-8").strip().split("\n")
        self.assertEqual(len(lines), 1)
        record = json.loads(lines[0])
        self.assertEqual(record["device_id"], "dev-001")
        self.assertEqual(record["task_id"], "task-123")
        self.assertEqual(record["route_policy"]["route_role"], "device_write")
        self.assertEqual(record["selected_model"], "gpt-4o")
        self.assertEqual(record["backend"], "openai")
        self.assertEqual(record["reason"], "svg path detected")
        self.assertEqual(len(record["alternatives"]), 1)
        self.assertIn("timestamp", record)

    def test_record_append_multiple(self):
        """Multiple records for the same device should append lines."""
        for i in range(3):
            record_route_evidence(
                device_id="dev-002",
                task_id=f"task-{i}",
                route_policy={"route_role": "device_control"},
            )
        time.sleep(0.5)
        lines = self._log_path("dev-002").read_text(encoding="utf-8").strip().split("\n")
        self.assertEqual(len(lines), 3)
        task_ids = [json.loads(line)["task_id"] for line in lines]
        self.assertCountEqual(task_ids, ["task-0", "task-1", "task-2"])

    def test_record_per_device_separation(self):
        """Different devices get separate log files."""
        record_route_evidence(
            device_id="dev-a", task_id="t1", route_policy={}
        )
        record_route_evidence(
            device_id="dev-b", task_id="t2", route_policy={}
        )
        time.sleep(0.5)
        self.assertTrue(self._log_path("dev-a").exists())
        self.assertTrue(self._log_path("dev-b").exists())
        self.assertNotEqual(
            self._log_path("dev-a").stat().st_size,
            self._log_path("dev-b").stat().st_size,
        )

    def test_default_values(self):
        """Optional fields should default to empty when not provided."""
        record_route_evidence(
            device_id="dev-003",
            task_id="task-defaults",
            route_policy={"route_role": "device_unknown"},
        )
        time.sleep(0.5)
        lines = self._log_path("dev-003").read_text(encoding="utf-8").strip().split("\n")
        self.assertEqual(len(lines), 1)
        record = json.loads(lines[0])
        self.assertEqual(record["selected_model"], "")
        self.assertEqual(record["backend"], "")
        self.assertEqual(record["reason"], "")
        self.assertEqual(record["alternatives"], [])

    def test_concurrent_writes(self):
        """Concurrent records should not corrupt the file."""
        import concurrent.futures

        def _write(i: int):
            record_route_evidence(
                device_id="dev-concurrent",
                task_id=f"task-{i:04d}",
                route_policy={"index": i},
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            futures = [pool.submit(_write, i) for i in range(50)]
            concurrent.futures.wait(futures)

        shutdown(wait=True)  # ensure all pending writes complete

        lines = self._log_path("dev-concurrent").read_text(encoding="utf-8").strip().split("\n")
        self.assertEqual(len(lines), 50)
        ids = sorted(json.loads(line)["task_id"] for line in lines)
        self.assertEqual(ids, [f"task-{i:04d}" for i in range(50)])

    def test_shutdown(self):
        """shutdown should drain pending work."""
        record_route_evidence(
            device_id="dev-shutdown",
            task_id="task-shutdown",
            route_policy={},
        )
        shutdown(wait=True)
        log_path = self._log_path("dev-shutdown")
        self.assertTrue(log_path.exists())
        lines = log_path.read_text(encoding="utf-8").strip().split("\n")
        self.assertEqual(len(lines), 1)


if __name__ == "__main__":
    unittest.main()
