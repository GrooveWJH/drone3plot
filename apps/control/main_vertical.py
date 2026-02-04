#!/usr/bin/env python3
"""
垂直高度控制器 - 主程序

功能：
- 使用 SLAM Z 或无人机 relative height 作为高度参考
- 通过PID算法控制无人机达到目标高度
- 仅控制油门（throttle），不控制XY和Yaw

使用方法：
1. 在 control/config.py 中配置高度数据源与目标高度
2. 手动完成 DRC 授权与进入 DRC 模式
3. 启动本程序: python -m apps.control.main_vertical
4. 按 Ctrl+C 退出程序
"""

from __future__ import annotations

import time
import sys
from pathlib import Path
from typing import Optional

if __package__ is None:
    project_root = Path(__file__).resolve().parents[2]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

from apps.control.bootstrap import ensure_pydjimqtt

ensure_pydjimqtt()

from pydjimqtt import MQTTClient, send_stick_control  # noqa: E402
from rich.console import Console  # noqa: E402
from rich.panel import Panel  # noqa: E402

from apps.control.core.pose_service import PoseService  # noqa: E402
from apps.control.config import (  # noqa: E402
    GATEWAY_SN,
    MQTT_CONFIG,
    SLAM_POSE_TOPIC,
    SLAM_YAW_TOPIC,
    NEUTRAL,
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
    ENABLE_DATA_LOGGING,
)
from apps.control.core.pid import PIDController  # noqa: E402
from apps.control.io.logger import DataLogger  # noqa: E402


def _clamp(value: float, min_value: int, max_value: int) -> int:
    return int(max(min_value, min(max_value, value)))


