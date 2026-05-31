"""Small in-process concurrency gate for reverse sidecars."""

from __future__ import annotations

import threading
from contextlib import contextmanager
from dataclasses import dataclass


@dataclass
class GateState:
    max_concurrency: int
    in_flight: int = 0


class ConcurrencyGate:
    def __init__(self, max_concurrency: int) -> None:
        self._state = GateState(max(1, max_concurrency))
        self._lock = threading.Lock()

    @property
    def state(self) -> GateState:
        with self._lock:
            return GateState(self._state.max_concurrency, self._state.in_flight)

    @contextmanager
    def acquire(self):
        with self._lock:
            if self._state.in_flight >= self._state.max_concurrency:
                raise RuntimeError("reverse provider concurrency limit exceeded")
            self._state.in_flight += 1
        try:
            yield
        finally:
            with self._lock:
                self._state.in_flight = max(0, self._state.in_flight - 1)
