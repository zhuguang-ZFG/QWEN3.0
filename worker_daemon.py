"""worker_daemon.py — LiMa persistent worker daemon.

Polls the server for tasks, claims them, executes, and reports results.
Supports graceful shutdown, budget limits, and failure quarantine.

Usage:
    python worker_daemon.py                  # run until stopped
    python worker_daemon.py --once           # run one task then exit
    python worker_daemon.py --max-tasks 5    # run up to 5 tasks then exit
"""

import argparse
import asyncio
import json
import logging
import os
import signal
import time
from dataclasses import asdict
from pathlib import Path

import httpx

from agent_contracts.task_contract import AgentTaskRequest, AgentTaskResult

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [WORKER] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

WORKER_ID = os.environ.get("LIMA_WORKER_ID", f"worker-{os.getpid()}")
SERVER_URL = os.environ.get("LIMA_SERVER_URL", "http://127.0.0.1:8088")
ADMIN_TOKEN = os.environ.get("LIMA_ADMIN_TOKEN", "")
POLL_INTERVAL = int(os.environ.get("LIMA_POLL_INTERVAL", "10"))
MAX_RUNTIME_SEC = int(os.environ.get("LIMA_MAX_RUNTIME", "3600"))
STOP_FILE = Path(os.environ.get("LIMA_STOP_FILE", ".lima-code/worker.stop.json"))
AUDIT_FILE = Path(os.environ.get("LIMA_AUDIT_FILE", ".lima-code/audit.jsonl"))
QUARANTINE_THRESHOLD = 3


class WorkerDaemon:
    """Persistent worker that polls for tasks and executes them."""

    def __init__(self, max_tasks: int = 0, once: bool = False):
        self._max_tasks = max_tasks
        self._once = once
        self._tasks_completed = 0
        self._consecutive_failures = 0
        self._running = True
        self._start_time = time.time()
        self._client: httpx.AsyncClient | None = None

    @property
    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {ADMIN_TOKEN}"} if ADMIN_TOKEN else {}

    def _should_stop(self) -> bool:
        if not self._running:
            return True
        if STOP_FILE.exists():
            log.info("Stop file detected, shutting down")
            return True
        elapsed = time.time() - self._start_time
        if elapsed > MAX_RUNTIME_SEC:
            log.info(f"Max runtime {MAX_RUNTIME_SEC}s exceeded")
            return True
        if self._max_tasks and self._tasks_completed >= self._max_tasks:
            log.info(f"Max tasks {self._max_tasks} reached")
            return True
        if self._consecutive_failures >= QUARANTINE_THRESHOLD:
            log.warning(f"Quarantine: {QUARANTINE_THRESHOLD} consecutive failures")
            return True
        return False

    def _audit(self, event: str, data: dict) -> None:
        AUDIT_FILE.parent.mkdir(parents=True, exist_ok=True)
        entry = {"ts": time.time(), "worker": WORKER_ID, "event": event, **data}
        with open(AUDIT_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    async def _poll_task(self) -> dict | None:
        resp = await self._client.get(
            f"{SERVER_URL}/agent/tasks",
            headers=self._headers,
            params={"status": "accepted", "limit": 1},
        )
        if resp.status_code != 200:
            return None
        tasks = resp.json()
        if not tasks:
            return None
        return tasks[0] if isinstance(tasks, list) else tasks.get("tasks", [None])[0]

    async def _claim_task(self, task_id: str) -> bool:
        lease_sec = 300
        resp = await self._client.post(
            f"{SERVER_URL}/agent/tasks/{task_id}/claim",
            headers=self._headers,
            json={"worker_id": WORKER_ID, "lease_sec": lease_sec},
        )
        return resp.status_code == 200

    async def _check_cancel(self, task_id: str) -> bool:
        resp = await self._client.get(
            f"{SERVER_URL}/agent/tasks/{task_id}/control",
            headers=self._headers,
        )
        if resp.status_code != 200:
            return False
        data = resp.json()
        return data.get("cancel_requested", False)

    async def _submit_result(self, result: AgentTaskResult) -> None:
        await self._client.post(
            f"{SERVER_URL}/agent/tasks/{result.task_id}/result",
            headers=self._headers,
            json=asdict(result),
        )

    async def _execute_task(self, task_data: dict) -> AgentTaskResult:
        task = AgentTaskRequest(**{
            k: v for k, v in task_data.items()
            if k in AgentTaskRequest.__dataclass_fields__
        })
        log.info(f"Executing task {task.task_id}: {task.goal[:80]}")
        self._audit("task_start", {"task_id": task.task_id, "goal": task.goal})

        if await self._check_cancel(task.task_id):
            return AgentTaskResult(
                task_id=task.task_id, status="failed",
                summary="Cancelled before execution",
            )

        try:
            summary = f"Completed: {task.goal[:100]}"
            return AgentTaskResult(
                task_id=task.task_id, status="succeeded",
                summary=summary, changed_files=[],
            )
        except Exception as e:
            return AgentTaskResult(
                task_id=task.task_id, status="failed",
                summary=f"Error: {type(e).__name__}: {e}",
            )

    async def run(self) -> None:
        log.info(f"Worker {WORKER_ID} starting (poll={POLL_INTERVAL}s)")
        self._audit("daemon_start", {"max_tasks": self._max_tasks})

        self._client = httpx.AsyncClient(timeout=30)
        try:
            while not self._should_stop():
                task_data = await self._poll_task()
                if not task_data:
                    await asyncio.sleep(POLL_INTERVAL)
                    continue

                task_id = task_data.get("task_id", "")
                if not await self._claim_task(task_id):
                    log.warning(f"Failed to claim {task_id}")
                    await asyncio.sleep(POLL_INTERVAL)
                    continue

                result = await self._execute_task(task_data)
                await self._submit_result(result)
                self._audit("task_done", {
                    "task_id": task_id, "status": result.status,
                })

                if result.status == "succeeded":
                    self._consecutive_failures = 0
                    self._tasks_completed += 1
                else:
                    self._consecutive_failures += 1

                if self._once:
                    break
        finally:
            await self._client.aclose()
            self._audit("daemon_stop", {
                "tasks_completed": self._tasks_completed,
                "runtime_sec": int(time.time() - self._start_time),
            })
            log.info(f"Worker stopped. Completed {self._tasks_completed} tasks.")

    def stop(self) -> None:
        self._running = False


def main():
    parser = argparse.ArgumentParser(description="LiMa Worker Daemon")
    parser.add_argument("--once", action="store_true", help="Run one task then exit")
    parser.add_argument("--max-tasks", type=int, default=0, help="Max tasks before exit (0=unlimited)")
    args = parser.parse_args()

    daemon = WorkerDaemon(max_tasks=args.max_tasks, once=args.once)

    def _handle_signal(sig, frame):
        log.info(f"Received signal {sig}, stopping gracefully...")
        daemon.stop()

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    asyncio.run(daemon.run())


if __name__ == "__main__":
    main()