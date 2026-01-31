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

from pydjimqtt import MQTTClient, start_heartbeat, stop_heartbeat, send_stick_control
from rich.console import Console
from rich.panel import Panel

from apps.control import config as cfg
from apps.control.core.controller import PlaneController
from apps.control.core.datasource import create_datasource
from apps.control.io.logger import DataLogger


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


def main():
    console = Console()

    gain_scheduling_cfg = cfg.PLANE_GAIN_SCHEDULING_CONFIG
    gain_scheduling_enabled = gain_scheduling_cfg['enabled']

    # 根据配置决定使用固定航点还是随机航点
    if cfg.PLANE_USE_RANDOM_WAYPOINTS:
        mode_info = (
            "[dim]模式: 随机航点生成 "
            f"(范围: ±{cfg.PLANE_RANDOM_BOUND}m, 近点: {cfg.PLANE_RANDOM_NEAR_DISTANCE}-{cfg.PLANE_RANDOM_NEAR_DISTANCE_MAX}m, "
            f"远点: ≥{cfg.PLANE_RANDOM_FAR_DISTANCE}m)[/dim]"
        )
    else:
        waypoints_str = "\n".join(
            [f"    航点{i}: ({wp[0]:.2f}, {wp[1]:.2f})m" for i, wp in enumerate(cfg.WAYPOINTS)])
        mode_info = f"[dim]航点数量: {len(cfg.WAYPOINTS)}[/dim]\n[dim]{waypoints_str}[/dim]"

    auto_mode_info = "[yellow]自动模式: 已启用[/yellow]" if cfg.PLANE_AUTO_NEXT_WAYPOINT else "[dim]手动模式: 到达后需按Enter[/dim]"

    # 控制特性说明
    features = []
    if gain_scheduling_enabled:
        features.append(
            f"[green]增益调度[/green] (远:{gain_scheduling_cfg['distance_far']}m, 近:{gain_scheduling_cfg['distance_near']}m)")
    features_info = " | ".join(features) if features else "[dim]基础PID控制[/dim]"

    # 显示数据源配置
    data_source_info = f"[yellow]位置源: SLAM[/yellow] ({cfg.SLAM_POSE_TOPIC})"

    console.print(Panel.fit(
        "[bold cyan]平面位置PID控制器 - 重构版本[/bold cyan]\n"
        f"{data_source_info}\n"
        f"{mode_info}\n"
        f"{auto_mode_info}\n"
        f"[dim]到达阈值: {cfg.TOLERANCE_XY*100:.1f} cm[/dim]\n"
        f"[dim]PID参数: Kp={cfg.KP_XY}, Ki={cfg.KI_XY}, Kd={cfg.KD_XY}[/dim]\n"
        f"[bold]控制特性:[/bold] {features_info}",
        border_style="cyan"
    ))

    # 1. 连接MQTT客户端
    console.print("\n[cyan]━━━ 步骤 1/2: 连接MQTT ━━━[/cyan]")
    mqtt_client = MQTTClient(cfg.GATEWAY_SN, cfg.MQTT_CONFIG)
    try:
        mqtt_client.connect()
        console.print(
            f"[green]✓ MQTT已连接: {cfg.MQTT_CONFIG['host']}:{cfg.MQTT_CONFIG['port']}[/green]")
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
            mqtt_client, cfg.SLAM_POSE_TOPIC, cfg.SLAM_YAW_TOPIC)
        console.print("[green]✓ 数据源已创建: 位置=SLAM[/green]")
    except Exception as e:
        console.print(f"[red]✗ 数据源创建失败: {e}[/red]")
        stop_heartbeat(heartbeat_thread)
        mqtt_client.disconnect()
        return 1

    # 4. 初始化控制器和航点
    controller = PlaneController(
        cfg.KP_XY, cfg.KI_XY, cfg.KD_XY,
        cfg.MAX_STICK_OUTPUT,
        enable_gain_scheduling=gain_scheduling_enabled,
        gain_schedule_profile=gain_scheduling_cfg.get('profile'),
        d_filter_alpha=cfg.PLANE_D_FILTER_ALPHA,
    )

    # 应用配置的增益调度参数
    if gain_scheduling_enabled:
        controller.distance_far = gain_scheduling_cfg['distance_far']
        controller.distance_near = gain_scheduling_cfg['distance_near']

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
        field_set='plane_only',
        csv_name='plane_control_data.csv',
        subdir='plane'
    )
    if logger.enabled:
        console.print(f"[green]✓ 数据记录已启用: {logger.get_log_dir()}[/green]")

    console.print("\n[bold green]✓ 初始化完成！开始控制...[/bold green]")
    if cfg.PLANE_USE_RANDOM_WAYPOINTS:
        console.print(
            f"[cyan]首个目标: 航点{waypoint_index} - ({target_waypoint[0]:.2f}, {target_waypoint[1]:.2f})m[/cyan]")
    else:
        console.print(
            f"[cyan]首个目标: 航点{waypoint_index} - ({target_waypoint[0]:.2f}, {target_waypoint[1]:.2f})m[/cyan]")
    console.print("[yellow]提示: 按Ctrl+C可随时退出[/yellow]\n")

    # 控制循环
    control_interval = 1.0 / cfg.CONTROL_FREQUENCY
    reached = False
    in_tolerance_since = None  # 记录进入阈值范围的时间戳
    control_start_time = time.time()  # 记录开始控制的时间
    loop_count = 0  # 循环计数器

    try:
        while True:
            loop_start = time.time()
            loop_count += 1

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

            yaw_for_control = 0.0 if abs(
                current_yaw) <= cfg.YAW_ZERO_THRESHOLD_DEG else current_yaw
            yaw_rad = math.radians(yaw_for_control)
            target_x, target_y = target_waypoint
            distance = controller.get_distance(
                target_x, target_y, current_x, current_y)

            # 世界坐标误差 -> 机体系误差（FLU）
            error_x_world = target_x - current_x
            error_y_world = target_y - current_y
            error_x_body = math.cos(
                yaw_rad) * error_x_world + math.sin(yaw_rad) * error_y_world
            error_y_body = -math.sin(yaw_rad) * error_x_world + \
                                     math.cos(yaw_rad) * error_y_world

            # 判断是否到达（带时间稳定性检查）
            if not reached:
                if distance < cfg.TOLERANCE_XY:
                    # 进入阈值范围
                    if in_tolerance_since is None:
                        in_tolerance_since = time.time()
                        console.print(
                            f"[yellow]⏱ 进入阈值范围 (距离:{distance*100:.2f}cm)，等待稳定 {cfg.PLANE_ARRIVAL_STABLE_TIME}s...[/yellow]")
                    else:
                        # 检查是否已稳定足够时间
                        stable_duration = time.time() - in_tolerance_since
                        if stable_duration >= cfg.PLANE_ARRIVAL_STABLE_TIME:
                            # 真正到达！
                            total_control_time = time.time() - control_start_time

                            # 计算下一个航点
                            if cfg.PLANE_USE_RANDOM_WAYPOINTS:
                                next_index = waypoint_index + 1
                                step_index = next_index
                                if step_index % 2 == 1:
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

                            console.print(f"\n[bold green]✓ 已到达航点{waypoint_index} - ({target_waypoint[0]:.2f}, {target_waypoint[1]:.2f})m！[/bold green]")
                            console.print(f"[dim]最终距离: {distance*100:.2f} cm | 稳定时长: {stable_duration:.2f}s | 控制用时: {total_control_time:.2f}s[/dim]")

                            if cfg.PLANE_AUTO_NEXT_WAYPOINT:
                                console.print(f"[cyan]自动切换 → {waypoint_desc} - ({next_waypoint[0]:.2f}, {next_waypoint[1]:.2f})m (按Ctrl+C退出)[/cyan]\n")
                            else:
                                console.print(f"[yellow]按 Enter 前往 {waypoint_desc} - ({next_waypoint[0]:.2f}, {next_waypoint[1]:.2f})m，或Ctrl+C退出...[/yellow]\n")

                            # 悬停并重置PID
                            for _ in range(5):
                                send_stick_control(mqtt_client)
                                time.sleep(0.01)
                            controller.reset()
                            reached = True
                            in_tolerance_since = None

                            # 根据模式决定是否等待用户输入
                            if cfg.PLANE_AUTO_NEXT_WAYPOINT:
                                # 自动模式：直接切换
                                waypoint_index = next_index
                                target_waypoint = next_waypoint
                                console.print(f"[bold cyan]→ {waypoint_desc} - ({target_waypoint[0]:.2f}, {target_waypoint[1]:.2f})m[/bold cyan]\n")
                                reached = False
                                control_start_time = time.time()
                                loop_count = 0
                            else:
                                # 手动模式：等待键盘输入
                                try:
                                    input()
                                    waypoint_index = next_index
                                    target_waypoint = next_waypoint
                                    console.print(f"[bold cyan]切换目标 → {waypoint_desc} - ({target_waypoint[0]:.2f}, {target_waypoint[1]:.2f})m[/bold cyan]\n")
                                    reached = False
                                    control_start_time = time.time()
                                    loop_count = 0
                                except KeyboardInterrupt:
                                    break
                            continue
                else:
                    # 离开阈值范围，重置计时器
                    if in_tolerance_since is not None:
                        console.print(f"[yellow]✗ 偏离目标 (距离:{distance*100:.2f}cm)，重置稳定计时[/yellow]")
                        in_tolerance_since = None

                # PID计算并发送控制指令
                current_time = time.time()
                roll_offset, pitch_offset, pid_components = controller.compute(
                    error_x_body, error_y_body,
                    0.0, 0.0,
                    current_time
                )

                roll = int(cfg.NEUTRAL + roll_offset)
                pitch = int(cfg.NEUTRAL + pitch_offset)
                send_stick_control(mqtt_client, roll=roll, pitch=pitch)

            # 每10次循环打印详细信息
            if loop_count % 2 == 0:
                error_x = target_x - current_x
                error_y = target_y - current_y
                kp_scale = controller.x_pid.kp / controller.kp_base if gain_scheduling_enabled else 1.0
                kd_scale = controller.x_pid.kd / controller.kd_base if gain_scheduling_enabled else 1.0
                info_parts = [
                    f"[cyan]#{loop_count:04d}[/cyan]",
                    f"WP{waypoint_index}",
                    f"目标({target_x:+.2f},{target_y:+.2f})",
                    f"当前({current_x:+.2f},{current_y:+.2f})",
                    f"距{distance*100:5.1f}cm"
                ]
                if gain_scheduling_enabled:
                    info_parts.append(f"[yellow]Kp×{kp_scale:.2f} Kd×{kd_scale:.2f}[/yellow]")

                info_parts.append(f"Out:P{pitch_offset:+5.0f}/R{roll_offset:+5.0f}")
                info_parts.append(f"X(P{pid_components['x'][0]:+5.0f}/I{pid_components['x'][1]:+5.0f}/D{pid_components['x'][2]:+5.0f})")
                info_parts.append(f"Y(P{pid_components['y'][0]:+5.0f}/I{pid_components['y'][1]:+5.0f}/D{pid_components['y'][2]:+5.0f})")
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
                    x_pid_p=pid_components['x'][0],
                    x_pid_i=pid_components['x'][1],
                    x_pid_d=pid_components['x'][2],
                    # PID components for Y (Roll)
                    y_pid_p=pid_components['y'][0],
                    y_pid_i=pid_components['y'][1],
                    y_pid_d=pid_components['y'][2]
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


if __name__ == '__main__':
    exit(main())
