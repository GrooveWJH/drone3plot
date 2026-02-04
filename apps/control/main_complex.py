#!/usr/bin/env python3
"""
平面 + Yaw 联合控制（任务朝向 + 运动朝向）

逻辑：
1) ALIGN：对准“当前点 → 下一点”的方向
2) MOVE：直线飞行至下一航点（带 BRAKE/SETTLE）
3) VERTICAL：高度调整到目标 z
4) TASK：对准任务 yaw，保持 1 秒（拍照占位）

使用方法：
1. 在 control/config.py 配置 SLAM 话题与 PID 参数
2. 启动: python -m apps.control.main_complex
3. 按 Ctrl+C 退出
"""

import sys
import time
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
from apps.control.core.complex_runtime import init_context, init_phase, step_complex  # noqa: E402
from apps.control.core.complex_state import ControlState  # noqa: E402
from apps.control.core.controller import (
    PlaneController,
    YawOnlyController,
    get_yaw_error,
)  # noqa: E402
from apps.control.core.datasource import create_datasource  # noqa: E402
from apps.control.core.pid import PIDController  # noqa: E402
from apps.control.io.logger import DataLogger  # noqa: E402


def main() -> int:
    console = Console()

    mode_info = (
        "[dim]模式: 随机航点+随机Yaw[/dim]"
        if cfg.PLANE_USE_RANDOM_WAYPOINTS
        else "[dim]模式: 固定航点+固定Yaw[/dim]"
    )
    console.print(
        Panel.fit(
            "[bold cyan]平面+Yaw 联合控制[/bold cyan]\n"
            f"{mode_info}\n"
            f"[dim]平面到达阈值: {cfg.TOLERANCE_XY * 100:.1f} cm[/dim]\n"
            f"[dim]Yaw到达阈值: ±{cfg.TOLERANCE_YAW:.1f}°[/dim]\n"
            f"[dim]刹车保持: {cfg.PLANE_BRAKE_HOLD_TIME:.2f}s[/dim]",
            border_style="cyan",
        )
    )

    console.print("\n[cyan]━━━ 步骤 1/2: 连接MQTT ━━━[/cyan]")
    mqtt_client = MQTTClient(cfg.GATEWAY_SN, cfg.MQTT_CONFIG)
    try:
        mqtt_client.connect()
        console.print(
            f"[green]✓ MQTT已连接: {cfg.MQTT_CONFIG['host']}:{cfg.MQTT_CONFIG['port']}[/green]"
        )
    except Exception as exc:
        console.print(f"[red]✗ MQTT连接失败: {exc}[/red]")
        return 1

    console.print("\n[cyan]━━━ 步骤 2/2: 启动心跳 ━━━[/cyan]")
    heartbeat_thread = start_heartbeat(mqtt_client, interval=0.2)
    console.print("[green]✓ 心跳已启动 (5.0Hz)[/green]")

    console.print("\n[cyan]━━━ 创建数据源接口 ━━━[/cyan]")
    try:
        datasource = create_datasource(
            mqtt_client, cfg.SLAM_POSE_TOPIC, cfg.SLAM_YAW_TOPIC
        )
        console.print("[green]✓ 数据源已创建: 位置=SLAM, 航向=SLAM[/green]")
    except Exception as exc:
        console.print(f"[red]✗ 数据源创建失败: {exc}[/red]")
        stop_heartbeat(heartbeat_thread)
        mqtt_client.disconnect()
        return 1

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

    console.print("[yellow]等待初始位置/航向数据...[/yellow]")
    position = None
    current_yaw = None
    while position is None or current_yaw is None:
        position = datasource.get_position()
        current_yaw = datasource.get_yaw()
        time.sleep(0.1)

    logger = DataLogger(
        enabled=cfg.ENABLE_DATA_LOGGING,
        field_set="plane_yaw",
        csv_name="plane_yaw_data.csv",
        subdir="plane_yaw",
    )
    if logger.enabled:
        console.print(f"[green]✓ 数据记录已启用: {logger.get_log_dir()}[/green]")

    ctx = init_context(cfg, position, current_yaw)
    console.print("\n[bold green]✓ 初始化完成！开始控制...[/bold green]")
    console.print(
        f"[cyan]首个目标: 航点{ctx.waypoint_index} - ({ctx.current_waypoint[0]:.2f}, {ctx.current_waypoint[1]:.2f})m | 任务Yaw {ctx.current_target_yaw:.1f}°[/cyan]"
    )
    console.print("[yellow]提示: 按Ctrl+C可随时退出[/yellow]\n")

    control_interval = 1.0 / cfg.CONTROL_FREQUENCY
    state = ControlState(control_start_time=time.time())
    init_phase(cfg, state, ctx, position)

    try:
        while True:
            loop_start = time.time()
            state.loop_count += 1

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
                mqtt_client=mqtt_client,
                plane_approach=plane_approach,
                plane_settle=plane_settle,
                yaw_controller=yaw_controller,
                vertical_controller=vertical_controller,
            )

            if state.loop_count % 2 == 0:
                total_label = (
                    "?" if ctx.total_waypoints is None else str(ctx.total_waypoints)
                )
                target_z = 0.0 if info.target_z is None else info.target_z
                current_z = 0.0 if info.current_z is None else info.current_z
                console.print(
                    f"[cyan]#{state.loop_count:04d}[/cyan] | "
                    f"WP{ctx.waypoint_index}/{total_label} | "
                    f"{info.phase_label} | "
                    f"目标({info.target_x:+.2f},{info.target_y:+.2f},{target_z:+.2f},{info.target_yaw:+.1f}°) | "
                    f"当前({info.current_x:+.2f},{info.current_y:+.2f},{current_z:+.2f},{info.current_yaw:+.1f}°) | "
                    f"距{info.distance * 100:5.1f}cm | "
                    f"Out:P{info.pitch_offset:+5.0f}/R{info.roll_offset:+5.0f}/Y{info.yaw_offset:+5.0f}"
                )

                logger.log(
                    timestamp=loop_start,
                    target_x=info.target_x,
                    target_y=info.target_y,
                    target_yaw=info.yaw_target,
                    current_x=info.current_x,
                    current_y=info.current_y,
                    current_yaw=current_yaw,
                    error_x=info.target_x - info.current_x,
                    error_y=info.target_y - info.current_y,
                    error_yaw=get_yaw_error(info.yaw_target, current_yaw),
                    distance=info.distance,
                    roll_offset=info.roll_offset,
                    pitch_offset=info.pitch_offset,
                    yaw_offset=info.yaw_offset,
                    roll_absolute=info.roll,
                    pitch_absolute=info.pitch,
                    yaw_absolute=info.yaw,
                    waypoint_index=ctx.waypoint_index,
                    x_pid_p=info.pid_components["x"][0],
                    x_pid_i=info.pid_components["x"][1],
                    x_pid_d=info.pid_components["x"][2],
                    y_pid_p=info.pid_components["y"][0],
                    y_pid_i=info.pid_components["y"][1],
                    y_pid_d=info.pid_components["y"][2],
                    yaw_pid_p=info.yaw_pid_components[0],
                    yaw_pid_i=info.yaw_pid_components[1],
                    yaw_pid_d=info.yaw_pid_components[2],
                )

            sleep_time = control_interval - (time.time() - loop_start)
            if sleep_time > 0:
                time.sleep(sleep_time)

    except KeyboardInterrupt:
        console.print("\n\n[yellow]⚠ 收到中断信号[/yellow]\n")
    except Exception as exc:
        console.print(f"\n\n[red]✗ 发生错误: {exc}[/red]")
        console.print(f"[red]错误类型: {type(exc).__name__}[/red]")
        import traceback

        console.print(f"[dim]{traceback.format_exc()}[/dim]\n")
    finally:
        console.print("[cyan]━━━ 清理资源 ━━━[/cyan]")
        logger.close()
        console.print("[yellow]发送悬停指令...[/yellow]")
        for _ in range(5):
            send_stick_control(mqtt_client)
            time.sleep(0.1)
        stop_heartbeat(heartbeat_thread)
        console.print("[green]✓ 心跳已停止[/green]")
        mqtt_client.disconnect()
        console.print("[green]✓ MQTT已断开[/green]")
        datasource.stop()
        console.print("[green]✓ 数据源已停止 (SLAM)[/green]")
        console.print("\n[bold green]✓ 已安全退出[/bold green]\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
