"""Trajectory ingest + execution endpoints."""

from __future__ import annotations

import time
from typing import Any, Dict, List

from flask import Blueprint, current_app, jsonify, request

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
            "takePhoto": bool(entry.get("takePhoto", True)),
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

    mission_executor = current_app.extensions["mission_executor"]
    draft = mission_executor.update_draft(trajectory_payload)

    published = False
    hub = current_app.extensions["runtime_hub"]
    if hub.drone.connected and hub.drone.trajectory:
        hub.drone.trajectory.set_http_payload(trajectory_payload)
        published = True

    return jsonify(
        {
            "status": "ok",
            "points": len(points),
            "published": published,
            "draft": draft,
        }
    )


@bp.get("/trajectory")
def get_trajectory():
    mission_executor = current_app.extensions["mission_executor"]
    draft = mission_executor.get_draft()

    hub = current_app.extensions["runtime_hub"]
    payload = None
    received_at = None
    if hub.drone.connected and hub.drone.trajectory:
        payload, received_at = hub.drone.trajectory.latest()

    return jsonify(
        {
            "payload": payload,
            "received_at": received_at,
            "draft": draft,
        }
    )


@bp.post("/trajectory/execute")
def execute_trajectory():
    mission_executor = current_app.extensions["mission_executor"]
    current_app.logger.warning(
        "[deprecation] POST /api/trajectory/execute -> use /api/mission/start"
    )
    try:
        run_id = mission_executor.start({})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 409
    return jsonify({"status": "started", "run_id": run_id, "mission": mission_executor.status()})
