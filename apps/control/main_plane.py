#!/usr/bin/env python3
"""
平面位置PID控制器 - 主程序（仅XY）

设计假设：
- 平面/垂直/旋转运动是拆分控制的，不存在复合运动。
- 本脚本只负责 XY 平面移动，不控制高度与 yaw。

功能：
- 使用 SLAM 位置数据 (slam/position) 与 SLAM yaw (slam/yaw)
- 通过PID算法控制无人机到目标 XY
- 支持固定航点或随机航点循环测试

坐标映射：
- 世界坐标误差先按 yaw 旋转到机体系（FLU）
- X轴（前方向，x变大）→ Pitch杆量（正值）
- Y轴（左方向，y变大）→ Roll杆量（负值）

使用方法：
1. 在 control/config.py 配置 SLAM 话题与 PID 参数
2. 手动让无人机起飞到合适高度（高度由 main_vertical 控制）
3. 启动: python -m apps.control.main_plane
4. 按 Ctrl+C 退出
"""

import time
import random
import math
import sys
from dataclasses import dataclass
from pathlib import Path

if __package__ is None:
    project_root = Path(__file__).resolve().parents[2]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

from apps.control.bootstrap import ensure_pydjimqtt

ensure_pydjimqtt()

from pydjimqtt import MQTTClient, send_stick_control, start_heartbeat, stop_heartbeat  # noqa: E402
from rich.console import Console  # noqa: E402
from rich.panel import Panel  # noqa: E402

from apps.control import config as cfg  # noqa: E402
from apps.control.core.controller import PlaneController  # noqa: E402
from apps.control.core.datasource import create_datasource  # noqa: E402
from apps.control.core.plane_logic import PlaneControlState, plane_control_step  # noqa: E402
from apps.control.io.logger import DataLogger  # noqa: E402


def generate_random_waypoint(
    current_x,
    current_y,
    bound=1.25,
    min_distance=1.0,
    max_distance=None,
    max_attempts=50,
):
    """
    生成随机航点（在指定正方形内，且与当前位置距离足够大）

    Args:
        current_x: 当前X坐标（米）
        current_y: 当前Y坐标（米）
        bound: 正方形边界（中心为原点，范围 [-bound, bound]）
        min_distance: 最小距离（米）
        max_attempts: 最大尝试次数

    Returns:
        (x, y) 随机航点坐标
    """
    for _ in range(max_attempts):
        new_x = random.uniform(-bound, bound)
        new_y = random.uniform(-bound, bound)
        distance = math.hypot(new_x - current_x, new_y - current_y)
        if distance < min_distance:
            continue
        if max_distance is not None and distance > max_distance:
            continue
        return (new_x, new_y)
    return (current_x, current_y)


@dataclass
class ControlState:
    reached: bool = False
    in_tolerance_since: float | None = None
    control_start_time: float = 0.0
    loop_count: int = 0
    plane_state: str = "approach"
    brake_started_at: float | None = None
    brake_count: int = 0
    settle_started_at: float | None = None


def reset_state_for_new_waypoint(state: ControlState) -> None:
    state.reached = False
    state.in_tolerance_since = None
    state.control_start_time = time.time()
    state.loop_count = 0
    state.plane_state = "approach"
    state.brake_started_at = None
    state.brake_count = 0
    state.settle_started_at = None


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


