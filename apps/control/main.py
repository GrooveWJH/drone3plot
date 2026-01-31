#!/usr/bin/env python3
"""
完整轨迹控制主程序

流程：
1) 进入 DRC
2) 起飞到预设高度
3) 对每个航点依次执行：水平 -> 垂直 -> Yaw
4) 航点完成后可选手动确认再继续
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from pydjimqtt import (  # noqa: E402
    MQTTClient,
    setup_drc_connection,
    stop_heartbeat,
    send_stick_control,
)
from rich.console import Console  # noqa: E402
from rich.panel import Panel  # noqa: E402

from dashboard.services.pose import PoseService  # noqa: E402
from apps.control.core.controller import PlaneController, YawOnlyController, get_yaw_error  # noqa: E402
from apps.control.core.datasource import create_datasource  # noqa: E402
from apps.control.core.pid import PIDController  # noqa: E402
from apps.control.config import (  # noqa: E402
    GATEWAY_SN,
    MQTT_CONFIG,
    SLAM_POSE_TOPIC,
    SLAM_YAW_TOPIC,
    NEUTRAL,
    CONTROL_FREQUENCY,
    TOLERANCE_XY,
    KP_XY,
    KI_XY,
    KD_XY,
    MAX_STICK_OUTPUT,
    PLANE_GAIN_SCHEDULING_CONFIG,
    PLANE_ARRIVAL_STABLE_TIME,
    VERTICAL_HEIGHT_SOURCE,
    VERTICAL_TARGET_HEIGHT,
    VERTICAL_SLAM_ZERO_AT_START,
    VERTICAL_KP,
    VERTICAL_KI,
    VERTICAL_KD,
    VERTICAL_I_ACTIVATION_ERROR,
    VERTICAL_TOLERANCE,
    VERTICAL_MAX_THROTTLE_OUTPUT,
    VERTICAL_CONTROL_FREQUENCY,
    VERTICAL_ARRIVAL_STABLE_TIME,
    KP_YAW,
    KI_YAW,
    KD_YAW,
    MAX_YAW_STICK_OUTPUT,
    TOLERANCE_YAW,
    YAW_I_ACTIVATION_ERROR,
    YAW_ARRIVAL_STABLE_TIME,
    YAW_DEADZONE,
    DRC_USER_ID,
    DRC_USER_CALLSIGN,
    DRC_OSD_FREQUENCY,
    DRC_HSI_FREQUENCY,
    DRC_HEARTBEAT_INTERVAL,
    TRAJECTORY_FILE,
    TRAJECTORY_REQUIRE_CONFIRM,
)


@dataclass(frozen=True)
class Waypoint:
    x: float
    y: float
    z: float
    yaw: float


def _load_waypoints(path: Path) -> list[Waypoint]:
    if not path.exists():
        raise FileNotFoundError(f"trajectory file not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    waypoints: Iterable[dict]
    if isinstance(payload, dict):
        waypoints = payload.get("waypoints", [])
    elif isinstance(payload, list):
        waypoints = payload
    else:
        raise ValueError("trajectory json must be a list or contain 'waypoints'")

    parsed: list[Waypoint] = []
    for idx, item in enumerate(waypoints):
        if not isinstance(item, dict):
            raise ValueError(f"waypoint[{idx}] must be an object")
        if "position" in item and isinstance(item["position"], dict):
            pos = item["position"]
            x = pos.get("x")
            y = pos.get("y")
            z = pos.get("z")
        else:
            x = item.get("x")
            y = item.get("y")
            z = item.get("z")
        yaw = item.get("yaw")
        if x is None or y is None or z is None or yaw is None:
            raise ValueError(f"waypoint[{idx}] missing x/y/z/yaw")
        parsed.append(Waypoint(float(x), float(y), float(z), float(yaw)))
    return parsed


def _clamp(value: float, min_value: int, max_value: int) -> int:
    return int(max(min_value, min(max_value, value)))


def _wait_for_height(mqtt: "MQTTClient", pose: Optional[PoseService], height_source: str,
                     slam_zero: Optional[float]) -> tuple[Optional[float], Optional[float]]:
    if height_source == "relative":
        return mqtt.get_relative_height(), slam_zero
    if pose is None:
        return None, slam_zero
    latest = pose.latest()
    z = latest.get("z")
    if z is None:
        return None, slam_zero
    if VERTICAL_SLAM_ZERO_AT_START:
        if slam_zero is None:
            slam_zero = z
        return z - slam_zero, slam_zero
    return z, slam_zero


def _confirm_or_auto(console: Console, prompt: str) -> None:
    if TRAJECTORY_REQUIRE_CONFIRM:
        console.print(f"[yellow]{prompt}[/yellow]")
        input()


def _run_plane_to_target(console: Console, mqtt: "MQTTClient", datasource, target: Waypoint) -> None:
    controller = PlaneController(
        KP_XY, KI_XY, KD_XY,
        MAX_STICK_OUTPUT,
        enable_gain_scheduling=PLANE_GAIN_SCHEDULING_CONFIG.get("enabled", True),
        gain_schedule_profile=PLANE_GAIN_SCHEDULING_CONFIG.get("profile"),
    )
    controller.distance_far = PLANE_GAIN_SCHEDULING_CONFIG.get("distance_far", 1.0)
    controller.distance_near = PLANE_GAIN_SCHEDULING_CONFIG.get("distance_near", 0.2)

    in_tolerance_since: Optional[float] = None
    control_interval = 1.0 / CONTROL_FREQUENCY
    console.print(f"[cyan]水平控制 → x={target.x:.2f}, y={target.y:.2f}[/cyan]")

    while True:
        loop_start = time.time()
        position = datasource.get_position()
        if position is None:
            time.sleep(0.1)
            continue
        current_x, current_y, _ = position
        distance = controller.get_distance(target.x, target.y, current_x, current_y)
        if distance <= TOLERANCE_XY:
            if in_tolerance_since is None:
                in_tolerance_since = loop_start
            elif loop_start - in_tolerance_since >= PLANE_ARRIVAL_STABLE_TIME:
                send_stick_control(mqtt, roll=NEUTRAL, pitch=NEUTRAL)
                console.print("[green]✓ 水平到达[/green]")
                return
        else:
            in_tolerance_since = None

        roll_offset, pitch_offset, _ = controller.compute(
            target.x, target.y, current_x, current_y, loop_start
        )
        roll = int(NEUTRAL + roll_offset)
        pitch = int(NEUTRAL + pitch_offset)
        send_stick_control(mqtt, roll=roll, pitch=pitch)

        elapsed = time.time() - loop_start
        if elapsed < control_interval:
            time.sleep(control_interval - elapsed)


def _run_vertical_to_target(console: Console, mqtt: "MQTTClient",
                            pose: Optional[PoseService], target: Waypoint,
                            slam_zero: Optional[float]) -> Optional[float]:
    height_source = VERTICAL_HEIGHT_SOURCE.strip().lower()
    if height_source not in {"slam", "relative"}:
        raise ValueError(f"invalid height source: {VERTICAL_HEIGHT_SOURCE}")
    pid = PIDController(
        VERTICAL_KP,
        VERTICAL_KI,
        VERTICAL_KD,
        output_limit=VERTICAL_MAX_THROTTLE_OUTPUT,
        i_activation_threshold=VERTICAL_I_ACTIVATION_ERROR,
    )
    control_interval = 1.0 / VERTICAL_CONTROL_FREQUENCY
    in_tolerance_since: Optional[float] = None
    console.print(f"[cyan]垂直控制 → z={target.z:.2f} ({height_source})[/cyan]")

    while True:
        loop_start = time.time()
        current_height, slam_zero = _wait_for_height(mqtt, pose, height_source, slam_zero)
        if current_height is None:
            time.sleep(0.1)
            continue

        error = target.z - current_height
        output, _ = pid.compute(error, loop_start)
        throttle = _clamp(NEUTRAL + output, 364, 1684)
        send_stick_control(mqtt, throttle=throttle)

        if abs(error) <= VERTICAL_TOLERANCE:
            if in_tolerance_since is None:
                in_tolerance_since = loop_start
            elif loop_start - in_tolerance_since >= VERTICAL_ARRIVAL_STABLE_TIME:
                send_stick_control(mqtt, throttle=NEUTRAL)
                console.print("[green]✓ 高度到达[/green]")
                return slam_zero
        else:
            in_tolerance_since = None

        elapsed = time.time() - loop_start
        if elapsed < control_interval:
            time.sleep(control_interval - elapsed)


def _run_yaw_to_target(console: Console, mqtt: "MQTTClient", datasource, target: Waypoint) -> None:
    controller = YawOnlyController(
        KP_YAW,
        KI_YAW,
        KD_YAW,
        MAX_YAW_STICK_OUTPUT,
        i_activation_error=YAW_I_ACTIVATION_ERROR,
    )
    control_interval = 1.0 / CONTROL_FREQUENCY
    in_tolerance_since: Optional[float] = None
    console.print(f"[cyan]Yaw 控制 → yaw={target.yaw:.1f}°[/cyan]")

    while True:
        loop_start = time.time()
        current_yaw = datasource.get_yaw()
        if current_yaw is None:
            time.sleep(0.1)
            continue

        error = get_yaw_error(target.yaw, current_yaw)
        if abs(error) <= TOLERANCE_YAW:
            if in_tolerance_since is None:
                in_tolerance_since = loop_start
            elif loop_start - in_tolerance_since >= YAW_ARRIVAL_STABLE_TIME:
                send_stick_control(mqtt, yaw=NEUTRAL)
                console.print("[green]✓ Yaw 到达[/green]")
                return
        else:
            in_tolerance_since = None

        yaw_offset, _ = controller.compute(target.yaw, current_yaw, loop_start)
        if YAW_DEADZONE > 0 and abs(yaw_offset) < YAW_DEADZONE:
            yaw_offset = 0
        yaw = int(NEUTRAL + yaw_offset)
        send_stick_control(mqtt, yaw=yaw)

        elapsed = time.time() - loop_start
        if elapsed < control_interval:
            time.sleep(control_interval - elapsed)


def main() -> int:
    console = Console()
    trajectory_path = Path(TRAJECTORY_FILE)

    console.print(Panel.fit(
        "[bold cyan]轨迹飞行控制[/bold cyan]\n"
        f"[dim]轨迹文件: {trajectory_path}[/dim]\n"
        f"[dim]手动确认: {'是' if TRAJECTORY_REQUIRE_CONFIRM else '否'}[/dim]",
        border_style="cyan"
    ))

    waypoints = _load_waypoints(trajectory_path)
    if not waypoints:
        console.print("[red]✗ 轨迹为空[/red]")
        return 1

    mqtt = None
    heartbeat = None
    datasource = None
    pose_service: Optional[PoseService] = None

    try:
        mqtt, _, heartbeat = setup_drc_connection(
            GATEWAY_SN,
            MQTT_CONFIG,
            user_id=DRC_USER_ID,
            user_callsign=DRC_USER_CALLSIGN,
            osd_frequency=DRC_OSD_FREQUENCY,
            hsi_frequency=DRC_HSI_FREQUENCY,
            heartbeat_interval=DRC_HEARTBEAT_INTERVAL,
            wait_for_user=True,
            skip_drc_setup=False,
        )

        datasource = create_datasource(mqtt, SLAM_POSE_TOPIC, SLAM_YAW_TOPIC)
        pose_service = PoseService(mqtt, SLAM_POSE_TOPIC, SLAM_YAW_TOPIC)

        console.print(f"[green]✓ 轨迹点数量: {len(waypoints)}[/green]")
        console.print("[yellow]提示: Ctrl+C 可中断[/yellow]\n")

        console.print("[cyan]起飞高度控制...[/cyan]")
        slam_zero: Optional[float] = None
        first_target = Waypoint(waypoints[0].x, waypoints[0].y, VERTICAL_TARGET_HEIGHT, waypoints[0].yaw)
        slam_zero = _run_vertical_to_target(console, mqtt, pose_service, first_target, slam_zero)

        for idx, wp in enumerate(waypoints, start=1):
            console.print(Panel.fit(
                f"[bold]航点 {idx}[/bold]\n"
                f"x={wp.x:.2f}, y={wp.y:.2f}, z={wp.z:.2f}, yaw={wp.yaw:.1f}°",
                border_style="blue"
            ))
            _run_plane_to_target(console, mqtt, datasource, wp)
            slam_zero = _run_vertical_to_target(console, mqtt, pose_service, wp, slam_zero)
            _run_yaw_to_target(console, mqtt, datasource, wp)

            if idx < len(waypoints):
                _confirm_or_auto(console, "航点完成，按 Enter 继续下一点...")

        console.print("[bold green]✓ 轨迹完成[/bold green]")
        return 0
    except KeyboardInterrupt:
        console.print("\n[yellow]中断退出[/yellow]")
        return 1
    finally:
        if mqtt:
            try:
                send_stick_control(mqtt, roll=NEUTRAL, pitch=NEUTRAL, yaw=NEUTRAL, throttle=NEUTRAL)
            except Exception:
                pass
        if heartbeat:
            stop_heartbeat(heartbeat)
        if mqtt:
            mqtt.disconnect()
        if datasource:
            datasource.stop()


if __name__ == "__main__":
    raise SystemExit(main())
