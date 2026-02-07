"""Local SLAM runtime, independent from DRC connection lifecycle."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Mapping

from pydjimqtt.core import MQTTClient

from .pose import PoseService


@dataclass(frozen=True)
class SlamStatus:
    connected: bool
    host: str
    port: int
    topics: dict[str, str]


class SlamRuntime:
    """Owns pose MQTT client and subscriptions for local SLAM data."""

    GATEWAY_SN = "__pose_slam_local__"

    def __init__(self, app_config: Mapping[str, Any]) -> None:
        self._config = app_config
        self.client: MQTTClient | None = None
        self.pose: PoseService | None = None
        self._connected = False

    def start(self) -> None:
        if self._connected:
            return

        host = str(self._config.get("SLAM_MQTT_HOST", "127.0.0.1") or "127.0.0.1").strip()
        port_raw = self._config.get("SLAM_MQTT_PORT", 1883)
        try:
            port = int(port_raw)
        except (TypeError, ValueError) as exc:
            raise RuntimeError("Invalid SLAM_MQTT_PORT") from exc

        mqtt_config = {
            "host": host,
            "port": port,
            "username": self._config.get("SLAM_MQTT_USERNAME", ""),
            "password": self._config.get("SLAM_MQTT_PASSWORD", ""),
        }

        client = MQTTClient(self.GATEWAY_SN, mqtt_config)
        client.connect()

        pose_topic = str(self._config.get("SLAM_POSE_TOPIC", "") or "").strip()
        yaw_topic = str(self._config.get("SLAM_YAW_TOPIC", "") or "").strip()
        status_topic = str(self._config.get("SLAM_STATUS_TOPIC", "") or "").strip()
        frequency_topic = str(self._config.get("SLAM_FREQUENCY_TOPIC", "") or "").strip()

        logger = logging.getLogger("dashboard")
        logger.info(
            "[slam] runtime start host=%s port=%s topics=%s",
            host,
            port,
            {
                "pose": pose_topic,
                "yaw": yaw_topic,
                "status": status_topic,
                "frequency": frequency_topic,
            },
        )

        self.client = client
        self.pose = PoseService(
            client,
            pose_topic,
            yaw_topic,
            status_topic,
            frequency_topic,
        )
        self._connected = True

    def stop(self) -> None:
        if self.client:
            try:
                self.client.disconnect()
            except Exception:
                pass
        self.client = None
        self.pose = None
        self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected

    def status(self) -> SlamStatus:
        host = str(self._config.get("SLAM_MQTT_HOST", "127.0.0.1") or "127.0.0.1").strip()
        port_raw = self._config.get("SLAM_MQTT_PORT", 1883)
        try:
            port = int(port_raw)
        except (TypeError, ValueError):
            port = 0
        return SlamStatus(
            connected=self._connected,
            host=host,
            port=port,
            topics={
                "pose": str(self._config.get("SLAM_POSE_TOPIC", "") or "").strip(),
                "yaw": str(self._config.get("SLAM_YAW_TOPIC", "") or "").strip(),
                "status": str(self._config.get("SLAM_STATUS_TOPIC", "") or "").strip(),
                "frequency": str(self._config.get("SLAM_FREQUENCY_TOPIC", "") or "").strip(),
            },
        )
