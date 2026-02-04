#!/usr/bin/env python3
"""
Yaw角PID控制器 - 主程序
使用统一的control模块重构版本

功能：
- 使用 SLAM yaw 数据 (slam/yaw)
- 通过PID算法控制无人机旋转到目标Yaw角
- 只控制Yaw角，不控制位置和高度
- 支持多个目标角度循环测试

使用方法：
1. 在 control/config.py 中配置 SLAM 话题:
   - cfg.SLAM_POSE_TOPIC, cfg.SLAM_YAW_TOPIC
2. 手动让无人机起飞到1m高度
3. 启动本程序: python -m apps.control.main_yaw
4. 无人机按顺序旋转到各个目标角度
5. 每到达一个角度，等待按 Enter 键
6. 自动前往下一个目标角度，循环往复
7. 按 Ctrl+C 退出程序
"""

import time
import random
import sys
from pathlib import Path

if __package__ is None:
    project_root = Path(__file__).resolve().parents[2]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

from apps.control.bootstrap import ensure_pydjimqtt

ensure_pydjimqtt()

from pydjimqtt import MQTTClient, start_heartbeat, stop_heartbeat, send_stick_control  # noqa: E402
from rich.console import Console  # noqa: E402
from rich.panel import Panel  # noqa: E402

from apps.control import config as cfg  # noqa: E402
from apps.control.core.controller import YawOnlyController, get_yaw_error  # noqa: E402
from apps.control.core.datasource import create_datasource  # noqa: E402
from apps.control.core.yaw_logic import yaw_control_step  # noqa: E402
from apps.control.io.logger import DataLogger  # noqa: E402


def generate_random_angle(current_angle, min_diff=30):
    """
    生成随机目标角度（确保与当前角度差值大于min_diff）

    Args:
        current_angle: 当前目标角度（度）
        min_diff: 最小角度差（度）

    Returns:
        随机角度（度），范围 [-180, 180]
    """
    while True:
        # 生成 -180 到 180 之间的随机角度
        new_angle = random.uniform(-180, 180)
        # 计算角度差（考虑±180°边界）
        angle_diff = abs(get_yaw_error(new_angle, current_angle))
        if angle_diff >= min_diff:
            return new_angle


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
            return now, None
        return in_tolerance_since, now - in_tolerance_since
    if in_tolerance_since is not None and not suppress_exit_log:
        console.print(exit_message)
    return None, None


