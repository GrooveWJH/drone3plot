#!/usr/bin/env python3
"""Establish DRC connection, keep heartbeat alive, print battery every second."""
from __future__ import annotations

import sys
import time
from pathlib import Path


def _ensure_local_sdk_on_path() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root))
    sdk_path = repo_root / "thirdparty" / "pydjimqtt" / "src"
    if sdk_path.exists():
        sys.path.insert(0, str(sdk_path))


_ensure_local_sdk_on_path()

from pydjimqtt import setup_drc_connection, stop_heartbeat  # noqa: E402


MQTT_CONFIG = {
    "host": "192.168.10.28",
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
    mqtt = None
    heartbeat = None
    try:
        mqtt, _, heartbeat = setup_drc_connection(
            DRONE_CONFIG["sn"],
            MQTT_CONFIG,
            user_id=DRONE_CONFIG["user_id"],
            user_callsign=DRONE_CONFIG["callsign"],
            osd_frequency=30,
            hsi_frequency=10,
            heartbeat_interval=1.0,
            wait_for_user=True,
            skip_drc_setup=False,
        )

        print("DRC ready. Printing battery once per second (Ctrl+C to stop).")
        while True:
            percent = mqtt.get_battery_percent() if mqtt else None
            if percent is None:
                print("Battery: --")
            else:
                print(f"Battery: {percent}%")
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("Stopping...")
        return 0
    finally:
        if heartbeat:
            stop_heartbeat(heartbeat)
        if mqtt:
            mqtt.disconnect()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
