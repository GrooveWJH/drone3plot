"""Shared plane control logic for plane and complex controllers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from pydjimqtt import drone_emergency_stop, send_stick_control


@dataclass
class PlaneControlState:
    """State holder for plane control finite state machine."""

    plane_state: str = "approach"  # approach -> brake -> settle
    brake_started_at: float | None = None
    brake_count: int = 0
    settle_started_at: float | None = None


def plane_control_step(
    state: PlaneControlState,
    cfg,
    plane_approach,
    plane_settle,
    error_x_body: float,
    error_y_body: float,
    distance: float,
    mqtt_client,
    now: float,
) -> Tuple[float, float, dict, int, int]:
    """
    Execute one control step for plane logic.

    Returns:
        roll_offset, pitch_offset, pid_components, roll, pitch
    """
    roll_offset = 0.0
    pitch_offset = 0.0
    roll = cfg.NEUTRAL
    pitch = cfg.NEUTRAL
    pid_components = {'x': (0.0, 0.0, 0.0), 'y': (0.0, 0.0, 0.0)}

    if state.plane_state == "approach":
        if distance <= cfg.PLANE_BRAKE_DISTANCE and state.brake_count < cfg.PLANE_BRAKE_MAX_COUNT:
            state.plane_state = "brake"
            state.brake_started_at = now
            state.brake_count += 1
            plane_approach.reset()
            plane_settle.reset()
            drone_emergency_stop(mqtt_client)
        elif distance <= cfg.PLANE_SETTLE_DISTANCE:
            state.plane_state = "settle"
            plane_settle.reset()
            state.settle_started_at = now
        else:
            roll_offset, pitch_offset, pid_components = plane_approach.compute(
                error_x_body,
                error_y_body,
                0.0,
                0.0,
                now,
            )
            roll = int(cfg.NEUTRAL + roll_offset)
            pitch = int(cfg.NEUTRAL + pitch_offset)
            send_stick_control(mqtt_client, roll=roll, pitch=pitch)

    if state.plane_state == "brake":
        if state.brake_started_at is None:
            state.brake_started_at = now
        send_stick_control(mqtt_client)
        if now - state.brake_started_at >= cfg.PLANE_BRAKE_HOLD_TIME:
            state.plane_state = "settle"
            plane_settle.reset()
            state.settle_started_at = now

    if state.plane_state == "settle":
        if distance > cfg.PLANE_SETTLE_DISTANCE:
            state.plane_state = "approach"
            plane_approach.reset()
            state.settle_started_at = None
        elif state.settle_started_at and (now - state.settle_started_at) >= cfg.PLANE_SETTLE_TIMEOUT:
            state.plane_state = "approach"
            plane_approach.reset()
            state.settle_started_at = None
        else:
            roll_offset, pitch_offset, pid_components = plane_settle.compute(
                error_x_body,
                error_y_body,
                0.0,
                0.0,
                now,
            )
            roll = int(cfg.NEUTRAL + roll_offset)
            pitch = int(cfg.NEUTRAL + pitch_offset)
            send_stick_control(mqtt_client, roll=roll, pitch=pitch)

    return roll_offset, pitch_offset, pid_components, roll, pitch
