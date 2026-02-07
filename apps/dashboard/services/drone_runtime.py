"""Drone runtime controlled by dashboard user input config."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from pydjimqtt.core import MQTTClient, ServiceCaller

from .camera import CameraService
from .control import ControlService
from .drc import DrcControlService
from .streaming import StreamingService
from .telemetry import TelemetryService
from .trajectory import TrajectoryService


@dataclass(frozen=True)
class DroneRuntimeStatus:
    state: str
    connected: bool
    gateway_sn: str
    host: str
    port: int
    drc_state: str | None
    drc_error: str | None


class DroneRuntime:
    """Owns mutable drone-side connection and services."""

    def __init__(self, app_config: Mapping[str, Any], active_config: Mapping[str, Any]):
        self._app_config = app_config
        self._active_config = active_config

        self.mqtt_client: MQTTClient | None = None
        self.service_caller: ServiceCaller | None = None
        self.telemetry: TelemetryService | None = None
        self.camera: CameraService | None = None
        self.control: ControlService | None = None
        self.streaming: StreamingService | None = None
        self.trajectory: TrajectoryService | None = None
        self.drc: DrcControlService | None = None

        self._connected = False

    def connect(self) -> None:
        if self._connected:
            return
        self._validate_required_config()

        gateway_sn = str(self._active_config.get("GATEWAY_SN", "") or "").strip()
        host = str(self._active_config.get("MQTT_HOST", "") or "").strip()
        port = int(self._active_config.get("MQTT_PORT", 0))

        mqtt_config = {
            "host": host,
            "port": port,
            "username": self._active_config.get("MQTT_USERNAME", ""),
            "password": self._active_config.get("MQTT_PASSWORD", ""),
        }
        client = MQTTClient(gateway_sn, mqtt_config)
        client.connect()

        caller = ServiceCaller(client)
        telemetry = TelemetryService(client, poll_hz=float(self._app_config.get("TELEMETRY_POLL_HZ", 2)))
        telemetry.start()

        self.mqtt_client = client
        self.service_caller = caller
        self.telemetry = telemetry
        self.camera = CameraService(client, tuple(self._app_config.get("AVAILABLE_LENSES", ("zoom",))))
        self.control = ControlService(client)
        self.streaming = StreamingService(
            caller,
            client,
            self._app_config.get("DEFAULT_VIDEO_INDEX", "normal-0"),
            self._app_config.get("DEFAULT_VIDEO_QUALITY", 0),
        )
        self.trajectory = TrajectoryService(
            client,
            self._app_config.get("TRAJECTORY_MQTT_TOPIC", "uav/trajectory"),
            publish_rate=float(self._app_config.get("TRAJECTORY_PUBLISH_RATE", 1.0)),
        )
        self.drc = DrcControlService(
            client,
            caller,
            {
                "host": host,
                "port": port,
                "username": self._active_config.get("MQTT_USERNAME", ""),
                "password": self._active_config.get("MQTT_PASSWORD", ""),
            },
            is_local_slam_mode=False,
            user_id=str(self._active_config.get("DRC_USER_ID", "") or ""),
            user_callsign=str(self._active_config.get("DRC_USER_CALLSIGN", "") or ""),
            osd_frequency=int(self._app_config.get("DRC_OSD_FREQUENCY", 30)),
            hsi_frequency=int(self._app_config.get("DRC_HSI_FREQUENCY", 10)),
            heartbeat_interval=float(self._app_config.get("DRC_HEARTBEAT_INTERVAL", 1.0)),
        )
        self._connected = True

    def disconnect(self) -> None:
        if self.telemetry:
            self.telemetry.stop()
        if self.drc:
            self.drc.shutdown()
        if self.trajectory:
            self.trajectory.stop()
        if self.mqtt_client:
            try:
                self.mqtt_client.disconnect()
            except Exception:
                pass

        self.mqtt_client = None
        self.service_caller = None
        self.telemetry = None
        self.camera = None
        self.control = None
        self.streaming = None
        self.trajectory = None
        self.drc = None
        self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected

    def status(self) -> DroneRuntimeStatus:
        gateway_sn = str(self._active_config.get("GATEWAY_SN", "") or "").strip()
        host = str(self._active_config.get("MQTT_HOST", "") or "").strip()
        try:
            port = int(self._active_config.get("MQTT_PORT", 0))
        except (TypeError, ValueError):
            port = 0

        drc_state = None
        drc_error = None
        if self.drc:
            payload = self.drc.status()
            drc_state = payload.get("state")
            drc_error = payload.get("last_error")

        state = "DISCONNECTED"
        if self._connected:
            state = "CONNECTED"
        if drc_state == "waiting_for_user":
            state = "AUTH_PENDING"
        if drc_state == "drc_ready":
            state = "DRC_READY"

        return DroneRuntimeStatus(
            state=state,
            connected=self._connected,
            gateway_sn=gateway_sn,
            host=host,
            port=port,
            drc_state=drc_state,
            drc_error=drc_error,
        )

    def _validate_required_config(self) -> None:
        gateway_sn = str(self._active_config.get("GATEWAY_SN", "") or "").strip()
        host = str(self._active_config.get("MQTT_HOST", "") or "").strip()
        try:
            port = int(self._active_config.get("MQTT_PORT", 0))
        except (TypeError, ValueError):
            port = 0

        missing: list[str] = []
        if not gateway_sn:
            missing.append("GATEWAY_SN")
        if not host:
            missing.append("MQTT_HOST")
        if port <= 0:
            missing.append("MQTT_PORT")
        if missing:
            raise RuntimeError(f"Missing required drone config: {', '.join(missing)}")
