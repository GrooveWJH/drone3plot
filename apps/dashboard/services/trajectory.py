"""Trajectory ingest + MQTT relay service."""

from __future__ import annotations

import json
import threading
import time
from typing import Any, Dict, Optional

from pydjimqtt.core.mqtt_client import MQTTClient


class TrajectoryService:
    """Keeps latest trajectory received from MQTT and relays HTTP payloads to MQTT."""

    def __init__(
        self, client: MQTTClient, topic: str, publish_rate: float = 1.0
    ) -> None:
        self.client = client
        self.topic = (topic or "uav/trajectory").strip()
        self.publish_interval = 1.0 / max(publish_rate, 0.1)
        self._lock = threading.Lock()
        self._http_payload: Optional[Dict[str, Any]] = None
        self._last_mqtt_payload: Optional[Dict[str, Any]] = None
        self._last_mqtt_at: Optional[float] = None
        self._original_on_message = None
        self._stop_event = threading.Event()
        self._publisher_thread: Optional[threading.Thread] = None

        if self.topic:
            self._attach_listener()
            self._start_publisher()

    def _attach_listener(self) -> None:
        mqtt_client = self.client.client
        if not mqtt_client:
            return

        self._original_on_message = mqtt_client.on_message

        def _wrapped(client, userdata, msg):
            if msg.topic == self.topic:
                self._handle_payload(msg.payload)
            if self._original_on_message:
                self._original_on_message(client, userdata, msg)

        mqtt_client.on_message = _wrapped
        mqtt_client.subscribe(self.topic, qos=0)

    def _handle_payload(self, raw_payload: bytes) -> None:
        try:
            payload = json.loads(raw_payload.decode())
        except Exception:
            return
        with self._lock:
            self._last_mqtt_payload = payload
            self._last_mqtt_at = time.time()

    def _start_publisher(self) -> None:
        if self._publisher_thread and self._publisher_thread.is_alive():
            return

        self._stop_event.clear()
        self._publisher_thread = threading.Thread(
            target=self._publisher_loop, name="trajectory-publisher", daemon=True
        )
        self._publisher_thread.start()

    def _publisher_loop(self) -> None:
        while not self._stop_event.is_set():
            payload = None
            with self._lock:
                if self._http_payload:
                    payload = dict(self._http_payload)
            if payload:
                self.publish(payload)
            time.sleep(self.publish_interval)

    def set_http_payload(self, payload: Dict[str, Any]) -> None:
        with self._lock:
            self._http_payload = payload
        self.publish(payload)

    def publish(self, payload: Dict[str, Any]) -> None:
        if not self.client.client:
            return
        try:
            self.client.client.publish(
                self.topic,
                json.dumps(payload, ensure_ascii=False),
                qos=0,
                retain=True,
            )
        except Exception:
            return

    def latest(self) -> tuple[Optional[Dict[str, Any]], Optional[float]]:
        with self._lock:
            return self._last_mqtt_payload, self._last_mqtt_at

    def stop(self) -> None:
        self._stop_event.set()
        if self._publisher_thread:
            self._publisher_thread.join(timeout=2)
