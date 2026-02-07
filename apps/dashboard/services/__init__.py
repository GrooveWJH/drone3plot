"""Service registry wiring SDK adapters into the Flask app."""

from __future__ import annotations

import logging
from typing import Any, Mapping

from pydjimqtt.core import MQTTClient, ServiceCaller

from .camera import CameraService
from .control import ControlService
from .drc import DrcControlService
from .pose import PoseService
from .trajectory import TrajectoryService
from .streaming import StreamingService
from .telemetry import TelemetryService


class ServiceRegistry:
    """Central place to access initialized services."""

    LOCAL_SLAM_GATEWAY_SN = "__local_slam__"
    POSE_SLAM_GATEWAY_SN = "__pose_slam_local__"

    def __init__(self, app_config: Mapping[str, Any]):
        self.config = app_config
        self.mqtt_client: MQTTClient | None = None
        self.service_caller: ServiceCaller | None = None
        self.telemetry: TelemetryService | None = None
        self.camera: CameraService | None = None
        self.control: ControlService | None = None
        self.streaming: StreamingService | None = None
        self.drc: DrcControlService | None = None
        self.pose: PoseService | None = None
        self.pose_client: MQTTClient | None = None
        self.trajectory: TrajectoryService | None = None
        self._bootstrapped = False
        self._started = False
        self._connected = False

    def bootstrap(self) -> None:
        if self._bootstrapped:
            return
        logger = logging.getLogger("dashboard")
        self._init_clients()
        if not self.mqtt_client:
            raise RuntimeError("MQTT client failed to initialize")
        gateway_sn = self._resolve_gateway_sn()
        poll_hz = float(self.config.get("TELEMETRY_POLL_HZ", 2))
        self.telemetry = TelemetryService(self.mqtt_client, poll_hz=poll_hz)
        self.camera = CameraService(
            self.mqtt_client, tuple(self.config.get("AVAILABLE_LENSES", ("zoom",)))
        )
        self.control = ControlService(self.mqtt_client)
        if isinstance(self.service_caller, ServiceCaller) and isinstance(
            self.mqtt_client, MQTTClient
        ):
            self.streaming = StreamingService(
                self.service_caller,
                self.mqtt_client,
                self.config.get("DEFAULT_VIDEO_INDEX", "normal-0"),
                self.config.get("DEFAULT_VIDEO_QUALITY", 0),
            )
            pose_config = {
                "host": self.config.get("SLAM_MQTT_HOST", "127.0.0.1"),
                "port": int(self.config.get("SLAM_MQTT_PORT", 1883)),
                "username": self.config.get("SLAM_MQTT_USERNAME", ""),
                "password": self.config.get("SLAM_MQTT_PASSWORD", ""),
            }
            self.pose_client = MQTTClient(self.POSE_SLAM_GATEWAY_SN, pose_config)
            self.pose_client.connect()
            self.pose = PoseService(
                self.pose_client,
                self.config.get("SLAM_POSE_TOPIC"),
                self.config.get("SLAM_YAW_TOPIC"),
                self.config.get("SLAM_STATUS_TOPIC"),
                self.config.get("SLAM_FREQUENCY_TOPIC"),
            )
            logger.info(
                "[slam] pose_topic=%r yaw_topic=%r status_topic=%r freq_topic=%r",
                self.config.get("SLAM_POSE_TOPIC"),
                self.config.get("SLAM_YAW_TOPIC"),
                self.config.get("SLAM_STATUS_TOPIC"),
                self.config.get("SLAM_FREQUENCY_TOPIC"),
            )
            self.trajectory = TrajectoryService(
                self.mqtt_client,
                self.config.get("TRAJECTORY_MQTT_TOPIC", "uav/trajectory"),
                publish_rate=float(self.config.get("TRAJECTORY_PUBLISH_RATE", 1.0)),
            )
            self.drc = DrcControlService(
                self.mqtt_client,
                self.service_caller,
                {
                    "host": self.config.get("MQTT_HOST"),
                    "port": self.config.get("MQTT_PORT"),
                    "username": self.config.get("MQTT_USERNAME"),
                    "password": self.config.get("MQTT_PASSWORD"),
                },
                is_local_slam_mode=(gateway_sn == self.LOCAL_SLAM_GATEWAY_SN),
                user_id=str(self.config.get("DRC_USER_ID", "") or ""),
                user_callsign=str(self.config.get("DRC_USER_CALLSIGN", "") or ""),
                osd_frequency=self.config.get("DRC_OSD_FREQUENCY", 30),
                hsi_frequency=self.config.get("DRC_HSI_FREQUENCY", 10),
                heartbeat_interval=self.config.get("DRC_HEARTBEAT_INTERVAL", 1.0),
            )
        self._bootstrapped = True

    def start_background_services(self) -> None:
        if not self.telemetry:
            raise RuntimeError("Telemetry service not initialized")
        if self._started:
            return
        self.telemetry.start()
        self._started = True

    def connect(self) -> None:
        if self._connected:
            return
        self.bootstrap()
        self.start_background_services()
        self._connected = True

    def disconnect(self) -> None:
        self.shutdown()
        self._connected = False

    def shutdown(self) -> None:
        if self.telemetry:
            self.telemetry.stop()
        if self.drc:
            self.drc.shutdown()
        if self.trajectory:
            self.trajectory.stop()
        if self.pose_client:
            try:
                self.pose_client.disconnect()
            except Exception:
                pass
        if self.mqtt_client and hasattr(self.mqtt_client, "disconnect"):
            try:
                self.mqtt_client.disconnect()
            except Exception:
                pass
        self._connected = False

    def reconfigure(self, app_config: Mapping[str, Any]) -> None:
        """Reinitialize services with a new config mapping."""
        self.shutdown()
        self.config = app_config
        self.mqtt_client = None
        self.service_caller = None
        self.telemetry = None
        self.camera = None
        self.control = None
        self.streaming = None
        self.drc = None
        self.pose = None
        self.pose_client = None
        self.trajectory = None
        self._bootstrapped = False
        self._started = False
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    # Internal helpers -------------------------------------------------

    def _init_clients(self) -> None:
        self._validate_required_connection_config()
        gateway_sn = self._resolve_gateway_sn()
        mqtt_config = {
            "host": self.config.get("MQTT_HOST"),
            "port": self.config.get("MQTT_PORT"),
            "username": self.config.get("MQTT_USERNAME"),
            "password": self.config.get("MQTT_PASSWORD"),
        }
        client = MQTTClient(gateway_sn, mqtt_config)
        client.connect()
        self.mqtt_client = client
        self.service_caller = ServiceCaller(client)

    def _validate_required_connection_config(self) -> None:
        mqtt_host = str(self.config.get("MQTT_HOST", "")).strip()
        mqtt_port_raw = self.config.get("MQTT_PORT", 0)
        try:
            mqtt_port = int(mqtt_port_raw)
        except (TypeError, ValueError):
            mqtt_port = 0

        missing = []
        if not mqtt_host:
            missing.append("MQTT_HOST")
        if mqtt_port <= 0:
            missing.append("MQTT_PORT")
        if missing:
            joined = ", ".join(missing)
            raise RuntimeError(f"Missing required MQTT config: {joined}")

    def _resolve_gateway_sn(self) -> str:
        gateway_sn = str(self.config.get("GATEWAY_SN", "")).strip()
        if gateway_sn:
            return gateway_sn
        return self.LOCAL_SLAM_GATEWAY_SN
