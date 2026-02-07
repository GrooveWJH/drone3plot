"""Mission execution API endpoints."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

bp = Blueprint("mission_api", __name__)


@bp.post("/mission/start")
def mission_start():
    executor = current_app.extensions["mission_executor"]
    payload = request.get_json(silent=True) or {}
    try:
        run_id = executor.start(payload)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 409
    return jsonify({"status": "started", "run_id": run_id, "mission": executor.status()})


@bp.post("/mission/abort")
def mission_abort():
    executor = current_app.extensions["mission_executor"]
    executor.abort()
    return jsonify({"status": "aborting", "mission": executor.status()})


@bp.get("/mission/status")
def mission_status():
    executor = current_app.extensions["mission_executor"]
    return jsonify(executor.status())


@bp.get("/mission/history")
def mission_history():
    executor = current_app.extensions["mission_executor"]
    return jsonify({"items": executor.history()})

