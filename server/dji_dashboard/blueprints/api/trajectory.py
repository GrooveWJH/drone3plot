"""Trajectory ingest + execution endpoints."""
from __future__ import annotations

import time
from typing import Any, Dict, List

from flask import Blueprint, current_app, jsonify, request

from dji_dashboard.services import ServiceRegistry

bp = Blueprint("trajectory_api", __name__)


def _parse_float(value: Any) -> float:
    return float(value)


def _coerce_point(entry: Any) -> Dict[str, Any] | None:
    if not isinstance(entry, dict):
        return None
    try:
        return {
            "x": _parse_float(entry.get("x")),
            "y": _parse_float(entry.get("y")),
            "z": _parse_float(entry.get("z")),
            "yaw": _parse_float(entry.get("yaw")),
            "takePhoto": bool(entry.get("takePhoto")),
        }
    except (TypeError, ValueError):
        return None


@bp.post("/trajectory")
def update_trajectory():
    payload = request.get_json(force=True) or {}
    points_raw = payload.get("points")
    if not isinstance(points_raw, list):
        return jsonify({"error": "points must be a list."}), 400

    points: List[Dict[str, Any]] = []
    for entry in points_raw:
        normalized = _coerce_point(entry)
        if normalized is None:
            return jsonify({"error": "Invalid point payload."}), 400
        points.append(normalized)

    trajectory_payload = {
        "trajectory_id": payload.get("trajectory_id") or "current",
        "name": payload.get("name") or "trajectory",
        "updated_at": payload.get("updated_at") or int(time.time() * 1000),
        "points": points,
    }

    registry: ServiceRegistry | None = current_app.extensions.get("services")
    if not registry or not registry.trajectory:
        return jsonify({"error": "Trajectory service unavailable."}), 503

    registry.trajectory.set_http_payload(trajectory_payload)
    return jsonify({"status": "ok", "points": len(points)})


@bp.get("/trajectory")
def get_trajectory():
    registry: ServiceRegistry | None = current_app.extensions.get("services")
    if not registry or not registry.trajectory:
        return jsonify({"error": "Trajectory service unavailable."}), 503
    payload, received_at = registry.trajectory.latest()
    return jsonify({"payload": payload, "received_at": received_at})


@bp.post("/trajectory/execute")
def execute_trajectory():
    registry: ServiceRegistry | None = current_app.extensions.get("services")
    if not registry or not registry.trajectory:
        return jsonify({"error": "Trajectory service unavailable."}), 503
    payload, received_at = registry.trajectory.latest()
    if not payload or not payload.get("points"):
        return jsonify({"error": "No trajectory available from MQTT."}), 409

    points = payload.get("points", [])
    print(f"[trajectory] execute start: {len(points)} points")
    print("[trajectory] execute completed")
    return jsonify({"status": "ok", "points": len(points), "received_at": received_at})
