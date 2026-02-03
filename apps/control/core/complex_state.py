"""State container for complex control."""

from __future__ import annotations

from dataclasses import dataclass
import time


@dataclass
class ControlState:
    phase: str = "task"  # task -> align -> move -> vertical
    plane_state: str = "approach"  # approach -> brake -> settle
    yaw_in_tolerance_since: float | None = None
    plane_in_tolerance_since: float | None = None
    z_in_tolerance_since: float | None = None
    control_start_time: float = 0.0
    loop_count: int = 0
    brake_started_at: float | None = None
    brake_count: int = 0
    settle_started_at: float | None = None
    task_photo_printed: bool = False
    task_completed_count: int = 0


def reset_for_next_target(state: ControlState) -> None:
    state.phase = "task"
    state.plane_state = "approach"
    state.yaw_in_tolerance_since = None
    state.plane_in_tolerance_since = None
    state.z_in_tolerance_since = None
    state.control_start_time = time.time()
    state.loop_count = 0
    state.brake_started_at = None
    state.brake_count = 0
    state.settle_started_at = None
    state.task_photo_printed = False
    state.task_completed_count = 0
