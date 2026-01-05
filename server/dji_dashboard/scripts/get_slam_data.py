#!/usr/bin/env python3
"""Connect to MQTT and print slam/position + slam/yaw in real time."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Optional


def _ensure_local_sdk_on_path() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root))
    sdk_path = repo_root / "thirdparty" / "pydjimqtt" / "src"
    if sdk_path.exists():
        sys.path.insert(0, str(sdk_path))


_ensure_local_sdk_on_path()

from pydjimqtt import MQTTClient  # noqa: E402


MQTT_CONFIG = {
    "host": "192.168.20.186",
    "port": 1883,
    "username": "admin",
    "password": "yundrone123",
}

DRONE_CONFIG = {
    "sn": "9N9CN2B00121JN",
}

SLAM_POSE_TOPIC = "slam/position"
SLAM_YAW_TOPIC = "slam/yaw"
SLAM_STATUS_TOPIC = "slam/status"


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def main() -> int:
    mqtt = MQTTClient(DRONE_CONFIG["sn"], MQTT_CONFIG)
    mqtt.connect()

    last_pose = {"x": None, "y": None, "z": None, "timestamp": None}
    last_yaw = {"yaw": None, "timestamp": None}
    last_status = {"status": None, "timestamp": None}
    last_pose_seen = None
    last_yaw_seen = None
    last_status_seen = None

    original_on_message = mqtt.client.on_message if mqtt.client else None

    def on_message(client, userdata, msg):
        nonlocal last_pose_seen, last_yaw_seen, last_status_seen
        if msg.topic in (SLAM_POSE_TOPIC, SLAM_YAW_TOPIC, SLAM_STATUS_TOPIC):
            try:
                payload = json.loads(msg.payload.decode())
            except Exception:
                payload = {}
            data = payload.get("data", payload)
            now = time.monotonic()
            if msg.topic == SLAM_POSE_TOPIC:
                last_pose_seen = now
                last_pose["timestamp"] = data.get("timestamp")
                last_pose["x"] = _to_float(data.get("x"))
                last_pose["y"] = _to_float(data.get("y"))
                last_pose["z"] = _to_float(data.get("z"))
            elif msg.topic == SLAM_YAW_TOPIC:
                last_yaw_seen = now
                last_yaw["timestamp"] = data.get("timestamp")
                last_yaw["yaw"] = _to_float(data.get("yaw"))
            else:
                last_status_seen = now
                last_status["timestamp"] = data.get("timestamp")
                status = data.get("status")
                last_status["status"] = None if status is None else str(status)
        if original_on_message:
            original_on_message(client, userdata, msg)

    if mqtt.client:
        mqtt.client.on_message = on_message
        mqtt.client.subscribe(SLAM_POSE_TOPIC, qos=0)
        mqtt.client.subscribe(SLAM_YAW_TOPIC, qos=0)
        mqtt.client.subscribe(SLAM_STATUS_TOPIC, qos=0)

    try:
        print("Streaming slam/position + slam/yaw + slam/status (Ctrl+C to stop)")
        while True:
            now = time.monotonic()
            pose_age = None if last_pose_seen is None else now - last_pose_seen
            yaw_age = None if last_yaw_seen is None else now - last_yaw_seen
            status_age = None if last_status_seen is None else now - last_status_seen

            pose_ready = all(last_pose[k] is not None for k in ("x", "y", "z"))
            yaw_ready = last_yaw["yaw"] is not None

            if last_pose_seen is None and last_yaw_seen is None and last_status_seen is None:
                print("No SLAM data yet. Waiting for slam/position + slam/yaw + slam/status ...")
            else:
                if last_pose_seen is None:
                    print("No slam/position data yet.")
                elif not pose_ready:
                    print(f"slam/position received but empty (age={pose_age:.2f}s)")
                else:
                    x = last_pose["x"]
                    y = last_pose["y"]
                    z = last_pose["z"]
                    print(
                        "slam/position OK: "
                        f"x={x:,.3f} y={y:,.3f} z={z:,.3f} "
                        f"(age={pose_age:.2f}s)"
                    )

                if last_yaw_seen is None:
                    print("No slam/yaw data yet.")
                elif not yaw_ready:
                    print(f"slam/yaw received but empty (age={yaw_age:.2f}s)")
                else:
                    print(f"slam/yaw OK: yaw={last_yaw['yaw']:.2f}° (age={yaw_age:.2f}s)")

                if last_status_seen is None:
                    print("No slam/status data yet.")
                elif last_status["status"] is None:
                    print(f"slam/status received but empty (age={status_age:.2f}s)")
                else:
                    print(f"slam/status OK: status={last_status['status']} (age={status_age:.2f}s)")

            time.sleep(0.5)
    except KeyboardInterrupt:
        print("Stopping...")
    finally:
        mqtt.disconnect()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
