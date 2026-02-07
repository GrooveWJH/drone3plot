"""RuntimeHub splits immutable SLAM runtime and mutable Drone runtime."""

from __future__ import annotations

import logging
import threading
from typing import Any, Mapping

from .drone_runtime import DroneRuntime
from .slam_runtime import SlamRuntime


class RuntimeHub:
    """Owns SLAM runtime and drone runtime lifecycles separately."""

    def __init__(self, app_config: Mapping[str, Any]):
        self._app_config = app_config
        self._lock = threading.Lock()

        self.slam = SlamRuntime(app_config)
        self.drone_active_config: dict[str, Any] = {
            "GATEWAY_SN": "",
            "MQTT_HOST": "",
            "MQTT_PORT": 0,
            "MQTT_USERNAME": "",
            "MQTT_PASSWORD": "",
            "DRC_USER_ID": "",
            "DRC_USER_CALLSIGN": "",
        }
        self.drone = DroneRuntime(app_config, self.drone_active_config)

    def start_slam(self) -> None:
        if self.slam.connected:
            return
        self.slam.start()

    def stop_all(self) -> None:
        self.drone.disconnect()
        self.slam.stop()

    def get_drone_config(self) -> dict[str, Any]:
        with self._lock:
            return dict(self.drone_active_config)

    def update_drone_config(self, payload: Mapping[str, Any]) -> tuple[bool, str | None]:
        with self._lock:
            if self.drone.connected:
                return False, "Cannot update config while connected."

            mapping = {
                "DJI_GATEWAY_SN": ("GATEWAY_SN", lambda x: str(x).strip()),
                "DJI_MQTT_HOST": ("MQTT_HOST", lambda x: str(x).strip()),
                "DJI_MQTT_PORT": ("MQTT_PORT", int),
                "DJI_MQTT_USERNAME": ("MQTT_USERNAME", str),
                "DJI_MQTT_PASSWORD": ("MQTT_PASSWORD", str),
                "DJI_USER_ID": ("DRC_USER_ID", lambda x: str(x).strip()),
                "DJI_USER_CALLSIGN": ("DRC_USER_CALLSIGN", lambda x: str(x).strip()),
            }
            changed = False
            for req_key, (cfg_key, parser) in mapping.items():
                if req_key not in payload:
                    continue
                try:
                    value = parser(payload[req_key])
                except (TypeError, ValueError):
                    return False, f"Invalid value for {req_key}."
                if self.drone_active_config.get(cfg_key) != value:
                    self.drone_active_config[cfg_key] = value
                    changed = True

            return changed, None

    def connect_drone(self) -> tuple[bool, str | None]:
        try:
            self.drone.connect()
        except Exception as exc:
            logging.getLogger("dashboard").warning("[drone] connect failed: %s", exc)
            return False, str(exc)
        return True, None

    def disconnect_drone(self) -> tuple[bool, str | None]:
        try:
            self.drone.disconnect()
        except Exception as exc:
            return False, str(exc)
        return True, None
