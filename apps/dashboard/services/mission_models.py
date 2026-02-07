"""Mission execution models for dashboard orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import time
from typing import Any


class MissionPhase(str, Enum):
    IDLE = "IDLE"
    VALIDATING = "VALIDATING"
    ARMING = "ARMING"
    TAKING_OFF = "TAKING_OFF"
    ALIGNING_TO_FIRST = "ALIGNING_TO_FIRST"
    RUNNING_WAYPOINTS = "RUNNING_WAYPOINTS"
    RETURNING_HOME = "RETURNING_HOME"
    LANDING = "LANDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    ABORTING = "ABORTING"
    ABORTED = "ABORTED"


@dataclass(frozen=True)
class MissionWaypoint:
    x: float
    y: float
    z: float
    yaw: float
    take_photo: bool = True


@dataclass(frozen=True)
class MissionSnapshot:
    run_id: str
    revision: int
    created_at: float
    points: list[MissionWaypoint]
    source: str = "dashboard"
    options: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "revision": self.revision,
            "created_at": self.created_at,
            "source": self.source,
            "options": dict(self.options),
            "points": [
                {
                    "x": point.x,
                    "y": point.y,
                    "z": point.z,
                    "yaw": point.yaw,
                    "takePhoto": point.take_photo,
                }
                for point in self.points
            ],
        }


@dataclass
class MissionRun:
    run_id: str
    phase: MissionPhase = MissionPhase.IDLE
    started_at: float | None = None
    ended_at: float | None = None
    current_index: int = -1
    total_points: int = 0
    error: str | None = None
    aborted: bool = False
    snapshot_revision: int | None = None
    snapshot_size: int = 0

    def start(self, total_points: int, snapshot_revision: int) -> None:
        self.started_at = time.time()
        self.phase = MissionPhase.VALIDATING
        self.current_index = -1
        self.total_points = total_points
        self.snapshot_revision = snapshot_revision
        self.snapshot_size = total_points
        self.error = None
        self.aborted = False
        self.ended_at = None

    def finish(self, phase: MissionPhase) -> None:
        self.phase = phase
        self.ended_at = time.time()

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "phase": self.phase.value,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "current_index": self.current_index,
            "total_points": self.total_points,
            "error": self.error,
            "aborted": self.aborted,
            "snapshot_revision": self.snapshot_revision,
            "snapshot_size": self.snapshot_size,
            "running": self.phase
            not in {MissionPhase.IDLE, MissionPhase.COMPLETED, MissionPhase.FAILED, MissionPhase.ABORTED},
        }
