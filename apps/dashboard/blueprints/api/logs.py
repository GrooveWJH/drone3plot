
"""Client-side log collection endpoints."""
from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

bp = Blueprint("logs_api", __name__)


@bp.post("/logs/client")
def log_client_message():
    payload = request.get_json(force=True) or {}
    source = payload.get("source", "client")
    message = payload.get("message", "")
    details = payload.get("details")
    current_app.logger.warning("[client:%s] %s | %s", source, message, details)
    return jsonify({"status": "ok"})
