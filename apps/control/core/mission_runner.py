"""Mission runner helpers for control scripts."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from rich.console import Console

from apps.control import config as cfg
from apps.control.core.complex_runtime import init_context, init_phase, step_complex
from apps.control.core.complex_state import ControlState
from apps.control.core.complex_targets import build_move_target_random
from apps.control.core.controller import PlaneController, YawOnlyController
from apps.control.core.pid import PIDController


@dataclass(frozen=True)
class MissionPoint:
    x: float
    y: float
    z: float
    yaw: float
    take_photo: bool = True


@dataclass(frozen=True)
class MissionSpec:
    initial: MissionPoint
    waypoints: list[MissionPoint]
    final: MissionPoint | None


def load_mission_from_file(path: Path) -> MissionSpec:
    payload = json.loads(path.read_text(encoding="utf-8"))
    waypoints_raw = (
        payload.get("waypoints", payload) if isinstance(payload, dict) else payload
    )
    waypoints: list[MissionPoint] = []
    for item in waypoints_raw:
        if isinstance(item, dict):
            waypoints.append(
                MissionPoint(
                    float(item["x"]),
                    float(item["y"]),
                    float(item["z"]),
                    float(item["yaw"]),
                    bool(item.get("takePhoto", True)),
                )
            )
        else:
            waypoints.append(
                MissionPoint(
                    float(item[0]), float(item[1]), float(item[2]), float(item[3]), True
                )
            )
    initial = (
        waypoints[0]
        if waypoints
        else MissionPoint(0.0, 0.0, cfg.VERTICAL_TARGET_HEIGHT, 0.0, True)
    )
    return MissionSpec(initial=initial, waypoints=waypoints, final=None)


def build_random_mission(count: int) -> MissionSpec:
    points: list[MissionPoint] = []
    current_xy = (0.0, 0.0)
    current_yaw = 0.0
    current_z = cfg.VERTICAL_TARGET_HEIGHT
    for step in range(1, count + 1):
        next_xy, next_z, next_yaw, _ = build_move_target_random(
            current_waypoint=current_xy,
            current_target_yaw=current_yaw,
            current_target_z=current_z,
            cfg=cfg,
            step_index=step,
        )
        points.append(MissionPoint(next_xy[0], next_xy[1], next_z, next_yaw, True))
        current_xy = next_xy
        current_yaw = next_yaw
        current_z = next_z
    initial = MissionPoint(0.0, 0.0, cfg.VERTICAL_TARGET_HEIGHT, 0.0, True)
    return MissionSpec(initial=initial, waypoints=points, final=None)


def apply_mission_to_config(spec: MissionSpec) -> None:
    cfg.PLANE_USE_RANDOM_WAYPOINTS = False
    full_points = list(spec.waypoints)
    if spec.final is not None:
        full_points.append(spec.final)
    cfg.WAYPOINTS = [(p.x, p.y, p.z) for p in full_points]
    cfg.TARGET_YAWS = [p.yaw for p in full_points]


def run_complex_mission(
    *,
    mqtt,
    datasource,
    console: Console,
    spec: MissionSpec,
) -> None:
    plane_approach = PlaneController(
        cfg.KP_XY,
        cfg.KI_XY,
        cfg.KD_XY,
        cfg.MAX_STICK_OUTPUT,
        enable_gain_scheduling=cfg.PLANE_GAIN_SCHEDULING_CONFIG["enabled"],
        gain_schedule_profile=cfg.PLANE_GAIN_SCHEDULING_CONFIG.get("profile"),
        d_filter_alpha=cfg.PLANE_D_FILTER_ALPHA,
    )
    plane_settle = PlaneController(
        cfg.PLANE_SETTLE_KP,
        cfg.PLANE_SETTLE_KI,
        cfg.PLANE_SETTLE_KD,
        cfg.MAX_STICK_OUTPUT,
        enable_gain_scheduling=False,
        d_filter_alpha=cfg.PLANE_D_FILTER_ALPHA,
    )
    yaw_controller = YawOnlyController(
        cfg.KP_YAW,
        cfg.KI_YAW,
        cfg.KD_YAW,
        cfg.MAX_YAW_STICK_OUTPUT,
        i_activation_error=cfg.YAW_I_ACTIVATION_ERROR,
    )
    vertical_controller = PIDController(
        cfg.VERTICAL_KP,
        cfg.VERTICAL_KI,
        cfg.VERTICAL_KD,
        output_limit=cfg.VERTICAL_MAX_THROTTLE_OUTPUT,
        i_activation_threshold=cfg.VERTICAL_I_ACTIVATION_ERROR,
    )
    if cfg.PLANE_GAIN_SCHEDULING_CONFIG["enabled"]:
        plane_approach.distance_far = cfg.PLANE_GAIN_SCHEDULING_CONFIG["distance_far"]
        plane_approach.distance_near = cfg.PLANE_GAIN_SCHEDULING_CONFIG["distance_near"]

    position = None
    current_yaw = None
    while position is None or current_yaw is None:
        position = datasource.get_position()
        current_yaw = datasource.get_yaw()
        time.sleep(0.1)

    ctx = init_context(cfg, position, current_yaw)
    ctx.current_waypoint = (spec.initial.x, spec.initial.y)
    ctx.current_target_z = spec.initial.z
    ctx.current_target_yaw = spec.initial.yaw
    task_required = [point.take_photo for point in spec.waypoints]
    if spec.final is not None:
        task_required.append(spec.final.take_photo)
    ctx.task_required = task_required
    ctx.total_waypoints = len(task_required)
    ctx.final_index_start = len(spec.waypoints) if spec.final is not None else None
    state = ControlState(control_start_time=time.time())
    init_phase(cfg, state, ctx, position)

    total_tasks = ctx.total_waypoints or len(task_required)
    control_interval = 1.0 / cfg.CONTROL_FREQUENCY
    last_print = 0.0
    while True:
        loop_start = time.time()
        position = datasource.get_position()
        current_yaw = datasource.get_yaw()
        if position is None or current_yaw is None:
            time.sleep(0.05)
            continue

        info = step_complex(
            cfg=cfg,
            state=state,
            ctx=ctx,
            position=position,
            current_yaw=current_yaw,
            console=console,
            mqtt_client=mqtt,
            plane_approach=plane_approach,
            plane_settle=plane_settle,
            yaw_controller=yaw_controller,
            vertical_controller=vertical_controller,
        )
        if loop_start - last_print >= 0.5:
            target_z = 0.0 if info.target_z is None else info.target_z
            current_z = 0.0 if info.current_z is None else info.current_z
            console.print(
                f"[cyan]#{state.loop_count:04d}[/cyan] | "
                f"WP{ctx.waypoint_index}/{total_tasks} | "
                f"{info.phase_label} | "
                f"目标({info.target_x:+.2f},{info.target_y:+.2f},{target_z:+.2f},{info.target_yaw:+.1f}°) | "
                f"当前({info.current_x:+.2f},{info.current_y:+.2f},{current_z:+.2f},{info.current_yaw:+.1f}°) | "
                f"距{info.distance * 100:5.1f}cm | "
                f"Out:P{info.pitch_offset:+5.0f}/R{info.roll_offset:+5.0f}/Y{info.yaw_offset:+5.0f}"
            )
            last_print = loop_start
        if state.phase == "done":
            return

        sleep_time = control_interval - (time.time() - loop_start)
        if sleep_time > 0:
            time.sleep(sleep_time)
