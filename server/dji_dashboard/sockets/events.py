"""Socket.IO event wiring."""
from __future__ import annotations

from flask import current_app
from flask_socketio import SocketIO, emit

from dji_dashboard.services import ServiceRegistry

TELEMETRY_NAMESPACE = "/telemetry"
POSE_NAMESPACE = "/pose"


def register_socketio_events(socketio: SocketIO, registry: ServiceRegistry) -> None:
    """Register namespaces and bootstrap telemetry push events."""

    if registry.telemetry:
        registry.telemetry.subscribe(lambda snapshot: socketio.emit(
            "telemetry",
            snapshot.model_dump(),
            namespace=TELEMETRY_NAMESPACE,
        ))

    def _pose_loop():
        while True:
            if registry.pose:
                socketio.emit("pose", registry.pose.latest(), namespace=POSE_NAMESPACE)
            socketio.sleep(registry.config.get("POSE_SOCKET_RATE", 0.2))

    socketio.start_background_task(_pose_loop)

    @socketio.on("connect", namespace=TELEMETRY_NAMESPACE)
    def _handle_connect():
        registry = current_app.extensions.get("services")
        if registry and registry.telemetry:
            emit("telemetry", registry.telemetry.latest_dict())

    @socketio.on("connect", namespace=POSE_NAMESPACE)
    def _handle_pose_connect():
        registry = current_app.extensions.get("services")
        if registry and registry.pose:
            emit("pose", registry.pose.latest())
