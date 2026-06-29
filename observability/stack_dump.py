"""Diagnostic signal handler to dump all thread stacks.

On Unix, sending SIGUSR1 to the LiMa process writes the current stack traces
of every thread to ``/tmp/lima-stacks-<pid>-<ts>.txt``. This is useful for
diagnosing event-loop stalls in production without attaching a debugger.

Windows does not support SIGUSR1, so this module is a no-op there.
"""

from __future__ import annotations

import os
import signal
import sys
import threading
import time
import traceback


def _dump_stacks(signum: int, frame) -> None:  # noqa: ARG001
    """Write a snapshot of every Python thread's stack to /tmp."""
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    path = f"/tmp/lima-stacks-{os.getpid()}-{int(time.time())}.txt"
    lines = [f"LiMa stack dump at {now} (thread {threading.current_thread().name})\n"]
    for tid, tframe in sys._current_frames().items():
        lines.append(f"\n--- Thread {tid} ---\n")
        lines.extend(traceback.format_stack(tframe))
    try:
        with open(path, "w", encoding="utf-8") as handle:
            handle.writelines(lines)
        print(f"[stack-dump] wrote {path}", file=sys.stderr)
    except Exception as exc:
        print(f"[stack-dump] failed to write {path}: {exc}", file=sys.stderr)


def install_stack_dump_handler() -> None:
    """Install SIGUSR1 handler if the signal is available (Unix only)."""
    sigusr1 = getattr(signal, "SIGUSR1", None)
    if sigusr1 is not None:
        try:
            signal.signal(sigusr1, _dump_stacks)
        except Exception as exc:
            print(f"[stack-dump] failed to install handler: {exc}", file=sys.stderr)


install_stack_dump_handler()
