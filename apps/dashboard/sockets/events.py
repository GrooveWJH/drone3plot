"""Socket.IO event wiring."""

from __future__ import annotations

from typing import Any, cast

from flask import current_app
from flask_socketio import SocketIO, emit

from dashboard.services.mission_executor import MissionExecutor
from dashboard.services.runtime_hub import RuntimeHub

TELEMETRY_NAMESPACE = "/telemetry"
POSE_NAMESPACE = "/pose"
MISSION_NAMESPACE = "/mission"


def register_socketio_events(
    socketio: SocketIO, runtime_hub: RuntimeHub, mission_executor: MissionExecutor
) -> None:
    """Register namespaces and bootstrap telemetry push events."""

    def _pose_loop():
        socketio_sleep = cast(Any, socketio.sleep)
        while True:
            if runtime_hub.slam.pose:
                socketio.emit(
                    "pose", runtime_hub.slam.pose.latest(), namespace=POSE_NAMESPACE
                )
            socketio_sleep(runtime_hub._app_config.get("POSE_SOCKET_RATE", 0.2))

    def _telemetry_loop():
        socketio_sleep = cast(Any, socketio.sleep)
        while True:
            if runtime_hub.drone.telemetry:
                socketio.emit(
                    "telemetry",
                    runtime_hub.drone.telemetry.latest_dict(),
                    namespace=TELEMETRY_NAMESPACE,
                )
            socketio_sleep(0.2)

    def _mission_loop():
        socketio_sleep = cast(Any, socketio.sleep)
        last_phase = None
        done_run_id = None
        while True:
            payload = mission_executor.status()
            run = payload.get("run", {})
            phase = run.get("phase")
            run_id = run.get("run_id")
            socketio.emit("mission:update", payload, namespace=MISSION_NAMESPACE)
            if phase != last_phase:
                socketio.emit(
                    "mission:phase",
                    {"run_id": run_id, "phase": phase},
                    namespace=MISSION_NAMESPACE,
                )
                last_phase = phase
            if phase in {"COMPLETED", "FAILED", "ABORTED"} and run_id != done_run_id:
                socketio.emit(
                    "mission:done",
                    {"run_id": run_id, "phase": phase, "error": run.get("error")},
                    namespace=MISSION_NAMESPACE,
                )
                done_run_id = run_id
            socketio_sleep(0.5)

    socketio.start_background_task(_pose_loop)
    socketio.start_background_task(_telemetry_loop)
    socketio.start_background_task(_mission_loop)

    @socketio.on("connect", namespace=TELEMETRY_NAMESPACE)
    def _handle_connect():
        hub = current_app.extensions.get("runtime_hub")
        if hub and hub.drone.telemetry:
            emit("telemetry", hub.drone.telemetry.latest_dict())

    @socketio.on("connect", namespace=POSE_NAMESPACE)
    def _handle_pose_connect():
        hub = current_app.extensions.get("runtime_hub")
        if hub and hub.slam.pose:
            emit("pose", hub.slam.pose.latest())

    @socketio.on("connect", namespace=MISSION_NAMESPACE)
    def _handle_mission_connect():
        executor = current_app.extensions.get("mission_executor")
        if executor:
            emit("mission:update", executor.status())
