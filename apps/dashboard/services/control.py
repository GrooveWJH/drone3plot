"""Virtual stick command helpers."""
from __future__ import annotations

from pydjimqtt.core.mqtt_client import MQTTClient
from pydjimqtt.services.drc_commands import send_stick_control

from dashboard.domain.models import StickCommand


class ControlService:
    """Map normalized UI commands to DJI stick values."""

    MIN_VALUE = 364
    MAX_VALUE = 1684
    CENTER_VALUE = 1024

    def __init__(self, client: MQTTClient):
        self.client = client

    def send_stick_command(self, command: StickCommand) -> dict:
        roll = self._map_axis(command.roll)
        pitch = self._map_axis(command.pitch)
        yaw = self._map_axis(command.yaw)
        throttle = self._map_axis(command.throttle)
        send_stick_control(self.client, roll=roll, pitch=pitch, yaw=yaw, throttle=throttle)
        return {
            "roll": roll,
            "pitch": pitch,
            "yaw": yaw,
            "throttle": throttle,
        }

    def _map_axis(self, value: float) -> int:
        clamped = max(-1.0, min(1.0, value))
        span = self.MAX_VALUE - self.CENTER_VALUE
        if clamped >= 0:
            return int(self.CENTER_VALUE + clamped * span)
        return int(self.CENTER_VALUE + clamped * (self.CENTER_VALUE - self.MIN_VALUE))
