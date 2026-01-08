"""Server-rendered dashboard views."""
from __future__ import annotations

from flask import Blueprint, current_app, jsonify, render_template

ui_bp = Blueprint("ui", __name__)


@ui_bp.get("/")
def dashboard():
    config = current_app.config
    config_values = {
        "DJI_GATEWAY_SN": config.get("GATEWAY_SN", ""),
        "DJI_MQTT_HOST": config.get("MQTT_HOST", ""),
        "DJI_MQTT_PORT": config.get("MQTT_PORT", 1883),
        "DJI_MQTT_USERNAME": config.get("MQTT_USERNAME", ""),
        "DJI_MQTT_PASSWORD": config.get("MQTT_PASSWORD", ""),
    }
    return render_template(
        "dashboard/index.html",
        config_values=config_values,
        config_file_loaded=config.get("CONFIG_FILE_LOADED", False),
        config_file_path=config.get("CONFIG_FILE_PATH"),
    )


@ui_bp.get("/health")
def healthcheck():
    registry = current_app.extensions["services"]
    status = registry.telemetry.latest()
    return jsonify({
        "ok": True,
        "online": status.connection.is_online,
        "mode": status.flight.mode_label,
    })