def main():
    console = Console()

    # 根据配置决定使用固定目标还是随机目标
    if cfg.USE_RANDOM_ANGLES:
        mode_info = (
            f"[dim]模式: 随机角度生成 (最小角度差: {cfg.RANDOM_ANGLE_MIN_DIFF}°)[/dim]"
        )
    else:
        targets_str = "\n".join(
            [f"    目标{i}: {yaw}°" for i, yaw in enumerate(cfg.TARGET_YAWS)]
        )
        mode_info = (
            f"[dim]目标数量: {len(cfg.TARGET_YAWS)}[/dim]\n[dim]{targets_str}[/dim]"
        )

    auto_mode_info = (
        "[yellow]自动模式: 已启用[/yellow]"
        if cfg.AUTO_NEXT_TARGET
        else "[dim]手动模式: 到达后需按Enter[/dim]"
    )

    # 显示数据源配置
    data_source_info = f"[yellow]航向角源: SLAM[/yellow] ({cfg.SLAM_YAW_TOPIC})"

    console.print(
        Panel.fit(
            "[bold cyan]Yaw角PID控制器 - 重构版本[/bold cyan]\n"
            f"{data_source_info}\n"
            f"{mode_info}\n"
            f"{auto_mode_info}\n"
            f"[dim]到达阈值: ±{cfg.TOLERANCE_YAW:.1f}°[/dim]\n"
            f"[dim]PID参数: Kp={cfg.KP_YAW}, Ki={cfg.KI_YAW}, Kd={cfg.KD_YAW}[/dim]",
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
        console.print("[green]✓ 数据源已创建: 航向角=SLAM[/green]")
    except Exception as e:
        console.print(f"[red]✗ 数据源创建失败: {e}[/red]")
        stop_heartbeat(heartbeat_thread)
        mqtt_client.disconnect()
        return 1

    # 4. 初始化控制器和目标
    controller = YawOnlyController(
        cfg.KP_YAW,
        cfg.KI_YAW,
        cfg.KD_YAW,
        cfg.MAX_YAW_STICK_OUTPUT,
        i_activation_error=cfg.YAW_I_ACTIVATION_ERROR,
    )

    # 初始化目标角度
    if cfg.USE_RANDOM_ANGLES:
        target_yaw = 0  # 初始目标设为0度
        target_index = 0
    else:
        target_index = 0
        target_yaw = cfg.TARGET_YAWS[target_index]

    # 5. 初始化数据记录器
    logger = DataLogger(
        enabled=cfg.ENABLE_DATA_LOGGING,
        field_set="yaw_only",
        csv_name="yaw_control_data.csv",
        subdir="yaw",
    )
    if logger.enabled:
        console.print(f"[green]✓ 数据记录已启用: {logger.get_log_dir()}[/green]")

    console.print("\n[bold green]✓ 初始化完成！开始控制...[/bold green]")
    if cfg.USE_RANDOM_ANGLES:
        console.print(
            f"[cyan]首个目标: 随机目标{target_index} - {target_yaw:.1f}°[/cyan]"
        )
    else:
        console.print(f"[cyan]首个目标: 目标{target_index} - {target_yaw:.1f}°[/cyan]")
    console.print("[yellow]提示: 按Ctrl+C可随时退出[/yellow]\n")

    # 控制循环
    control_interval = 1.0 / cfg.CONTROL_FREQUENCY
    reached = False
    in_tolerance_since = None  # 记录进入阈值范围的时间戳
    control_start_time = time.time()  # 记录开始控制的时间

    try:
        while True:
            loop_start = time.time()

            # 读取航向角数据（使用统一数据源接口）
            current_yaw = datasource.get_yaw()
            if current_yaw is None:
                console.print("[yellow]⚠ 等待航向角数据...[/yellow]")
                time.sleep(0.1)
                continue

            error_yaw = get_yaw_error(target_yaw, current_yaw)
            abs_error = abs(error_yaw)

            # 判断是否到达（带时间稳定性检查）
            if not reached:
                in_tolerance_since, stable_duration = update_stability_timer(
                    in_range=abs_error < cfg.TOLERANCE_YAW,
                    in_tolerance_since=in_tolerance_since,
                    now=loop_start,
                    console=console,
                    enter_message=(
                        f"[yellow]⏱ 进入阈值范围 (误差:{error_yaw:+.2f}°)，等待稳定 {cfg.YAW_ARRIVAL_STABLE_TIME}s...[/yellow]"
                    ),
                    exit_message=(
                        f"[yellow]✗ 偏离目标 (误差:{error_yaw:+.2f}°)，重置稳定计时[/yellow]"
                    ),
                )
                if (
                    stable_duration is not None
                    and stable_duration >= cfg.YAW_ARRIVAL_STABLE_TIME
                ):
                    # 真正到达！
                    total_control_time = time.time() - control_start_time

                    # 计算下一个目标
                    if cfg.USE_RANDOM_ANGLES:
                        next_target = generate_random_angle(
                            target_yaw, cfg.RANDOM_ANGLE_MIN_DIFF
                        )
                        next_index = target_index + 1
                        target_desc = f"随机目标{next_index}"
                    else:
                        next_index = (target_index + 1) % len(cfg.TARGET_YAWS)
                        next_target = cfg.TARGET_YAWS[next_index]
                        target_desc = f"目标{next_index}"

                    console.print(
                        f"\n[bold green]✓ 已到达目标{target_index} - {target_yaw:.1f}°！[/bold green]"
                    )
                    console.print(
                        f"[dim]最终误差: {error_yaw:+.2f}° | 稳定时长: {stable_duration:.2f}s | 控制用时: {total_control_time:.2f}s[/dim]"
                    )

                    if cfg.AUTO_NEXT_TARGET:
                        console.print(
                            f"[cyan]自动切换 → {target_desc} - {next_target:.1f}° (按Ctrl+C退出)[/cyan]\n"
                        )
                    else:
                        console.print(
                            f"[yellow]按 Enter 前往 {target_desc} - {next_target:.1f}°，或Ctrl+C退出...[/yellow]\n"
                        )

                    # 悬停并重置PID
                    for _ in range(5):
                        send_stick_control(mqtt_client)
                        time.sleep(0.01)
                    controller.reset()
                    reached = True
                    in_tolerance_since = None

                    # 根据模式决定是否等待用户输入
                    if cfg.AUTO_NEXT_TARGET:
                        # 自动模式：直接切换
                        target_index = next_index
                        target_yaw = next_target
                        console.print(
                            f"[bold cyan]→ {target_desc} - {target_yaw:.1f}°[/bold cyan]\n"
                        )
                        reached = False
                        control_start_time = time.time()
                    else:
                        # 手动模式：等待键盘输入
                        try:
                            input()
                            target_index = next_index
                            target_yaw = next_target
                            console.print(
                                f"[bold cyan]切换目标 → {target_desc} - {target_yaw:.1f}°[/bold cyan]\n"
                            )
                            reached = False
                            control_start_time = time.time()
                        except KeyboardInterrupt:
                            break
                    continue

            # PID计算并发送控制指令
            current_time = time.time()
            yaw_offset, pid_components, yaw = yaw_control_step(
                cfg,
                controller,
                error_yaw,
                mqtt_client,
                current_time,
            )

            # 记录数据（包含PID分量）
            logger.log(
                timestamp=current_time,
                target_yaw=target_yaw,
                current_yaw=current_yaw,
                error_yaw=error_yaw,
                yaw_offset=yaw_offset,
                yaw_absolute=yaw,
                target_index=target_index,
                yaw_pid_p=pid_components[0],
                yaw_pid_i=pid_components[1],
                yaw_pid_d=pid_components[2],
            )

            # 每次循环都打印状态（实时监控杆量输出）
            console.print(
                f"[cyan]目标: {target_yaw:+6.1f}° | "
                f"当前: {current_yaw:+6.1f}° | "
                f"误差: {error_yaw:+6.2f}° | "
                f"杆量: {yaw_offset:+6.0f} ({yaw})[/cyan]"
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
