"""Control API endpoints."""
from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from dji_dashboard.domain.models import StickCommand

bp = Blueprint("control_api", __name__)


@bp.post("/control/stick")
def stick_control():
    registry = current_app.extensions["services"]
    command = StickCommand(**(request.get_json(force=True) or {}))
    ticks = registry.control.send_stick_command(command)
    return jsonify({"status": "ok", "ticks": ticks})


@bp.get("/control/auth/status")
def control_auth_status():
    registry = current_app.extensions["services"]
    if not registry.is_connected or not registry.drc:
        return jsonify({"state": "disconnected", "last_error": None})
    return jsonify(registry.drc.status())


@bp.post("/control/auth/request")
def control_auth_request():
    registry = current_app.extensions["services"]
    if not registry.is_connected:
        try:
            registry.connect()
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500
    if not registry.drc:
        return jsonify({"error": "DRC control is only available when connected to a real drone."}), 400
    payload = request.get_json(force=True) or {}
    status = registry.drc.request_control(
        user_id=payload.get("user_id"),
        user_callsign=payload.get("user_callsign"),
    )
    if status.get("state") == "error":
        return jsonify({"error": status.get("last_error", "request_control failed")}), 500
    return jsonify(status)


@bp.post("/control/auth/confirm")
def control_auth_confirm():
    registry = current_app.extensions["services"]
    if not registry.is_connected or not registry.drc:
        return jsonify({"error": "DRC control is only available when connected to a real drone."}), 400
    try:
        status = registry.drc.confirm_control()
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 400
    if status.get("state") == "error":
        return jsonify({"error": status.get("last_error", "confirm_control failed")}), 500
    return jsonify(status)
