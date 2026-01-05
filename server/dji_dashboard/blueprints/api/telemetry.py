"""Telemetry API endpoints."""
from __future__ import annotations

from flask import Blueprint, current_app, jsonify

bp = Blueprint("telemetry_api", __name__)


@bp.get("/telemetry")
def telemetry_snapshot():
    registry = current_app.extensions["services"]
    if not registry.is_connected or not registry.telemetry:
        return jsonify({"error": "Telemetry is not available before connecting."}), 503
    return jsonify(registry.telemetry.latest_dict())


@bp.get("/pose")
def pose_snapshot():
    registry = current_app.extensions["services"]
    if not registry.is_connected or not registry.pose:
        return jsonify({"x": None, "y": None, "z": None, "yaw": None})
    return jsonify(registry.pose.latest())


@bp.get("/status")
def status():
    registry = current_app.extensions["services"]
    if not registry.is_connected or not registry.telemetry:
        return jsonify({"osd_frequency": None, "online": False, "flight_mode": "未连接"}), 503
    snapshot = registry.telemetry.latest()
    payload = {
        "osd_frequency": snapshot.connection.osd_frequency,
        "online": snapshot.connection.is_online,
        "flight_mode": snapshot.flight.mode_label,
    }
    return jsonify(payload)
