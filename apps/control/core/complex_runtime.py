"""Runtime helpers for complex control loop."""

from __future__ import annotations

from dataclasses import dataclass
import math
import time
from typing import Any

from pydjimqtt import send_stick_control

from apps.control.core.complex_targets import (
    build_move_target_fixed,
    build_move_target_random,
    generate_random_angle,
)
from apps.control.core.complex_utils import parse_waypoint, update_stability_timer, yaw_from_points
from apps.control.core.controller import get_yaw_error
from apps.control.core.plane_logic import PlaneControlState, plane_control_step
from apps.control.core.yaw_logic import yaw_control_step


@dataclass
class ComplexContext:
    current_waypoint: tuple[float, float]
    current_target_yaw: float
    current_target_z: float
    waypoint_index: int
    move_target_waypoint: tuple[float, float] | None = None
    move_target_yaw: float | None = None
    move_target_z: float | None = None
    move_yaw: float | None = None


@dataclass
class LoopInfo:
    target_x: float
    target_y: float
    yaw_target: float
    current_x: float
    current_y: float
    distance: float
    phase_label: str
    roll_offset: float
    pitch_offset: float
    yaw_offset: float
    roll: int
    pitch: int
    yaw: int
    pid_components: dict[str, tuple[float, float, float]]
    yaw_pid_components: tuple[float, float, float]


def init_context(cfg: Any, position: tuple[float, float, float], current_yaw: float) -> ComplexContext:
    if cfg.PLANE_USE_RANDOM_WAYPOINTS:
        return ComplexContext(
            current_waypoint=(0.0, 0.0),
            current_target_yaw=generate_random_angle(current_yaw, cfg.RANDOM_ANGLE_MIN_DIFF),
            current_target_z=cfg.VERTICAL_TARGET_HEIGHT,
            waypoint_index=0,
        )

    waypoint_index = 0
    current_waypoint_raw = cfg.WAYPOINTS[waypoint_index]
    default_yaw = cfg.TARGET_YAWS[waypoint_index % len(cfg.TARGET_YAWS)]
    target_x, target_y, target_z, target_yaw = parse_waypoint(
        current_waypoint_raw,
        cfg.VERTICAL_TARGET_HEIGHT,
        default_yaw,
    )
    return ComplexContext(
        current_waypoint=(target_x, target_y),
        current_target_yaw=target_yaw,
        current_target_z=target_z,
        waypoint_index=waypoint_index,
    )


def init_phase(
    cfg: Any,
    state: Any,
    ctx: ComplexContext,
    position: tuple[float, float, float],
) -> None:
    current_x, current_y, current_z = position
    initial_distance = math.hypot(ctx.current_waypoint[0] - current_x, ctx.current_waypoint[1] - current_y)
    if initial_distance <= cfg.TOLERANCE_XY and abs(current_z - ctx.current_target_z) <= cfg.VERTICAL_TOLERANCE:
        state.phase = "task"
    elif initial_distance <= cfg.TOLERANCE_XY:
        state.phase = "vertical"
    else:
        state.phase = "align"
        ctx.move_target_waypoint = ctx.current_waypoint
        ctx.move_target_yaw = ctx.current_target_yaw
        ctx.move_target_z = ctx.current_target_z
        ctx.move_yaw = yaw_from_points(
            current_x,
            current_y,
            ctx.current_waypoint[0],
            ctx.current_waypoint[1],
        )


def _format_phase_label(state: Any, phase_percent: float | None) -> str:
    if state.phase == "task":
        percent = "" if phase_percent is None else f"{phase_percent:5.1f}%"
        return f"TASK {percent}".rstrip()
    if state.phase == "align":
        percent = "" if phase_percent is None else f"{phase_percent:5.1f}%"
        return f"ALIGN {percent}".rstrip()
    if state.phase == "vertical":
        return "VERT"
    return f"MOVE-{state.plane_state.upper()}"


