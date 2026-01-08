"""Camera control helpers."""
from __future__ import annotations

from pydjimqtt.core.mqtt_client import MQTTClient
from pydjimqtt.services.drc_commands import camera_look_at, set_camera_zoom, take_photo_wait


class CameraService:
    """Encapsulates camera control commands."""

    def __init__(self, client: MQTTClient, available_lenses: tuple[str, ...]):
        self.client = client
        self.available_lenses = available_lenses
        self._current_lens = available_lenses[0] if available_lenses else "zoom"

    def set_zoom(self, zoom_factor: float, camera_type: str | None = None) -> None:
        payload_index = self.client.get_payload_index()
        if not payload_index:
            raise RuntimeError("Camera payload index is unknown. Wait for telemetry before sending commands.")
        resolved_type = camera_type or self._current_lens
        set_camera_zoom(self.client, payload_index=payload_index, zoom_factor=zoom_factor, camera_type=resolved_type)
        self._current_lens = resolved_type

    def select_lens(self, camera_type: str) -> str:
        if camera_type not in self.available_lenses:
            raise ValueError(f"Unsupported lens '{camera_type}'. Available: {self.available_lenses}")
        self._current_lens = camera_type
        return self._current_lens

    def look_at(self, latitude: float, longitude: float, height: float, locked: bool = False) -> None:
        payload_index = self.client.get_payload_index()
        if not payload_index:
            raise RuntimeError("Camera payload index is unknown. Wait for telemetry before sending commands.")
        camera_look_at(
            self.client,
            payload_index=payload_index,
            latitude=latitude,
            longitude=longitude,
            height=height,
            locked=locked,
        )

    def take_photo(self, timeout: float = 10.0) -> dict:
        payload_index = self.client.get_payload_index()
        if not payload_index:
            raise RuntimeError("Camera payload index is unknown. Wait for telemetry before sending commands.")
        return take_photo_wait(self.client, payload_index=payload_index, timeout=timeout)

    def current_lens(self) -> str:
        return self._current_lens
