"""DRC control flow helpers for web-driven confirmation."""
from __future__ import annotations

import threading
import time
import uuid
from typing import Any, Dict, Optional

from pydjimqtt.core.mqtt_client import MQTTClient
from pydjimqtt.core.service_caller import ServiceCaller
from pydjimqtt.services.commands import enter_drc_mode, request_control_auth
from pydjimqtt.services.heartbeat import start_heartbeat, stop_heartbeat


class DrcControlService:
    """Split DRC flow into request + confirm steps for UI-driven control."""

    STATE_IDLE = "idle"
    STATE_DISCONNECTED = "disconnected"
    STATE_WAITING = "waiting_for_user"
    STATE_READY = "drc_ready"
    STATE_ERROR = "error"

    def __init__(
        self,
        client: MQTTClient,
        caller: ServiceCaller,
        mqtt_config: Dict[str, Any],
        *,
        user_id: str,
        user_callsign: str,
        osd_frequency: int = 30,
        hsi_frequency: int = 10,
        heartbeat_interval: float = 1.0,
    ) -> None:
        self.client = client
        self.caller = caller
        self.mqtt_config = mqtt_config
        self.default_user_id = user_id
        self.default_callsign = user_callsign
        self.osd_frequency = osd_frequency
        self.hsi_frequency = hsi_frequency
        self.heartbeat_interval = heartbeat_interval
        self._state = self.STATE_IDLE
        self._last_error: Optional[str] = None
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    def status(self) -> Dict[str, Optional[str]]:
        with self._lock:
            is_online = True
            if hasattr(self.client, "is_online"):
                try:
                    is_online = self.client.is_online(timeout=3.0)
                except Exception:
                    is_online = True
            if not is_online and self._state != self.STATE_WAITING:
                print("DrcControlService.status(): MQTT client offline, resetting state.")
                self._state = self.STATE_DISCONNECTED
                self._last_error = None
                if self._heartbeat_thread:
                    stop_heartbeat(self._heartbeat_thread)
                    self._heartbeat_thread = None
            return {"state": self._state, "last_error": self._last_error}

    def request_control(self, user_id: Optional[str] = None, user_callsign: Optional[str] = None) -> Dict[str, Optional[str]]:
        with self._lock:
            if self._state in {self.STATE_WAITING, self.STATE_READY}:
                return {"state": self._state, "last_error": self._last_error}
            self._last_error = None

        resolved_user_id = user_id or self.default_user_id
        resolved_callsign = user_callsign or self.default_callsign
        print(
            "[drc] cloud_control_auth_request params: "
            f"user_id={resolved_user_id}, user_callsign={resolved_callsign}, "
            f"gateway_sn={self.client.gateway_sn}, mqtt={self.mqtt_config.get('host')}:{self.mqtt_config.get('port')}"
        )

        try:
            request_control_auth(
                self.caller,
                user_id=resolved_user_id,
                user_callsign=resolved_callsign,
            )
        except Exception as exc:
            with self._lock:
                self._state = self.STATE_ERROR
                self._last_error = str(exc)
                return {"state": self._state, "last_error": self._last_error}

        with self._lock:
            self._state = self.STATE_WAITING
            return {"state": self._state, "last_error": None}

    def confirm_control(self) -> Dict[str, Optional[str]]:
        with self._lock:
            if self._state != self.STATE_WAITING:
                raise RuntimeError("Control auth not requested yet.")
            self._last_error = None

        try:
            random_suffix = str(uuid.uuid4())[:3]
            mqtt_broker_config = {
                "address": f"{self.mqtt_config['host']}:{self.mqtt_config['port']}",
                "client_id": f"drc-{self.client.gateway_sn}-{random_suffix}",
                "username": self.mqtt_config["username"],
                "password": self.mqtt_config["password"],
                "expire_time": int(time.time()) + 3600,
                "enable_tls": self.mqtt_config.get("enable_tls", False),
            }
            enter_drc_mode(
                self.caller,
                mqtt_broker=mqtt_broker_config,
                osd_frequency=self.osd_frequency,
                hsi_frequency=self.hsi_frequency,
            )
            if self._heartbeat_thread:
                stop_heartbeat(self._heartbeat_thread)
            self._heartbeat_thread = start_heartbeat(self.client, interval=self.heartbeat_interval)
        except Exception as exc:
            with self._lock:
                self._state = self.STATE_ERROR
                self._last_error = str(exc)
                return {"state": self._state, "last_error": self._last_error}

        with self._lock:
            self._state = self.STATE_READY
            return {"state": self._state, "last_error": None}

    def shutdown(self) -> None:
        if self._heartbeat_thread:
            stop_heartbeat(self._heartbeat_thread)
            self._heartbeat_thread = None
