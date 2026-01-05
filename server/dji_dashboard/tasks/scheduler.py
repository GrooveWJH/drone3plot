"""Placeholder for future APScheduler jobs."""
from __future__ import annotations

from typing import Callable, List


class SimpleTaskScheduler:
    """Minimal scheduler placeholder that executes callbacks sequentially."""

    def __init__(self) -> None:
        self._jobs: List[Callable[[], None]] = []

    def add_job(self, func: Callable[[], None]) -> None:
        self._jobs.append(func)

    def run_all(self) -> None:
        for job in list(self._jobs):
            job()
