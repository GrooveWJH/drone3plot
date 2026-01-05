#!/usr/bin/env python3
"""Interactive live stream CLI using pydjimqtt."""
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
from pydjimqtt.live_utils import start_live, stop_live, set_live_quality  # noqa: E402


DEFAULT_MQTT_CONFIG = {
    "host": "192.168.20.186",
    "port": 1883,
    "username": "admin",
    "password": "yundrone123",
}

DEFAULT_DRONE_CONFIG = {
    "sn": "9N9CN2B00121JN",
    "user_id": "pilot_0",
    "callsign": "Pilot 0",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Interactive live stream CLI.")
    parser.add_argument("--wait", type=int, default=20, help="Seconds to wait for camera data.")
    parser.add_argument("--skip-drc", action="store_true", help="Only connect MQTT; skip DRC setup.")
    parser.add_argument("--no-confirm", action="store_true", help="Do not wait for manual auth.")
    return parser.parse_args()


def _prompt(text: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{text}{suffix}: ").strip()
    return value or (default or "")


def _prompt_quality(default: int) -> int:
    while True:
        raw = _prompt("Quality 0-4 (0=auto,1=fluent,2=sd,3=hd,4=full)", str(default))
        try:
            value = int(raw)
        except ValueError:
            print("Invalid number.")
            continue
        if 0 <= value <= 4:
            return value
        print("Quality must be 0-4.")


def _show_menu() -> None:
    print("\n=== Live Stream CLI ===")
    print("1) Start live push")
    print("2) Set live quality")
    print("3) Stop live push")
    print("4) Show status")
    print("5) Exit")


def main() -> int:
    args = parse_args()
    mqtt = caller = heartbeat = None
    video_id = ""
    rtmp_url = "rtmp://192.168.20.186/live/Drone001"
    video_index = "normal-0"
    quality = 0
    mqtt_config = DEFAULT_MQTT_CONFIG

    try:
        mqtt, caller, heartbeat = setup_drc_connection(
            gateway_sn=DEFAULT_DRONE_CONFIG["sn"],
            mqtt_config=mqtt_config,
            user_id=DEFAULT_DRONE_CONFIG["user_id"],
            user_callsign=DEFAULT_DRONE_CONFIG["callsign"],
            wait_for_user=not args.no_confirm,
            skip_drc_setup=args.skip_drc,
        )

        _, payload_index = wait_for_camera_data(mqtt, max_wait=args.wait)
        if not payload_index:
            print("Warning: payload_index not ready yet. Live start may fail.")

        while True:
            _show_menu()
            choice = _prompt("Choose")
            if choice == "1":
                if not rtmp_url:
                    rtmp_url = _prompt("RTMP URL")
                quality = _prompt_quality(quality)
                video_id = start_live(caller, mqtt, rtmp_url, video_index=video_index, video_quality=quality) or ""
            elif choice == "2":
                if not video_id:
                    video_id = _prompt("Video ID (sn/payload/video_index)")
                quality = _prompt_quality(quality)
                ok = set_live_quality(caller, video_id, quality)
                if not ok:
                    print("Set quality failed.")
            elif choice == "3":
                if not video_id:
                    video_id = _prompt("Video ID (sn/payload/video_index)")
                ok = stop_live(caller, video_id)
                if ok:
                    video_id = ""
            elif choice == "4":
                print(f"payload_index={mqtt.get_payload_index()}")
                print(f"video_id={video_id or '(none)'}")
                print(f"url={rtmp_url or '(none)'}")
                print(f"video_index={video_index}")
                print(f"quality={quality}")
            elif choice == "5" or choice.lower() in {"q", "quit", "exit"}:
                break
            else:
                print("Unknown option.")

    finally:
        if heartbeat:
            stop_heartbeat(heartbeat)
            time.sleep(0.2)
        if mqtt:
            mqtt.disconnect()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