def _ensure_next_move_target(cfg: Any, ctx: ComplexContext) -> tuple[str, tuple[float, float]]:
    if ctx.move_target_waypoint is None:
        if cfg.PLANE_USE_RANDOM_WAYPOINTS:
            ctx.move_target_waypoint, ctx.move_target_z, ctx.move_target_yaw, next_desc = build_move_target_random(
                current_waypoint=ctx.current_waypoint,
                current_target_yaw=ctx.current_target_yaw,
                cfg=cfg,
                step_index=ctx.waypoint_index + 1,
            )
        else:
            ctx.move_target_waypoint, ctx.move_target_z, ctx.move_target_yaw, next_desc = build_move_target_fixed(
                waypoints=cfg.WAYPOINTS,
                target_yaws=cfg.TARGET_YAWS,
                index=ctx.waypoint_index + 1,
                fallback_z=cfg.VERTICAL_TARGET_HEIGHT,
            )
        ctx.move_yaw = yaw_from_points(
            ctx.current_waypoint[0],
            ctx.current_waypoint[1],
            ctx.move_target_waypoint[0],
            ctx.move_target_waypoint[1],
        )
        return next_desc, ctx.move_target_waypoint
    return "", ctx.move_target_waypoint


def step_complex(
    *,
    cfg: Any,
    state: Any,
    ctx: ComplexContext,
    position: tuple[float, float, float],
    current_yaw: float,
    console: Any,
    mqtt_client: Any,
    plane_approach: Any,
    plane_settle: Any,
    yaw_controller: Any,
    vertical_controller: Any,
) -> LoopInfo:
    current_time = time.time()
    current_x, current_y, _ = position

    roll_offset = 0.0
    pitch_offset = 0.0
    yaw_offset = 0.0
    roll = cfg.NEUTRAL
    pitch = cfg.NEUTRAL
    yaw = cfg.NEUTRAL
    pid_components = {"x": (0.0, 0.0, 0.0), "y": (0.0, 0.0, 0.0)}
    yaw_pid_components = (0.0, 0.0, 0.0)

    if state.phase in {"align", "move"}:
        target_waypoint = ctx.move_target_waypoint or ctx.current_waypoint
        yaw_target = ctx.move_yaw if ctx.move_yaw is not None else current_yaw
    else:
        target_waypoint = ctx.current_waypoint
        yaw_target = ctx.current_target_yaw

    target_x, target_y = target_waypoint
    phase_percent: float | None = None

    if state.phase == "task":
        error_yaw = get_yaw_error(ctx.current_target_yaw, current_yaw)
        abs_error = abs(error_yaw)
        task_hold_time = 1.0
        phase_percent = max(0.0, min(100.0, (1.0 - abs_error / cfg.TOLERANCE_YAW) * 100.0))

        state.yaw_in_tolerance_since, stable_duration = update_stability_timer(
            in_range=abs_error < cfg.TOLERANCE_YAW,
            in_tolerance_since=state.yaw_in_tolerance_since,
            now=current_time,
            console=console,
            enter_message=(
                f"[yellow]⏱ 进入任务朝向 (误差:{error_yaw:+.2f}°)，保持 {task_hold_time:.1f}s...[/yellow]"
            ),
            exit_message=(
                f"[yellow]✗ 偏离任务朝向 (误差:{error_yaw:+.2f}°)，重置计时[/yellow]"
            ),
        )
        if stable_duration == 0.0 and not state.task_photo_printed:
            console.print("[cyan]拍照（未实现）[/cyan]")
            state.task_photo_printed = True
        if stable_duration is not None and stable_duration >= task_hold_time:
            yaw_controller.reset()
            state.phase = "align"
            state.yaw_in_tolerance_since = None
            state.task_photo_printed = False
            state.plane_state = "approach"
            state.plane_in_tolerance_since = None
            state.brake_started_at = None
            state.brake_count = 0
            state.settle_started_at = None
            state.control_start_time = time.time()
            _ensure_next_move_target(cfg, ctx)

        yaw_offset, yaw_pid_components, yaw = yaw_control_step(
            cfg,
            yaw_controller,
            error_yaw,
            mqtt_client,
            current_time,
        )

    elif state.phase == "align":
        error_yaw = get_yaw_error(ctx.move_yaw, current_yaw)
        abs_error = abs(error_yaw)
        phase_percent = max(0.0, min(100.0, (1.0 - abs_error / cfg.TOLERANCE_YAW) * 100.0))
        state.yaw_in_tolerance_since, stable_duration = update_stability_timer(
            in_range=abs_error < cfg.TOLERANCE_YAW,
            in_tolerance_since=state.yaw_in_tolerance_since,
            now=current_time,
            console=console,
            enter_message=(
                f"[yellow]⏱ 转向下一点 (误差:{error_yaw:+.2f}°)，等待稳定 {cfg.YAW_ARRIVAL_STABLE_TIME}s...[/yellow]"
            ),
            exit_message=(
                f"[yellow]✗ 偏离航向 (误差:{error_yaw:+.2f}°)，重置计时[/yellow]"
            ),
        )
        if stable_duration is not None and stable_duration >= cfg.YAW_ARRIVAL_STABLE_TIME:
            yaw_controller.reset()
            state.phase = "move"
            state.yaw_in_tolerance_since = None
            state.control_start_time = time.time()

        yaw_offset, yaw_pid_components, yaw = yaw_control_step(
            cfg,
            yaw_controller,
            error_yaw,
            mqtt_client,
            current_time,
        )

    else:
        yaw_for_control = 0.0 if abs(current_yaw) <= cfg.YAW_ZERO_THRESHOLD_DEG else current_yaw
        yaw_rad = math.radians(yaw_for_control)

        error_x_world = target_x - current_x
        error_y_world = target_y - current_y
        error_x_body = math.cos(yaw_rad) * error_x_world + math.sin(yaw_rad) * error_y_world
        error_y_body = -math.sin(yaw_rad) * error_x_world + math.cos(yaw_rad) * error_y_world

        distance = plane_approach.get_distance(target_x, target_y, current_x, current_y)

        error_yaw = get_yaw_error(ctx.move_yaw, current_yaw)
        yaw_offset, yaw_pid_components, yaw = yaw_control_step(
            cfg,
            yaw_controller,
            error_yaw,
            mqtt_client,
            current_time,
        )

        state.plane_in_tolerance_since, stable_duration = update_stability_timer(
            in_range=distance < cfg.TOLERANCE_XY,
            in_tolerance_since=state.plane_in_tolerance_since,
            now=current_time,
            console=console,
            enter_message=(
                f"[yellow]⏱ 平面进入阈值 (距离:{distance*100:.2f}cm)，等待稳定 {cfg.PLANE_ARRIVAL_STABLE_TIME}s...[/yellow]"
            ),
            exit_message=(
                f"[yellow]✗ 偏离目标 (距离:{distance*100:.2f}cm)，重置稳定计时[/yellow]"
            ),
            suppress_exit_log=(state.plane_state == "brake"),
        )
        if stable_duration is not None:
            brake_cooldown_ok = True
            if state.plane_state == "brake" and state.brake_started_at is not None:
                brake_cooldown_ok = (current_time - state.brake_started_at) >= cfg.PLANE_BRAKE_HOLD_TIME
            if brake_cooldown_ok and stable_duration >= cfg.PLANE_ARRIVAL_STABLE_TIME:
                total_control_time = current_time - state.control_start_time
                console.print(
                    f"\n[bold green]✓ 已到达航点{ctx.waypoint_index} - ({target_x:.2f}, {target_y:.2f})m！[/bold green]"
                )
                console.print(
                    f"[dim]最终距离: {distance*100:.2f} cm | 稳定时长: {stable_duration:.2f}s | 控制用时: {total_control_time:.2f}s[/dim]"
                )

                ctx.current_waypoint = ctx.move_target_waypoint or ctx.current_waypoint
                ctx.current_target_yaw = ctx.move_target_yaw or ctx.current_target_yaw
                ctx.current_target_z = ctx.move_target_z if ctx.move_target_z is not None else ctx.current_target_z
                ctx.waypoint_index += 1
                state.phase = "vertical"
                state.z_in_tolerance_since = None
                state.yaw_in_tolerance_since = None
                plane_approach.reset()
                plane_settle.reset()
                yaw_controller.reset()

        if state.phase == "vertical":
            current_z = position[2]
            error_z = ctx.current_target_z - current_z
            state.z_in_tolerance_since, stable_duration = update_stability_timer(
                in_range=abs(error_z) <= cfg.VERTICAL_TOLERANCE,
                in_tolerance_since=state.z_in_tolerance_since,
                now=current_time,
                console=console,
                enter_message=(
                    f"[yellow]⏱ 高度进入阈值 (误差:{error_z:+.2f}m)，等待稳定 {cfg.VERTICAL_ARRIVAL_STABLE_TIME}s...[/yellow]"
                ),
                exit_message=(
                    f"[yellow]✗ 高度偏离 (误差:{error_z:+.2f}m)，重置计时[/yellow]"
                ),
            )
            if stable_duration is not None and stable_duration >= cfg.VERTICAL_ARRIVAL_STABLE_TIME:
                state.phase = "task"
                state.z_in_tolerance_since = None
                state.task_photo_printed = False
                vertical_controller.reset()
                yaw_controller.reset()

                if cfg.PLANE_USE_RANDOM_WAYPOINTS:
                    ctx.move_target_waypoint, ctx.move_target_z, ctx.move_target_yaw, next_desc = build_move_target_random(
                        current_waypoint=ctx.current_waypoint,
                        current_target_yaw=ctx.current_target_yaw,
                        cfg=cfg,
                        step_index=ctx.waypoint_index + 1,
                    )
                else:
                    ctx.move_target_waypoint, ctx.move_target_z, ctx.move_target_yaw, next_desc = build_move_target_fixed(
                        waypoints=cfg.WAYPOINTS,
                        target_yaws=cfg.TARGET_YAWS,
                        index=ctx.waypoint_index,
                        fallback_z=cfg.VERTICAL_TARGET_HEIGHT,
                    )
                ctx.move_yaw = yaw_from_points(
                    ctx.current_waypoint[0],
                    ctx.current_waypoint[1],
                    ctx.move_target_waypoint[0],
                    ctx.move_target_waypoint[1],
                )
                console.print(
                    f"[bold cyan]→ {next_desc} - ({ctx.current_waypoint[0]:.2f}, {ctx.current_waypoint[1]:.2f})m | 任务Yaw {ctx.current_target_yaw:.1f}°[/bold cyan]\n"
                )
            else:
                output_z, _ = vertical_controller.compute(error_z, current_time)
                throttle = int(max(364, min(1684, cfg.NEUTRAL + output_z)))
                send_stick_control(mqtt_client, throttle=throttle)

        plane_state = PlaneControlState(
            plane_state=state.plane_state,
            brake_started_at=state.brake_started_at,
            brake_count=state.brake_count,
            settle_started_at=state.settle_started_at,
        )
        roll_offset, pitch_offset, pid_components, roll, pitch = plane_control_step(
            plane_state,
            cfg,
            plane_approach,
            plane_settle,
            error_x_body,
            error_y_body,
            distance,
            mqtt_client,
            current_time,
        )
        state.plane_state = plane_state.plane_state
        state.brake_started_at = plane_state.brake_started_at
        state.brake_count = plane_state.brake_count
        state.settle_started_at = plane_state.settle_started_at

    distance = math.hypot(target_x - current_x, target_y - current_y)
    phase_label = _format_phase_label(state, phase_percent)

    return LoopInfo(
        target_x=target_x,
        target_y=target_y,
        yaw_target=yaw_target,
        current_x=current_x,
        current_y=current_y,
        distance=distance,
        phase_label=phase_label,
        roll_offset=roll_offset,
        pitch_offset=pitch_offset,
        yaw_offset=yaw_offset,
        roll=roll,
        pitch=pitch,
        yaw=yaw,
        pid_components=pid_components,
        yaw_pid_components=yaw_pid_components,
    )
