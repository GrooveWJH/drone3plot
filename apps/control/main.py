#!/usr/bin/env python3
"""起飞 -> 执行 complex 航迹 -> 回原点 -> 降落."""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ is None:
    project_root = Path(__file__).resolve().parents[2]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

from apps.control.bootstrap import ensure_pydjimqtt

ensure_pydjimqtt()

import typer  # noqa: E402
from pydjimqtt import send_stick_control, setup_drc_connection, stop_heartbeat  # noqa: E402
from rich.console import Console  # noqa: E402
from rich.panel import Panel  # noqa: E402

from apps.control import config as cfg  # noqa: E402
from apps.control.core.datasource import create_datasource  # noqa: E402
from apps.control.core.mission_runner import (  # noqa: E402
    MissionPoint,
    MissionSpec,
    apply_mission_to_config,
    build_random_mission,
    load_mission_from_file,
    run_complex_mission,
)
from apps.control.core.pose_service import PoseService  # noqa: E402
from apps.control.main_takeoff import TakeoffState, _arm_drone, _land, _run_takeoff  # noqa: E402


app = typer.Typer(add_completion=False)


@app.command()
def main(
    file: Path | None = typer.Option(None, "--file", help="航点文件路径（json）"),
    count: int = typer.Option(5, "--count", help="随机航点数量"),
    final: str | None = typer.Option(None, "--final", help="最终点 x,y,z,yaw（默认最后一个航点）"),
) -> None:
    console = Console()
    console.print(Panel.fit("[bold cyan]起飞 → complex → 回原点 → 降落[/bold cyan]", border_style="cyan"))

    if file:
        spec = load_mission_from_file(file)
    else:
        spec = build_random_mission(count)
    final_point = spec.final
    if final:
        parts = [p.strip() for p in final.split(",")]
        if len(parts) != 4:
            raise typer.BadParameter("final 必须为 x,y,z,yaw")
        final_point = MissionPoint(float(parts[0]), float(parts[1]), float(parts[2]), float(parts[3]))
    spec = MissionSpec(
        initial=spec.initial,
        waypoints=spec.waypoints,
        final=final_point,
    )
    apply_mission_to_config(spec)

    mqtt = heartbeat = None
    state = TakeoffState()
    try:
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

        _arm_drone(mqtt, console)
        if not _run_takeoff(mqtt, console, state, pose_service, auto_land_on_fail=True):
            console.print("[red]✗ 起飞失败，已执行降落[/red]")
            raise typer.Exit(code=1)

        datasource = create_datasource(mqtt, cfg.SLAM_POSE_TOPIC, cfg.SLAM_YAW_TOPIC)
        run_complex_mission(mqtt=mqtt, datasource=datasource, console=console, spec=spec)
        console.print("[yellow]已返回原点，开始降落[/yellow]")
        _land(mqtt, console, state, pose_service)

    except KeyboardInterrupt:
        console.print("\n[yellow]中断退出[/yellow]")
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


if __name__ == "__main__":
    app()
