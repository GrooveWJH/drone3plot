"""Waypoint generation and selection for complex control."""

from __future__ import annotations

import random
from typing import Iterable

from .complex_utils import parse_waypoint


def generate_random_waypoint(
    current_x: float,
    current_y: float,
    bound: float,
    min_distance: float,
    max_distance: float | None = None,
    max_attempts: int = 50,
) -> tuple[float, float]:
    for _ in range(max_attempts):
        new_x = random.uniform(-bound, bound)
        new_y = random.uniform(-bound, bound)
        dist = ((new_x - current_x) ** 2 + (new_y - current_y) ** 2) ** 0.5
        if dist < min_distance:
            continue
        if max_distance is not None and dist > max_distance:
            continue
        return (new_x, new_y)
    return (current_x, current_y)


def generate_random_angle(current_angle: float, min_diff: float = 30) -> float:
    while True:
        new_angle = random.uniform(-180, 180)
        angle_diff = abs(((new_angle - current_angle + 180) % 360) - 180)
        if angle_diff >= min_diff:
            return new_angle


def build_move_target_random(
    *,
    current_waypoint: tuple[float, float],
    current_target_yaw: float,
    current_target_z: float,
    cfg,
    step_index: int,
) -> tuple[tuple[float, float], float, float, str]:
    if cfg.PLANE_RANDOM_ONLY_FAR:
        min_distance = cfg.PLANE_RANDOM_FAR_DISTANCE
        max_distance = None
    elif step_index % 2 == 1:
        min_distance = cfg.PLANE_RANDOM_NEAR_DISTANCE
        max_distance = cfg.PLANE_RANDOM_NEAR_DISTANCE_MAX
    else:
        min_distance = cfg.PLANE_RANDOM_FAR_DISTANCE
        max_distance = None
    next_waypoint = generate_random_waypoint(
        current_waypoint[0],
        current_waypoint[1],
        bound=cfg.PLANE_RANDOM_BOUND,
        min_distance=min_distance,
        max_distance=max_distance,
    )
    next_yaw = generate_random_angle(current_target_yaw, cfg.RANDOM_ANGLE_MIN_DIFF)
    next_z = _generate_random_height(
        current_target_z=current_target_z,
        min_height=cfg.VERTICAL_RANDOM_MIN,
        max_height=cfg.VERTICAL_RANDOM_MAX,
        min_delta=cfg.VERTICAL_RANDOM_MIN_DELTA,
    )
    desc = f"随机航点{step_index}"
    return next_waypoint, next_z, next_yaw, desc


def _generate_random_height(
    *,
    current_target_z: float,
    min_height: float,
    max_height: float,
    min_delta: float,
    max_attempts: int = 50,
) -> float:
    low = min(min_height, max_height)
    high = max(min_height, max_height)
    if high <= low:
        return low
    if min_delta <= 0:
        return random.uniform(low, high)
    for _ in range(max_attempts):
        candidate = random.uniform(low, high)
        if abs(candidate - current_target_z) >= min_delta:
            return candidate
    return max(low, min(high, current_target_z + min_delta))


def build_move_target_fixed(
    *,
    waypoints: Iterable[tuple[float, ...]],
    target_yaws: Iterable[float],
    index: int,
    fallback_z: float,
) -> tuple[tuple[float, float], float, float, str]:
    waypoint_list = list(waypoints)
    yaw_list = list(target_yaws)
    next_index = index % len(waypoint_list)
    raw = waypoint_list[next_index]
    fallback_yaw = yaw_list[next_index % len(yaw_list)]
    next_x, next_y, next_z, next_yaw = parse_waypoint(raw, fallback_z, fallback_yaw)
    desc = f"航点{next_index}"
    return (next_x, next_y), next_z, next_yaw, desc
