#!/usr/bin/env python3
"""
起飞脚本：
- 请求 DRC 控制权限并进入 DRC 模式
- 外八解锁
- 起飞到目标高度（默认 1m）
- 达到高度后仅保留心跳，不再发送杆量
"""

from __future__ import annotations

import sys
import time
import select
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Protocol

if __package__ is None:
    project_root = Path(__file__).resolve().parents[2]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

from apps.control.bootstrap import ensure_pydjimqtt

ensure_pydjimqtt()

import typer  # noqa: E402
from pydjimqtt import send_stick_control, setup_drc_connection, stop_heartbeat  # noqa: E402
from pydjimqtt.primitives import send_stick_repeatedly  # noqa: E402
from rich.console import Console  # noqa: E402
from rich.panel import Panel  # noqa: E402

from apps.control import config as cfg  # noqa: E402
from apps.control.core.pid import PIDController  # noqa: E402
from apps.control.core.pose_service import PoseService  # noqa: E402


class PoseFeed(Protocol):
    def latest(self) -> dict[str, object | None]:
        ...


def _wait_for_slam_height(
    pose_service: PoseFeed, timeout: float = 30.0
) -> Optional[float]:
    deadline = time.time() + timeout
    while time.time() < deadline:
        pose = pose_service.latest()
        height = pose.get("z") if pose else None
        if height is not None:
            return height
        time.sleep(0.1)
    return None


def _clamp(value: float, min_value: int, max_value: int) -> int:
    return int(max(min_value, min(max_value, value)))


def _try_read_command() -> Optional[str]:
    if select.select([sys.stdin], [], [], 0.0)[0]:
        return sys.stdin.readline().strip().lower()
    return None


@dataclass
class TakeoffState:
    airborne: bool = False


def _land(
    mqtt,
    console: Console,
    state: TakeoffState,
    pose_service: PoseFeed,
    stable_window: float = 3.0,
    stable_delta: float = 0.1,
) -> bool:
    throttle_low = 364
    last_change_time = time.time()
    last_pose = pose_service.latest()
    last_height = last_pose.get("z") if last_pose else None
    console.print("[yellow]开始降落：油门拉到最低[/yellow]")
    while True:
        cmd = _try_read_command()
        if cmd == "up":
            console.print("[cyan]收到起飞指令，停止降落[/cyan]")
            return False
        pose = pose_service.latest()
        height = pose.get("z") if pose else None
        if height is not None and last_height is not None:
            if abs(height - last_height) >= stable_delta:
                last_change_time = time.time()
                last_height = height
        elif height is not None:
            last_height = height

        if time.time() - last_change_time >= stable_window:
            console.print("[green]✓ 降落完成，停止发送杆量[/green]")
            state.airborne = False
            return True

        send_stick_control(mqtt, throttle=throttle_low)
        time.sleep(0.1)


def _arm_drone(mqtt, console: Console) -> None:
    console.print("\n[cyan]━━━ 外八解锁 ━━━[/cyan]")
    send_stick_repeatedly(
        mqtt,
        roll=1684,
        pitch=364,
        throttle=364,
        yaw=364,
        duration=3.0,
        frequency=10,
    )
    console.print("[green]✓ 解锁完成[/green]")


def _run_takeoff(
    mqtt,
    console: Console,
    state: TakeoffState,
    pose_service: PoseFeed,
    auto_land_on_fail: bool = False,
) -> bool:
    target_height = cfg.VERTICAL_TARGET_HEIGHT
    height_tolerance = cfg.VERTICAL_TOLERANCE
    throttle_min = 364
    throttle_max = 1684

    height = _wait_for_slam_height(pose_service)
    if height is None:
        console.print("[red]✗ 未获取到高度数据[/red]")
        return False

    console.print(f"[green]✓ 当前相对高度: {height:.2f} m[/green]")
    if height >= target_height - height_tolerance:
        console.print(f"[green]✓ 已在目标高度范围内: {height:.2f} m[/green]")
        state.airborne = True
        return True

    pid = PIDController(
        cfg.VERTICAL_KP,
        cfg.VERTICAL_KI,
        cfg.VERTICAL_KD,
        output_limit=cfg.VERTICAL_MAX_THROTTLE_OUTPUT,
        i_activation_threshold=cfg.VERTICAL_I_ACTIVATION_ERROR,
    )

    console.print("[cyan]实时高度输出已开启[/cyan]")
    control_interval = 1.0 / cfg.VERTICAL_CONTROL_FREQUENCY
    in_tolerance_since: Optional[float] = None
    last_print = 0.0
    start_time = time.time()

    while True:
        loop_start = time.time()
        if loop_start - start_time >= 10.0:
            console.print("[red]✗ 起飞超时：10s内未达到目标高度[/red]")
            state.airborne = False
            if auto_land_on_fail:
                console.print("[yellow]起飞失败，开始自动降落[/yellow]")
                _land(mqtt, console, state, pose_service)
            return False

        pose = pose_service.latest()
        height = pose.get("z") if pose else None
        if height is None:
            time.sleep(0.1)
            continue

        error = target_height - height
        if abs(error) <= height_tolerance:
            if in_tolerance_since is None:
                in_tolerance_since = loop_start
                console.print(
                    f"[yellow]⏱ 进入高度阈值 (误差:{error:+.2f}m)，等待稳定 {cfg.VERTICAL_ARRIVAL_STABLE_TIME}s...[/yellow]"
                )
            elif loop_start - in_tolerance_since >= cfg.VERTICAL_ARRIVAL_STABLE_TIME:
                console.print(
                    f"[bold green]✓ 已到达目标高度: {height:.2f} m[/bold green]"
                )
                state.airborne = True
                return True
        else:
            in_tolerance_since = None

        output, _ = pid.compute(error, loop_start)
        throttle = _clamp(cfg.NEUTRAL + output, throttle_min, throttle_max)
        send_stick_control(mqtt, throttle=throttle)

        if loop_start - last_print >= 0.2:
            console.print(
                f"[cyan]高度: {height:+.2f} m | 误差: {error:+.2f} m | 油门: {throttle}[/cyan]"
            )
            last_print = loop_start

        sleep_time = control_interval - (time.time() - loop_start)
        if sleep_time > 0:
            time.sleep(sleep_time)


