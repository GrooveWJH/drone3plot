"""Camera control endpoints."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from dashboard.domain.models import ZoomCommand

bp = Blueprint("camera_api", __name__)


@bp.post("/camera/zoom")
def zoom_camera():
    hub = current_app.extensions["runtime_hub"]
    if not hub.drone.connected or not hub.drone.camera:
        return jsonify({"error": "Drone runtime not connected."}), 409
    payload = ZoomCommand(**(request.get_json(force=True) or {}))
    hub.drone.camera.set_zoom(payload.zoom_factor, camera_type=payload.camera_type)
    return jsonify({"status": "ok", "lens": hub.drone.camera.current_lens()})


@bp.post("/camera/lens")
def change_lens():
    hub = current_app.extensions["runtime_hub"]
    if not hub.drone.connected or not hub.drone.camera:
        return jsonify({"error": "Drone runtime not connected."}), 409
    data = request.get_json(force=True) or {}
    lens = data.get("camera_type")
    if not lens:
        return jsonify({"error": "camera_type is required"}), 400
    try:
        selected = hub.drone.camera.select_lens(lens)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"status": "ok", "lens": selected})


@bp.post("/camera/photo")
def take_photo():
    hub = current_app.extensions["runtime_hub"]
    if not hub.drone.connected or not hub.drone.camera:
        return jsonify({"error": "Drone runtime not connected."}), 409
    data = request.get_json(force=True) or {}
    timeout = data.get("timeout", 10.0)
    try:
        result = hub.drone.camera.take_photo(timeout=float(timeout))
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    return jsonify({"status": "ok", "result": result})
