"""Adapters between dashboard runtime and control mission runner."""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any

from apps.control.core.mission_runner import MissionPoint, MissionSpec

from .mission_models import MissionSnapshot, MissionWaypoint


class RuntimeHubDataSource:
    """DataSource-like adapter backed by `runtime_hub.slam.pose`."""

    def __init__(self, runtime_hub: Any) -> None:
        self._hub = runtime_hub

    def get_position(self) -> tuple[float, float, float] | None:
        payload = self._pose_payload()
        if not payload:
            return None
        x = payload.get("x")
        y = payload.get("y")
        z = payload.get("z")
        if x is None or y is None or z is None:
            return None
        return (float(x), float(y), float(z))

    def get_yaw(self) -> float | None:
        payload = self._pose_payload()
        if not payload:
            return None
        yaw = payload.get("yaw")
        if yaw is None:
            return None
        return float(yaw)

    def stop(self) -> None:
        return None

    def _pose_payload(self) -> dict[str, Any] | None:
        pose_service = getattr(self._hub.slam, "pose", None)
        if pose_service is None:
            return None
        payload = pose_service.latest()
        if not isinstance(payload, dict):
            return None
        return payload


class RuntimeHubPoseFeed:
    """Pose feed adapter for takeoff/landing helpers (`latest()` contract)."""

    def __init__(self, runtime_hub: Any) -> None:
        self._hub = runtime_hub

    def latest(self) -> dict[str, Any]:
        pose_service = getattr(self._hub.slam, "pose", None)
        if pose_service is None:
            return {"x": None, "y": None, "z": None, "yaw": None}
        payload = pose_service.latest()
        if not isinstance(payload, dict):
            return {"x": None, "y": None, "z": None, "yaw": None}
        return payload


def parse_mission_waypoints(points_raw: list[dict[str, Any]]) -> list[MissionWaypoint]:
    points: list[MissionWaypoint] = []
    for idx, entry in enumerate(points_raw):
        if not isinstance(entry, dict):
            raise ValueError(f"Point[{idx}] must be an object.")
        try:
            point = MissionWaypoint(
                x=_require_float(entry.get("x"), idx, "x"),
                y=_require_float(entry.get("y"), idx, "y"),
                z=_require_float(entry.get("z"), idx, "z"),
                yaw=_require_float(entry.get("yaw"), idx, "yaw"),
                take_photo=bool(entry.get("takePhoto", True)),
            )
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid point[{idx}] fields.") from exc
        points.append(point)
    return points


def build_snapshot(
    *,
    run_id: str,
    revision: int,
    points: list[MissionWaypoint],
    options: dict[str, Any] | None = None,
) -> MissionSnapshot:
    return MissionSnapshot(
        run_id=run_id,
        revision=revision,
        created_at=time.time(),
        points=points,
        source="dashboard",
        options=options or {},
    )


@dataclass(frozen=True)
class ReturnPoint:
    x: float = 0.0
    y: float = 0.0
    z: float = 1.0
    yaw: float = 0.0
    take_photo: bool = False


def to_control_spec(snapshot: MissionSnapshot, return_point: ReturnPoint) -> MissionSpec:
    if not snapshot.points:
        raise ValueError("Mission snapshot has no waypoints.")
    points = snapshot.points
    initial = MissionPoint(
        x=points[0].x,
        y=points[0].y,
        z=points[0].z,
        yaw=points[0].yaw,
        take_photo=points[0].take_photo,
    )
    waypoints = [
        MissionPoint(
            x=point.x,
            y=point.y,
            z=point.z,
            yaw=point.yaw,
            take_photo=point.take_photo,
        )
        for point in points
    ]
    final = MissionPoint(
        x=return_point.x,
        y=return_point.y,
        z=return_point.z,
        yaw=return_point.yaw,
        take_photo=return_point.take_photo,
    )
    return MissionSpec(initial=initial, waypoints=waypoints, final=final)


def slam_payload_is_fresh(payload: dict[str, Any] | None) -> bool:
    if not isinstance(payload, dict):
        return False
    status = payload.get("status")
    if status == "stale":
        return False
    return all(payload.get(key) is not None for key in ("x", "y", "z", "yaw"))


def _require_float(value: Any, idx: int, key: str) -> float:
    if value is None:
        raise ValueError(f"Point[{idx}] field '{key}' cannot be null.")
    return float(value)
