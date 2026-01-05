#!/usr/bin/env python3
"""Connect to DRC and print local height (down_distance) continuously."""
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

        print("[3/3] Relative height stream. Press Ctrl+C to stop.")
        while True:
            height = mqtt.get_relative_height()
            if height is None:
                print("relative_height=--")
            else:
                print(f"relative_height={height} m")
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("Stopping...")
    finally:
        if heartbeat:
            stop_heartbeat(heartbeat)
        mqtt.disconnect()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
