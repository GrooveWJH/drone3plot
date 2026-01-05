#!/usr/bin/env python3
"""Connect to a DJI gateway via pydjimqtt and print the payload_index."""
# Preset CLI commands (for the drone in this file):
# - Start live: python scripts/live_stream_cli.py --sn 9N9CN2B00121JN --user-id pilot_0 --callsign "Pilot 0" --host 192.168.20.186 --port 1883 --username admin --password yundrone123 --url rtmp://192.168.20.186/live/Drone001 --quality 3
# - Set quality: python scripts/live_stream_cli.py --sn 9N9CN2B00121JN --user-id pilot_0 --callsign "Pilot 0" --host 192.168.20.186 --port 1883 --username admin --password yundrone123
#   then choose: 2) Set live quality (provide video_id when prompted)
# - Stop live: python scripts/live_stream_cli.py --sn 9N9CN2B00121JN --user-id pilot_0 --callsign "Pilot 0" --host 192.168.20.186 --port 1883 --username admin --password yundrone123
#   then choose: 3) Stop live push (provide video_id when prompted)
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path


def _ensure_local_sdk_on_path() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    sdk_path = repo_root / "thirdparty" / "pydjimqtt" / "src"
    if sdk_path.exists():
        sys.path.insert(0, str(sdk_path))


_ensure_local_sdk_on_path()

from pydjimqtt import setup_drc_connection, stop_heartbeat, wait_for_camera_data  # noqa: E402


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read payload_index via pydjimqtt.")
    parser.add_argument(
        "--wait",
        type=int,
        default=20,
        help="Max seconds to wait for camera payload index.",
    )
    parser.add_argument(
        "--skip-drc",
        action="store_true",
        help="Only connect MQTT; skip control auth and DRC setup.",
    )
    parser.add_argument(
        "--no-confirm",
        action="store_true",
        help="Do not wait for manual control auth confirmation.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    mqtt = caller = heartbeat = None

    try:
        mqtt, caller, heartbeat = setup_drc_connection(
            gateway_sn=DRONE_CONFIG["sn"],
            mqtt_config=MQTT_CONFIG,
            user_id=DRONE_CONFIG["user_id"],
            user_callsign=DRONE_CONFIG["callsign"],
            wait_for_user=not args.no_confirm,
            skip_drc_setup=args.skip_drc,
        )

        _, payload_index = wait_for_camera_data(mqtt, max_wait=args.wait)
        if payload_index:
            print(f"payload_index={payload_index}")
            return 0

        print("payload_index not available (timeout).")
        return 1
    finally:
        if heartbeat:
            stop_heartbeat(heartbeat)
            time.sleep(0.2)
        if mqtt:
            mqtt.disconnect()


if __name__ == "__main__":
    raise SystemExit(main())
