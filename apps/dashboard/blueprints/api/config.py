"""Drone configuration endpoints."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

bp = Blueprint("config_api", __name__)


DRONE_CONFIG_FIELDS = {
    "DJI_GATEWAY_SN": "GATEWAY_SN",
    "DJI_MQTT_HOST": "MQTT_HOST",
    "DJI_MQTT_PORT": "MQTT_PORT",
    "DJI_MQTT_USERNAME": "MQTT_USERNAME",
    "DJI_MQTT_PASSWORD": "MQTT_PASSWORD",
    "DJI_USER_ID": "DRC_USER_ID",
    "DJI_USER_CALLSIGN": "DRC_USER_CALLSIGN",
}


def _serialize_drone_config(payload: dict) -> dict:
    return {
        "DJI_GATEWAY_SN": payload.get("GATEWAY_SN", ""),
        "DJI_MQTT_HOST": payload.get("MQTT_HOST", ""),
        "DJI_MQTT_PORT": payload.get("MQTT_PORT", 0),
        "DJI_MQTT_USERNAME": payload.get("MQTT_USERNAME", ""),
        "DJI_MQTT_PASSWORD": payload.get("MQTT_PASSWORD", ""),
        "DJI_USER_ID": payload.get("DRC_USER_ID", ""),
        "DJI_USER_CALLSIGN": payload.get("DRC_USER_CALLSIGN", ""),
    }


@bp.get("/drone/config")
def get_drone_config():
    hub = current_app.extensions["runtime_hub"]
    return jsonify({"config": _serialize_drone_config(hub.get_drone_config())})


@bp.post("/drone/config")
def update_drone_config():
    hub = current_app.extensions["runtime_hub"]
    payload = request.get_json(force=True) or {}
    changed, error = hub.update_drone_config(payload)
    if error:
        status = 409 if "while connected" in error else 400
        return jsonify({"error": error}), status
    return jsonify(
        {
            "status": "ok",
            "changed": changed,
            "config": _serialize_drone_config(hub.get_drone_config()),
        }
    )


@bp.get("/config")
def compat_get_config_values():
    current_app.logger.warning("[deprecation] GET /api/config -> use /api/drone/config")
    return get_drone_config()


@bp.post("/config")
def compat_update_config_values():
    current_app.logger.warning("[deprecation] POST /api/config -> use /api/drone/config")
    return update_drone_config()
