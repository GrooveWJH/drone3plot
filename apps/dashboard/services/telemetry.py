"""Telemetry aggregation service."""
from __future__ import annotations

import threading
import time
from typing import Callable, List

from pydjimqtt.core.mqtt_client import MQTTClient

from dashboard.domain.models import (
    CameraState,
    ConnectionState,
    FlightState,
    GimbalState,
    Position,
    Speed,
    TelemetrySnapshot,
)

TelemetryCallback = Callable[[TelemetrySnapshot], None]


class TelemetryService:
    """Continuously pull telemetry from the SDK client and expose snapshots."""

    def __init__(
        self,
        client: MQTTClient,
        poll_hz: float = 2.0,
    ) -> None:
        self.client = client
        self.poll_hz = max(poll_hz, 0.1)
        self.poll_interval = 1.0 / self.poll_hz
        self._snapshot = TelemetrySnapshot()
        self._lock = threading.Lock()
        self._callbacks: List[TelemetryCallback] = []
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="telemetry-loop", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)

    def subscribe(self, callback: TelemetryCallback) -> None:
        self._callbacks.append(callback)

    def latest(self) -> TelemetrySnapshot:
        with self._lock:
            return self._snapshot

    def latest_dict(self) -> dict:
        return self.latest().model_dump()

    def _run(self) -> None:
        while not self._stop_event.is_set():
            snapshot = self._collect_snapshot()
            with self._lock:
                self._snapshot = snapshot
            for callback in list(self._callbacks):
                try:
                    callback(snapshot)
                except Exception:
                    # Avoid crashing the loop because of subscriber errors.
                    continue
            time.sleep(self.poll_interval)

    def _collect_snapshot(self) -> TelemetrySnapshot:
        lat = self.client.get_latitude()
        lon = self.client.get_longitude()
        height = self.client.get_height()
        relative_height = self.client.get_relative_height() if hasattr(self.client, "get_relative_height") else None
        speed_tuple = self.client.get_speed() or (None, None, None, None)
        battery = self.client.get_battery_percent()
        osd_freq = self.client.get_osd_frequency()
        is_online = self.client.is_online() if hasattr(self.client, "is_online") else True
        camera_osd = self.client.get_camera_osd_data() or {}
        flight_mode_code = self.client.get_flight_mode() if hasattr(self.client, "get_flight_mode") else None
        flight_mode_label = (
            self.client.get_flight_mode_name() if hasattr(self.client, "get_flight_mode_name") else "未知"
        )

        camera_state = CameraState(
            payload_index=camera_osd.get("payload_index"),
            gimbal=GimbalState(
                pitch=camera_osd.get("gimbal_pitch"),
                roll=camera_osd.get("gimbal_roll"),
                yaw=camera_osd.get("gimbal_yaw"),
            ),
        )

        snapshot = TelemetrySnapshot(
            position=Position(
                latitude=lat,
                longitude=lon,
                altitude=height,
                relative_altitude=relative_height,
            ),
            speed=Speed(
                horizontal=speed_tuple[0],
                x=speed_tuple[1],
                y=speed_tuple[2],
                z=speed_tuple[3],
            ),
        )
        snapshot.battery.percent = battery
        snapshot.flight = FlightState(mode_code=flight_mode_code, mode_label=flight_mode_label)
        snapshot.camera = camera_state
        snapshot.connection = ConnectionState(osd_frequency=osd_freq, is_online=is_online)
        return snapshot
