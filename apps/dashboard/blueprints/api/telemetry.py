"""Telemetry API endpoints."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify

bp = Blueprint("telemetry_api", __name__)


@bp.get("/telemetry")
def telemetry_snapshot():
    hub = current_app.extensions["runtime_hub"]
    if not hub.drone.connected or not hub.drone.telemetry:
        return jsonify({"error": "Telemetry is not available before drone connect."}), 503
    return jsonify(hub.drone.telemetry.latest_dict())


@bp.get("/pose")
def pose_snapshot():
    hub = current_app.extensions["runtime_hub"]
    if not hub.slam.connected or not hub.slam.pose:
        return jsonify({"x": None, "y": None, "z": None, "yaw": None})
    return jsonify(hub.slam.pose.latest())


@bp.get("/ui/pose-strip")
def ui_pose_strip():
    """Single payload for pose strip to avoid multi-request jitter."""
    hub = current_app.extensions["runtime_hub"]
    pose_payload = {"x": None, "y": None, "z": None, "yaw": None}
    if hub.slam.connected and hub.slam.pose:
        pose_payload = hub.slam.pose.latest()

    relative_altitude = None
    flight_mode = None
    if hub.drone.connected and hub.drone.telemetry:
        telemetry = hub.drone.telemetry.latest_dict()
        relative_altitude = (
            telemetry.get("position", {}).get("relative_altitude")
            if isinstance(telemetry, dict)
            else None
        )
        flight = telemetry.get("flight", {}) if isinstance(telemetry, dict) else {}
        flight_mode = flight.get("mode_label") or flight.get("mode_code")

    return jsonify(
        {
            "x": pose_payload.get("x"),
            "y": pose_payload.get("y"),
            "z": pose_payload.get("z"),
            "yaw": pose_payload.get("yaw"),
            "status": pose_payload.get("status"),
            "frequency": pose_payload.get("frequency"),
            "relative_altitude": relative_altitude,
            "flight_mode": flight_mode,
        }
    )


@bp.get("/slam/status")
def slam_status():
    hub = current_app.extensions["runtime_hub"]
    status = hub.slam.status()
    return jsonify(
        {
            "connected": status.connected,
            "host": status.host,
            "port": status.port,
            "topics": status.topics,
            "last_pose": hub.slam.pose.latest() if hub.slam.pose else None,
        }
    )


@bp.get("/status")
def status():
    hub = current_app.extensions["runtime_hub"]
    if not hub.drone.connected or not hub.drone.telemetry:
        return jsonify(
            {"osd_frequency": None, "online": False, "flight_mode": "未连接"}
        ), 503
    snapshot = hub.drone.telemetry.latest()
    payload = {
        "osd_frequency": snapshot.connection.osd_frequency,
        "online": snapshot.connection.is_online,
        "flight_mode": snapshot.flight.mode_label,
    }
    return jsonify(payload)
