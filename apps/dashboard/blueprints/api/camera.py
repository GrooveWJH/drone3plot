"""Camera control endpoints."""
from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from dashboard.domain.models import ZoomCommand

bp = Blueprint("camera_api", __name__)


@bp.post("/camera/zoom")
def zoom_camera():
    registry = current_app.extensions["services"]
    payload = ZoomCommand(**(request.get_json(force=True) or {}))
    registry.camera.set_zoom(payload.zoom_factor, camera_type=payload.camera_type)
    return jsonify({"status": "ok", "lens": registry.camera.current_lens()})


@bp.post("/camera/lens")
def change_lens():
    registry = current_app.extensions["services"]
    data = request.get_json(force=True) or {}
    lens = data.get("camera_type")
    if not lens:
        return jsonify({"error": "camera_type is required"}), 400
    try:
        selected = registry.camera.select_lens(lens)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"status": "ok", "lens": selected})


@bp.post("/camera/photo")
def take_photo():
    registry = current_app.extensions["services"]
    data = request.get_json(force=True) or {}
    timeout = data.get("timeout", 10.0)
    try:
        result = registry.camera.take_photo(timeout=float(timeout))
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    return jsonify({"status": "ok", "result": result})
