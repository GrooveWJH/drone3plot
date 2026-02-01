"""Shared yaw control logic for yaw and complex controllers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from pydjimqtt import send_stick_control


@dataclass
class YawControlState:
    """State holder for yaw control stability tracking."""

    in_tolerance_since: float | None = None


def yaw_control_step(
    cfg,
    yaw_controller,
    error_yaw: float,
    mqtt_client,
    now: float,
) -> Tuple[float, Tuple[float, float, float], int]:
    """
    Execute one yaw control step.

    Returns:
        yaw_offset, yaw_pid_components, yaw
    """
    yaw_offset, yaw_pid_components = yaw_controller.compute(error_yaw, 0.0, now)
    if cfg.YAW_DEADZONE > 0 and abs(yaw_offset) < cfg.YAW_DEADZONE:
        yaw_offset = 0.0
    yaw = int(cfg.NEUTRAL + yaw_offset)
    send_stick_control(mqtt_client, yaw=yaw)
    return yaw_offset, yaw_pid_components, yaw
