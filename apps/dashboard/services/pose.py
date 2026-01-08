"""Pose data listener for slam/position MQTT messages."""
from __future__ import annotations

import json
import time
import threading
from typing import Any, Dict, Optional

from pydjimqtt.core.mqtt_client import MQTTClient


class PoseService:
    """Subscribe to pose/yaw topics and keep the latest payload."""
    STALE_AFTER_SEC = 5.0

    def __init__(
        self,
        client: MQTTClient,
        pose_topic: str | None,
        yaw_topic: str | None,
        status_topic: str | None,
        frequency_topic: str | None,
    ) -> None:
        self.client = client
        self.pose_topic = (pose_topic or "").strip()
        self.yaw_topic = (yaw_topic or "").strip()
        self.status_topic = (status_topic or "").strip()
        self.frequency_topic = (frequency_topic or "").strip()
        self._lock = threading.Lock()
        self._pose: Dict[str, Optional[float]] = {
            "x": None,
            "y": None,
            "z": None,
            "yaw": None,
        }
        self._frequency: Dict[str, Optional[float]] = {
            "rostopic": None,
            "mqtt": None,
            "timestamp": None,
        }
        self._status: Optional[str] = None
        self._last_pose_at = 0.0
        self._last_yaw_at = 0.0
        self._original_on_message = None
        if self.pose_topic or self.yaw_topic or self.status_topic or self.frequency_topic:
            self._attach_listener()

    def _attach_listener(self) -> None:
        if not self.client.client:
            return
        self._original_on_message = self.client.client.on_message

        def on_message(client, userdata, msg):
            if self.pose_topic and msg.topic == self.pose_topic:
                self._handle_pose(msg.payload)
            if self.yaw_topic and msg.topic == self.yaw_topic:
                self._handle_yaw(msg.payload)
            if self.status_topic and msg.topic == self.status_topic:
                self._handle_status(msg.payload)
            if self.frequency_topic and msg.topic == self.frequency_topic:
                self._handle_frequency(msg.payload)
            if self._original_on_message:
                self._original_on_message(client, userdata, msg)

        self.client.client.on_message = on_message
        if self.pose_topic:
            self.client.client.subscribe(self.pose_topic, qos=0)
        if self.yaw_topic:
            self.client.client.subscribe(self.yaw_topic, qos=0)
        if self.status_topic:
            self.client.client.subscribe(self.status_topic, qos=0)
        if self.frequency_topic:
            self.client.client.subscribe(self.frequency_topic, qos=0)

    def _handle_pose(self, raw_payload: bytes) -> None:
        try:
            payload = json.loads(raw_payload.decode())
        except Exception:
            return
        data: Dict[str, Any] = payload.get("data", payload)
        x = data.get("x")
        y = data.get("y")
        z = data.get("z")
        with self._lock:
            self._pose["x"] = _to_float(x)
            self._pose["y"] = _to_float(y)
            self._pose["z"] = _to_float(z)
            self._last_pose_at = time.monotonic()

    def _handle_yaw(self, raw_payload: bytes) -> None:
        try:
            payload = json.loads(raw_payload.decode())
        except Exception:
            return
        data: Dict[str, Any] = payload.get("data", payload)
        yaw = data.get("yaw")
        with self._lock:
            self._pose["yaw"] = _to_float(yaw)
            self._last_yaw_at = time.monotonic()

    def _handle_status(self, raw_payload: bytes) -> None:
        try:
            payload = json.loads(raw_payload.decode())
        except Exception:
            return
        data: Dict[str, Any] = payload.get("data", payload)
        status = data.get("status")
        if status is None:
            return
        with self._lock:
            self._status = str(status)

    def _handle_frequency(self, raw_payload: bytes) -> None:
        try:
            payload = json.loads(raw_payload.decode())
        except Exception:
            return
        data: Dict[str, Any] = payload.get("data", payload)
        mqtt_rate = _to_float(data.get("mqtt"))
        rostopic_rate = _to_float(data.get("rostopic"))
        timestamp = _to_float(data.get("timestamp"))
        with self._lock:
            self._frequency["mqtt"] = mqtt_rate
            self._frequency["rostopic"] = rostopic_rate
            self._frequency["timestamp"] = timestamp

    def latest(self) -> Dict[str, Optional[float] | Optional[str]]:
        with self._lock:
            payload = dict(self._pose)
            last_update = max(self._last_pose_at, self._last_yaw_at)
            is_stale = (last_update == 0.0) or (
                time.monotonic() - last_update > self.STALE_AFTER_SEC
            )
            if is_stale:
                payload["x"] = None
                payload["y"] = None
                payload["z"] = None
                payload["yaw"] = None
                payload["status"] = "stale"
            else:
                payload["status"] = self._status
            payload["frequency"] = dict(self._frequency)
            return payload


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
