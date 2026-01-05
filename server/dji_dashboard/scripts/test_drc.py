#!/usr/bin/env python3
"""Test DRC flow: request control, enter DRC, print battery percent."""
from __future__ import annotations

import sys
import time
from pathlib import Path


def _ensure_local_sdk_on_path() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    sdk_path = repo_root / "thirdparty" / "pydjimqtt" / "src"
    if sdk_path.exists():
        sys.path.insert(0, str(sdk_path))


_ensure_local_sdk_on_path()

from pydjimqtt import (  # noqa: E402
    MQTTClient,
    ServiceCaller,
    enter_drc_mode,
    request_control_auth,
    start_heartbeat,
    stop_heartbeat,
)


MQTT_CONFIG = {
    "host": "192.168.20.186",
    "port": 1883,
    "username": "admin",
    "password": "yundrone123",
}

DRONE_CONFIG = {
    "sn": "9N9CN2B00121JN",
    "user_id": "pilot_0",
    "callsign": "Pilot 0",
}


def wait_for_battery(mqtt: MQTTClient, timeout: int = 15) -> int | None:
    """Wait for battery percent to show up in OSD."""
    end_time = time.time() + timeout
    while time.time() < end_time:
        percent = mqtt.get_battery_percent()
        if percent is not None:
            return percent
        time.sleep(0.5)
    return None


def main() -> int:
    mqtt = MQTTClient(DRONE_CONFIG["sn"], MQTT_CONFIG)
    mqtt.connect()
    caller = ServiceCaller(mqtt)
    heartbeat = None

    try:
        print("[1/3] Request control auth...")
        request_control_auth(
            caller,
            user_id=DRONE_CONFIG["user_id"],
            user_callsign=DRONE_CONFIG["callsign"],
        )
        input("Please allow control on the RC, then press Enter to continue...")

        print("[2/3] Enter DRC mode...")
        mqtt_broker_config = {
            "address": f"{MQTT_CONFIG['host']}:{MQTT_CONFIG['port']}",
            "client_id": f"drc-{DRONE_CONFIG['sn']}",
            "username": MQTT_CONFIG["username"],
            "password": MQTT_CONFIG["password"],
            "expire_time": int(time.time()) + 3600,
            "enable_tls": MQTT_CONFIG.get("enable_tls", False),
        }
        enter_drc_mode(caller, mqtt_broker=mqtt_broker_config, osd_frequency=30, hsi_frequency=10)
        heartbeat = start_heartbeat(mqtt, interval=1.0)

        print("[3/3] Waiting for battery data...")
        percent = wait_for_battery(mqtt, timeout=20)
        if percent is None:
            print("Battery percent not available (timeout).")
            return 1
        print(f"Battery: {percent}%")
        return 0
    finally:
        if heartbeat:
            stop_heartbeat(heartbeat)
        mqtt.disconnect()


if __name__ == "__main__":
    raise SystemExit(main())
