"""Server-rendered dashboard views."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, render_template

ui_bp = Blueprint("ui", __name__)


@ui_bp.get("/")
def dashboard():
    hub = current_app.extensions["runtime_hub"]
    active = hub.get_drone_config()
    config = current_app.config
    mqtt_port = active.get("MQTT_PORT")
    if not isinstance(mqtt_port, int) or mqtt_port <= 0:
        mqtt_port = ""
    config_values = {
        "DJI_GATEWAY_SN": active.get("GATEWAY_SN", ""),
        "DJI_MQTT_HOST": active.get("MQTT_HOST", ""),
        "DJI_MQTT_PORT": mqtt_port,
        "DJI_MQTT_USERNAME": active.get("MQTT_USERNAME", ""),
        "DJI_MQTT_PASSWORD": active.get("MQTT_PASSWORD", ""),
        "DJI_USER_ID": active.get("DRC_USER_ID", ""),
        "DJI_USER_CALLSIGN": active.get("DRC_USER_CALLSIGN", ""),
    }
    return render_template(
        "dashboard/index.html",
        config_values=config_values,
        config_file_loaded=config.get("CONFIG_FILE_LOADED", False),
        config_file_path=config.get("CONFIG_FILE_PATH"),
    )


@ui_bp.get("/health")
def healthcheck():
    hub = current_app.extensions["runtime_hub"]
    if not hub.drone.connected or not hub.drone.telemetry:
        return jsonify({"ok": True, "online": False, "mode": "未连接"})
    status = hub.drone.telemetry.latest()
    return jsonify(
        {
            "ok": True,
            "online": status.connection.is_online,
            "mode": status.flight.mode_label,
        }
    )