def main() -> int:
    console = Console()
    height_source = VERTICAL_HEIGHT_SOURCE.strip().lower()
    if height_source not in {"slam", "relative"}:
        console.print(f"[red]✗ 无效的高度来源: {VERTICAL_HEIGHT_SOURCE}[/red]")
        return 1

    console.print(
        Panel.fit(
            "[bold cyan]垂直高度控制器[/bold cyan]\n"
            f"[yellow]高度来源: {height_source}[/yellow]\n"
            f"[dim]目标高度: {VERTICAL_TARGET_HEIGHT:.2f} m | 容差: ±{VERTICAL_TOLERANCE:.2f} m[/dim]\n"
            f"[dim]PID: Kp={VERTICAL_KP}, Ki={VERTICAL_KI}, Kd={VERTICAL_KD}[/dim]\n"
            "[dim]提示: 需先完成 DRC 授权 + 进入 DRC 模式[/dim]",
            border_style="cyan",
        )
    )

    console.print("\n[cyan]━━━ 步骤 1/2: 连接MQTT ━━━[/cyan]")
    mqtt_client = MQTTClient(GATEWAY_SN, MQTT_CONFIG)
    try:
        mqtt_client.connect()
        console.print(
            f"[green]✓ MQTT已连接: {MQTT_CONFIG['host']}:{MQTT_CONFIG['port']}[/green]"
        )
    except Exception as e:
        console.print(f"[red]✗ MQTT连接失败: {e}[/red]")
        return 1

    pose_service: Optional[PoseService] = None
    slam_zero: Optional[float] = None
    if height_source == "slam":
        pose_service = PoseService(mqtt_client, SLAM_POSE_TOPIC, SLAM_YAW_TOPIC)
        console.print(f"[green]✓ 已订阅 SLAM: {SLAM_POSE_TOPIC}[/green]")

    pid = PIDController(
        VERTICAL_KP,
        VERTICAL_KI,
        VERTICAL_KD,
        output_limit=VERTICAL_MAX_THROTTLE_OUTPUT,
        i_activation_threshold=VERTICAL_I_ACTIVATION_ERROR,
    )

    logger = DataLogger(
        enabled=ENABLE_DATA_LOGGING,
        field_set="vertical",
        csv_name="vertical_control_data.csv",
        subdir="vertical",
    )
    if logger.enabled:
        console.print(f"[green]✓ 数据记录已启用: {logger.get_log_dir()}[/green]")

    console.print("\n[bold green]✓ 初始化完成！开始控制...[/bold green]")
    console.print("[yellow]提示: 按Ctrl+C可随时退出[/yellow]\n")

    control_interval = 1.0 / VERTICAL_CONTROL_FREQUENCY
    in_tolerance_since: Optional[float] = None
    reached = False
    last_print = 0.0

    def read_height() -> Optional[float]:
        nonlocal slam_zero
        if height_source == "relative":
            return mqtt_client.get_relative_height()
        if pose_service is None:
            return None
        pose = pose_service.latest()
        z = pose.get("z")
        if z is None:
            return None
        if VERTICAL_SLAM_ZERO_AT_START:
            if slam_zero is None:
                slam_zero = z
                console.print(
                    f"[cyan]SLAM 初始高度: {slam_zero:.3f} m (置为 0点)[/cyan]"
                )
            return z - slam_zero
        return z

    try:
        while True:
            loop_start = time.time()
            current_height = read_height()
            if current_height is None:
                if loop_start - last_print > 0.5:
                    console.print("[yellow]⚠ 等待高度数据...[/yellow]")
                    last_print = loop_start
                time.sleep(0.1)
                continue

            error = VERTICAL_TARGET_HEIGHT - current_height
            if not reached:
                output, (p_term, i_term, d_term) = pid.compute(error, loop_start)
                throttle = _clamp(NEUTRAL + output, 364, 1684)

                send_stick_control(mqtt_client, throttle=throttle)
                logger.log(
                    timestamp=loop_start,
                    target_height=VERTICAL_TARGET_HEIGHT,
                    current_height=current_height,
                    error_height=error,
                    throttle_offset=output,
                    throttle_absolute=throttle,
                    height_pid_p=p_term,
                    height_pid_i=i_term,
                    height_pid_d=d_term,
                )

                if abs(error) <= VERTICAL_TOLERANCE:
                    if in_tolerance_since is None:
                        in_tolerance_since = loop_start
                    elif (
                        loop_start - in_tolerance_since >= VERTICAL_ARRIVAL_STABLE_TIME
                    ):
                        send_stick_control(mqtt_client, throttle=NEUTRAL)
                        reached = True
                        console.print(
                            f"[bold green]✓ 高度已到达目标 ({VERTICAL_TARGET_HEIGHT:.2f}m)[/bold green]"
                        )
                else:
                    in_tolerance_since = None
            else:
                throttle = NEUTRAL
                send_stick_control(mqtt_client, throttle=throttle)
                logger.log(
                    timestamp=loop_start,
                    target_height=VERTICAL_TARGET_HEIGHT,
                    current_height=current_height,
                    error_height=error,
                    throttle_offset=0.0,
                    throttle_absolute=throttle,
                    height_pid_p=0.0,
                    height_pid_i=0.0,
                    height_pid_d=0.0,
                )

            if loop_start - last_print > 0.5:
                if reached:
                    console.print(
                        f"[dim]height={current_height:.3f}m "
                        f"err={error:+.3f} "
                        f"thr={throttle} "
                        "P=+0.0 I=+0.0 D=+0.0[/dim]"
                    )
                else:
                    console.print(
                        f"[dim]height={current_height:.3f}m "
                        f"err={error:+.3f} "
                        f"thr={throttle} "
                        f"P={p_term:+.1f} I={i_term:+.1f} D={d_term:+.1f}[/dim]"
                    )
                last_print = loop_start

            elapsed = time.time() - loop_start
            if elapsed < control_interval:
                time.sleep(control_interval - elapsed)
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopping...[/yellow]")
    finally:
        send_stick_control(mqtt_client, throttle=NEUTRAL)
        mqtt_client.disconnect()
        logger.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
