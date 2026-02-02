"""Helpers for complex (plane+vertical+yaw) control."""

from __future__ import annotations

import math
from typing import Sequence
from rich.console import Console


def update_stability_timer(
    *,
    in_range: bool,
    in_tolerance_since: float | None,
    now: float,
    console: Console,
    enter_message: str,
    exit_message: str,
    suppress_exit_log: bool = False,
) -> tuple[float | None, float | None]:
    if in_range:
        if in_tolerance_since is None:
            console.print(enter_message)
            return now, 0.0
        return in_tolerance_since, now - in_tolerance_since
    if in_tolerance_since is not None and not suppress_exit_log:
        console.print(exit_message)
    return None, None


def yaw_from_points(x1: float, y1: float, x2: float, y2: float) -> float:
    return math.degrees(math.atan2(y2 - y1, x2 - x1))


def parse_waypoint(
    waypoint: Sequence[float],
    fallback_z: float,
    fallback_yaw: float,
) -> tuple[float, float, float, float]:
    if len(waypoint) >= 4:
        return waypoint[0], waypoint[1], waypoint[2], waypoint[3]
    if len(waypoint) == 3:
        return waypoint[0], waypoint[1], waypoint[2], fallback_yaw
    if len(waypoint) >= 2:
        return waypoint[0], waypoint[1], fallback_z, fallback_yaw
    raise ValueError("Waypoint must have at least x and y")