app = typer.Typer(add_completion=False, help="DRC 起飞/降落控制")


@app.command()
def main(
    auto_takeoff: bool = typer.Option(
        False,
        "--auto-takeoff",
        help="进入 DRC 后自动起飞（默认等待指令）",
    ),
) -> None:
    console = Console()

    console.print(
        Panel.fit(
            "[bold cyan]自动起飞[/bold cyan]\n"
            f"[dim]目标高度: {cfg.VERTICAL_TARGET_HEIGHT:.2f} m | 容差: ±{cfg.VERTICAL_TOLERANCE:.2f} m[/dim]\n"
            f"[dim]控制频率: {cfg.VERTICAL_CONTROL_FREQUENCY} Hz[/dim]\n"
            "[dim]到达后仅保留心跳[/dim]",
            border_style="cyan",
        )
    )

    mqtt = None
    heartbeat = None
    state = TakeoffState()
    try:
        console.print("\n[cyan]━━━ 步骤 1/3: 连接并进入 DRC ━━━[/cyan]")
        mqtt, _, heartbeat = setup_drc_connection(
            cfg.GATEWAY_SN,
            cfg.MQTT_CONFIG,
            user_id=cfg.DRC_USER_ID,
            user_callsign=cfg.DRC_USER_CALLSIGN,
            osd_frequency=cfg.DRC_OSD_FREQUENCY,
            hsi_frequency=cfg.DRC_HSI_FREQUENCY,
            heartbeat_interval=cfg.DRC_HEARTBEAT_INTERVAL,
            wait_for_user=False,
            skip_drc_setup=False,
        )

        pose_service = PoseService(mqtt, cfg.SLAM_POSE_TOPIC, cfg.SLAM_YAW_TOPIC)

        if not auto_takeoff:
            console.print(
                "[yellow]已进入 DRC，等待指令：输入 up 回车开始起飞；输入 down 回车降落；Ctrl+C 退出。[/yellow]"
            )
            while True:
                user_input = input().strip().lower()
                if user_input == "up":
                    break
                if user_input == "down":
                    _land(mqtt, console, state, pose_service)
                time.sleep(0.1)

        console.print("\n[cyan]━━━ 步骤 2/3: 解锁并起飞 ━━━[/cyan]")
        if not state.airborne:
            _arm_drone(mqtt, console)
        else:
            console.print("[yellow]检测到已在空中，跳过外八解锁[/yellow]")
        if not _run_takeoff(mqtt, console, state, pose_service, auto_land_on_fail=True):
            console.print("[red]✗ 起飞失败，已执行降落，等待新指令[/red]")

        console.print("[yellow]进入保持模式：仅心跳，不再发送杆量[/yellow]")
        send_stick_repeatedly(mqtt, duration=1.0, frequency=10)
        while True:
            console.print(
                "[dim]输入 down 开始降落；输入 up 重新起飞；Ctrl+C 退出。[/dim]"
            )
            user_input = input().strip().lower()
            if user_input == "down":
                landed = _land(mqtt, console, state, pose_service)
                if landed:
                    continue
            elif user_input == "up":
                console.print("[cyan]重新起飞...[/cyan]")
                if not state.airborne:
                    _arm_drone(mqtt, console)
                else:
                    console.print("[yellow]检测到已在空中，跳过外八解锁[/yellow]")
                if not _run_takeoff(
                    mqtt, console, state, pose_service, auto_land_on_fail=True
                ):
                    console.print("[red]✗ 起飞失败，已执行降落，等待新指令[/red]")
                continue
            time.sleep(0.2)

    except KeyboardInterrupt:
        console.print("\n[yellow]中断退出[/yellow]")
        raise typer.Exit(code=1)
    except Exception as exc:
        console.print(f"\n[red]✗ 发生错误: {exc}[/red]")
        raise typer.Exit(code=1)
    finally:
        if mqtt:
            try:
                send_stick_control(mqtt)
            except Exception:
                pass
        if heartbeat:
            stop_heartbeat(heartbeat)
        if mqtt:
            mqtt.disconnect()
        console.print("[green]✓ 已安全退出[/green]")
    raise typer.Exit(code=0)


if __name__ == "__main__":
    app()