def main():
    console = Console()

    gain_scheduling_cfg = cfg.PLANE_GAIN_SCHEDULING_CONFIG
    gain_scheduling_enabled = gain_scheduling_cfg["enabled"]

    # 根据配置决定使用固定航点还是随机航点
    if cfg.PLANE_USE_RANDOM_WAYPOINTS:
        mode_info = (
            "[dim]模式: 随机航点生成 "
            f"(范围: ±{cfg.PLANE_RANDOM_BOUND}m, 近点: {cfg.PLANE_RANDOM_NEAR_DISTANCE}-{cfg.PLANE_RANDOM_NEAR_DISTANCE_MAX}m, "
            f"远点: ≥{cfg.PLANE_RANDOM_FAR_DISTANCE}m)[/dim]"
        )
    else:
        waypoints_str = "\n".join(
            [
                f"    航点{i}: ({wp[0]:.2f}, {wp[1]:.2f})m"
                for i, wp in enumerate(cfg.WAYPOINTS)
            ]
        )
        mode_info = (
            f"[dim]航点数量: {len(cfg.WAYPOINTS)}[/dim]\n[dim]{waypoints_str}[/dim]"
        )

    auto_mode_info = (
        "[yellow]自动模式: 已启用[/yellow]"
        if cfg.PLANE_AUTO_NEXT_WAYPOINT
        else "[dim]手动模式: 到达后需按Enter[/dim]"
    )

    # 控制特性说明
    features = []
    if gain_scheduling_enabled:
        features.append(
            f"[green]增益调度[/green] (远:{gain_scheduling_cfg['distance_far']}m, 近:{gain_scheduling_cfg['distance_near']}m)"
        )
    features.append("[green]三段控制[/green] (APPROACH → BRAKE → SETTLE)")
    features_info = " | ".join(features) if features else "[dim]基础PID控制[/dim]"

    # 显示数据源配置
    data_source_info = f"[yellow]位置源: SLAM[/yellow] ({cfg.SLAM_POSE_TOPIC})"

    console.print(
        Panel.fit(
            "[bold cyan]平面位置PID控制器 - 重构版本[/bold cyan]\n"
            f"{data_source_info}\n"
            f"{mode_info}\n"
            f"{auto_mode_info}\n"
            f"[dim]到达阈值: {cfg.TOLERANCE_XY * 100:.1f} cm[/dim]\n"
            f"[dim]PID参数: Kp={cfg.KP_XY}, Ki={cfg.KI_XY}, Kd={cfg.KD_XY}[/dim]\n"
            f"[bold]控制特性:[/bold] {features_info}",
            border_style="cyan",
        )
    )

    # 1. 连接MQTT客户端
    console.print("\n[cyan]━━━ 步骤 1/2: 连接MQTT ━━━[/cyan]")
    mqtt_client = MQTTClient(cfg.GATEWAY_SN, cfg.MQTT_CONFIG)
    try:
        mqtt_client.connect()
        console.print(
            f"[green]✓ MQTT已连接: {cfg.MQTT_CONFIG['host']}:{cfg.MQTT_CONFIG['port']}[/green]"
        )
    except Exception as e:
        console.print(f"[red]✗ MQTT连接失败: {e}[/red]")
        return 1

    # 2. 启动心跳
    console.print("\n[cyan]━━━ 步骤 2/2: 启动心跳 ━━━[/cyan]")
    heartbeat_thread = start_heartbeat(mqtt_client, interval=0.2)
    console.print("[green]✓ 心跳已启动 (5.0Hz)[/green]")

    # 3. 创建统一数据源
    console.print("\n[cyan]━━━ 创建数据源接口 ━━━[/cyan]")
    try:
        datasource = create_datasource(
            mqtt_client, cfg.SLAM_POSE_TOPIC, cfg.SLAM_YAW_TOPIC
        )
        console.print("[green]✓ 数据源已创建: 位置=SLAM[/green]")
    except Exception as e:
        console.print(f"[red]✗ 数据源创建失败: {e}[/red]")
        stop_heartbeat(heartbeat_thread)
        mqtt_client.disconnect()
        return 1

    # 4. 初始化控制器和航点
    approach_controller = PlaneController(
        cfg.KP_XY,
        cfg.KI_XY,
        cfg.KD_XY,
        cfg.MAX_STICK_OUTPUT,
        enable_gain_scheduling=gain_scheduling_enabled,
        gain_schedule_profile=gain_scheduling_cfg.get("profile"),
        d_filter_alpha=cfg.PLANE_D_FILTER_ALPHA,
    )
    settle_controller = PlaneController(
        cfg.PLANE_SETTLE_KP,
        cfg.PLANE_SETTLE_KI,
        cfg.PLANE_SETTLE_KD,
        cfg.MAX_STICK_OUTPUT,
        enable_gain_scheduling=False,
        d_filter_alpha=cfg.PLANE_D_FILTER_ALPHA,
    )

    # 应用配置的增益调度参数
    if gain_scheduling_enabled:
        approach_controller.distance_far = gain_scheduling_cfg["distance_far"]
        approach_controller.distance_near = gain_scheduling_cfg["distance_near"]

    # 初始化航点
    if cfg.PLANE_USE_RANDOM_WAYPOINTS:
        # 随机模式：获取当前位置作为起点
        console.print("[yellow]等待初始位置数据...[/yellow]")
        position = None
        while position is None:
            position = datasource.get_position()
            time.sleep(0.1)
        current_x, current_y, _ = position
        target_waypoint = (0, 0)  # 第一个目标是原点
        waypoint_index = 0
    else:
        waypoint_index = 0
        target_waypoint = cfg.WAYPOINTS[waypoint_index]

    # 5. 初始化数据记录器
    logger = DataLogger(
        enabled=cfg.ENABLE_DATA_LOGGING,
        field_set="plane_only",
        csv_name="plane_control_data.csv",
        subdir="plane",
    )
    if logger.enabled:
        console.print(f"[green]✓ 数据记录已启用: {logger.get_log_dir()}[/green]")

    console.print("\n[bold green]✓ 初始化完成！开始控制...[/bold green]")
    if cfg.PLANE_USE_RANDOM_WAYPOINTS:
        console.print(
            f"[cyan]首个目标: 航点{waypoint_index} - ({target_waypoint[0]:.2f}, {target_waypoint[1]:.2f})m[/cyan]"
        )
    else:
        console.print(
            f"[cyan]首个目标: 航点{waypoint_index} - ({target_waypoint[0]:.2f}, {target_waypoint[1]:.2f})m[/cyan]"
        )
    console.print("[yellow]提示: 按Ctrl+C可随时退出[/yellow]\n")

    # 控制循环
    control_interval = 1.0 / cfg.CONTROL_FREQUENCY
    state = ControlState(control_start_time=time.time())
    plane_state = PlaneControlState()

    try:
        while True:
            loop_start = time.time()
            current_time = loop_start
            state.loop_count += 1
            roll_offset = 0.0
            pitch_offset = 0.0
            roll = cfg.NEUTRAL
            pitch = cfg.NEUTRAL
            pid_components = {"x": (0.0, 0.0, 0.0), "y": (0.0, 0.0, 0.0)}

            # 读取位置数据（使用统一数据源接口）
            position = datasource.get_position()
            if position is None:
                time.sleep(0.1)
                continue

            current_x, current_y, _ = position
            current_yaw = datasource.get_yaw()
            if current_yaw is None:
                time.sleep(0.1)
                continue

            yaw_for_control = (
                0.0 if abs(current_yaw) <= cfg.YAW_ZERO_THRESHOLD_DEG else current_yaw
            )
            # 假设 SLAM yaw 为顺时针为正（0°=正北, 90°=正东）
            yaw_rad = math.radians(yaw_for_control)
            target_x, target_y = target_waypoint
            distance = approach_controller.get_distance(
                target_x, target_y, current_x, current_y
            )

            # 世界坐标误差 -> 机体系误差（FLU）
            error_x_world = target_x - current_x
            error_y_world = target_y - current_y
            error_x_body = (
                math.cos(yaw_rad) * error_x_world + math.sin(yaw_rad) * error_y_world
            )
            error_y_body = (
                -math.sin(yaw_rad) * error_x_world + math.cos(yaw_rad) * error_y_world
            )

            # 判断是否到达（带时间稳定性检查）
            if not state.reached and state.plane_state in {
                "approach",
                "brake",
                "settle",
            }:
                state.in_tolerance_since, stable_duration = update_stability_timer(
                    in_range=distance < cfg.TOLERANCE_XY,
                    in_tolerance_since=state.in_tolerance_since,
                    now=current_time,
                    console=console,
                    enter_message=(
                        f"[yellow]⏱ 进入阈值范围 (距离:{distance * 100:.2f}cm)，等待稳定 {cfg.PLANE_ARRIVAL_STABLE_TIME}s...[/yellow]"
                    ),
                    exit_message=(
                        f"[yellow]✗ 偏离目标 (距离:{distance * 100:.2f}cm)，重置稳定计时[/yellow]"
                    ),
                    suppress_exit_log=(state.plane_state == "brake"),
                )
                if stable_duration is not None:
                    brake_cooldown_ok = True
                    if (
                        state.plane_state == "brake"
                        and state.brake_started_at is not None
                    ):
                        brake_cooldown_ok = (
                            current_time - state.brake_started_at
                        ) >= cfg.PLANE_BRAKE_HOLD_TIME
                    if (
                        brake_cooldown_ok
                        and stable_duration >= cfg.PLANE_ARRIVAL_STABLE_TIME
                    ):
                        # 真正到达！
                        total_control_time = time.time() - state.control_start_time

                        # 计算下一个航点
                        if cfg.PLANE_USE_RANDOM_WAYPOINTS:
                            next_index = waypoint_index + 1
                            step_index = next_index
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
                                current_x,
                                current_y,
                                bound=cfg.PLANE_RANDOM_BOUND,
                                min_distance=min_distance,
                                max_distance=max_distance,
                            )
                            waypoint_desc = f"随机航点{next_index}"
                        else:
                            next_index = (waypoint_index + 1) % len(cfg.WAYPOINTS)
                            next_waypoint = cfg.WAYPOINTS[next_index]
                            waypoint_desc = f"航点{next_index}"

                        console.print(
                            f"\n[bold green]✓ 已到达航点{waypoint_index} - ({target_waypoint[0]:.2f}, {target_waypoint[1]:.2f})m！[/bold green]"
                        )
                        console.print(
                            f"[dim]最终距离: {distance * 100:.2f} cm | 稳定时长: {stable_duration:.2f}s | 控制用时: {total_control_time:.2f}s[/dim]"
                        )

                        if cfg.PLANE_AUTO_NEXT_WAYPOINT:
                            console.print(
                                f"[cyan]自动切换 → {waypoint_desc} - ({next_waypoint[0]:.2f}, {next_waypoint[1]:.2f})m (按Ctrl+C退出)[/cyan]\n"
                            )
                        else:
                            console.print(
                                f"[yellow]按 Enter 前往 {waypoint_desc} - ({next_waypoint[0]:.2f}, {next_waypoint[1]:.2f})m，或Ctrl+C退出...[/yellow]\n"
                            )

                        # 悬停并重置PID
                        for _ in range(5):
                            send_stick_control(mqtt_client)
                            time.sleep(0.01)
                        approach_controller.reset()
                        settle_controller.reset()
                        state.reached = True
                        state.in_tolerance_since = None

                        # 根据模式决定是否等待用户输入
                        if cfg.PLANE_AUTO_NEXT_WAYPOINT:
                            # 自动模式：直接切换
                            waypoint_index = next_index
                            target_waypoint = next_waypoint
                            console.print(
                                f"[bold cyan]→ {waypoint_desc} - ({target_waypoint[0]:.2f}, {target_waypoint[1]:.2f})m[/bold cyan]\n"
                            )
                            reset_state_for_new_waypoint(state)
                        else:
                            # 手动模式：等待键盘输入
                            try:
                                input()
                                waypoint_index = next_index
                                target_waypoint = next_waypoint
                                console.print(
                                    f"[bold cyan]切换目标 → {waypoint_desc} - ({target_waypoint[0]:.2f}, {target_waypoint[1]:.2f})m[/bold cyan]\n"
                                )
                                reset_state_for_new_waypoint(state)
                            except KeyboardInterrupt:
                                break
                        continue
            plane_state.plane_state = state.plane_state
            plane_state.brake_started_at = state.brake_started_at
            plane_state.brake_count = state.brake_count
            plane_state.settle_started_at = state.settle_started_at

            roll_offset, pitch_offset, pid_components, roll, pitch = plane_control_step(
                plane_state,
                cfg,
                approach_controller,
                settle_controller,
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

            # 每10次循环打印详细信息
            if state.loop_count % 2 == 0:
                error_x = target_x - current_x
                error_y = target_y - current_y
                kp_scale = (
                    approach_controller.x_pid.kp / approach_controller.kp_base
                    if gain_scheduling_enabled
                    else 1.0
                )
                kd_scale = (
                    approach_controller.x_pid.kd / approach_controller.kd_base
                    if gain_scheduling_enabled
                    else 1.0
                )
                info_parts = [
                    f"[cyan]#{state.loop_count:04d}[/cyan]",
                    f"WP{waypoint_index}",
                    f"目标({target_x:+.2f},{target_y:+.2f})",
                    f"当前({current_x:+.2f},{current_y:+.2f})",
                    f"距{distance * 100:5.1f}cm",
                    f"阶段:{state.plane_state.upper()}",
                ]
                if gain_scheduling_enabled and state.plane_state == "approach":
                    info_parts.append(
                        f"[yellow]Kp×{kp_scale:.2f} Kd×{kd_scale:.2f}[/yellow]"
                    )

                info_parts.append(f"Out:P{pitch_offset:+5.0f}/R{roll_offset:+5.0f}")
                info_parts.append(
                    f"X(P{pid_components['x'][0]:+5.0f}/I{pid_components['x'][1]:+5.0f}/D{pid_components['x'][2]:+5.0f})"
                )
                info_parts.append(
                    f"Y(P{pid_components['y'][0]:+5.0f}/I{pid_components['y'][1]:+5.0f}/D{pid_components['y'][2]:+5.0f})"
                )
                console.print(" | ".join(info_parts))

                # 记录数据（包含PID分量）
                error_x = target_x - current_x
                error_y = target_y - current_y
                logger.log(
                    timestamp=current_time,
                    target_x=target_x,
                    target_y=target_y,
                    current_x=current_x,
                    current_y=current_y,
                    error_x=error_x,
                    error_y=error_y,
                    distance=distance,
                    roll_offset=roll_offset,
                    pitch_offset=pitch_offset,
                    roll_absolute=roll,
                    pitch_absolute=pitch,
                    waypoint_index=waypoint_index,
                    # PID components for X (Pitch)
                    x_pid_p=pid_components["x"][0],
                    x_pid_i=pid_components["x"][1],
                    x_pid_d=pid_components["x"][2],
                    # PID components for Y (Roll)
                    y_pid_p=pid_components["y"][0],
                    y_pid_i=pid_components["y"][1],
                    y_pid_d=pid_components["y"][2],
                )

            # 精确控制循环频率
            sleep_time = control_interval - (time.time() - loop_start)
            if sleep_time > 0:
                time.sleep(sleep_time)

    except KeyboardInterrupt:
        console.print("\n\n[yellow]⚠ 收到中断信号[/yellow]\n")
    except Exception as e:
        console.print(f"\n\n[red]✗ 发生错误: {e}[/red]")
        console.print(f"[red]错误类型: {type(e).__name__}[/red]")
        import traceback

        console.print(f"[dim]{traceback.format_exc()}[/dim]\n")
    finally:
        console.print("[cyan]━━━ 清理资源 ━━━[/cyan]")

        # 关闭数据记录器
        logger.close()

        console.print("[yellow]发送悬停指令...[/yellow]")
        for _ in range(5):
            send_stick_control(mqtt_client)
            time.sleep(0.1)
        stop_heartbeat(heartbeat_thread)
        console.print("[green]✓ 心跳已停止[/green]")
        mqtt_client.disconnect()
        console.print("[green]✓ MQTT已断开[/green]")

        # 停止数据源
        datasource.stop()
        console.print("[green]✓ 数据源已停止 (SLAM)[/green]")

        console.print("\n[bold green]✓ 已安全退出[/bold green]\n")
    return 0


if __name__ == "__main__":
    exit(main())
