"""Configuration endpoints."""
from __future__ import annotations

from typing import Any, Callable, Mapping

from flask import Blueprint, current_app, jsonify, request

from dji_dashboard.services import ServiceRegistry

bp = Blueprint("config_api", __name__)

def _parse_int(value: Any) -> int:
    return int(value)

CONFIG_FIELDS: dict[str, tuple[str, Callable[[Any], Any]]] = {
    "DJI_GATEWAY_SN": ("GATEWAY_SN", str),
    "DJI_MQTT_HOST": ("MQTT_HOST", str),
    "DJI_MQTT_PORT": ("MQTT_PORT", _parse_int),
    "DJI_MQTT_USERNAME": ("MQTT_USERNAME", str),
    "DJI_MQTT_PASSWORD": ("MQTT_PASSWORD", str),
}

def _serialize_config(app_config: Mapping[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "CONFIG_FILE_LOADED": app_config.get("CONFIG_FILE_LOADED", False),
        "CONFIG_FILE_PATH": app_config.get("CONFIG_FILE_PATH"),
    }
    for env_key, (config_key, _) in CONFIG_FIELDS.items():
        value = app_config.get(config_key)
        if isinstance(value, tuple):
            value = list(value)
        payload[env_key] = value
    return payload

@bp.get("/config")
def get_config_values():
    return jsonify(_serialize_config(current_app.config))

@bp.post("/config")
def update_config_values():
    payload = request.get_json(force=True) or {}
    updated: dict[str, Any] = {}
    changed = False
    for env_key, (config_key, parser) in CONFIG_FIELDS.items():
        if env_key not in payload:
            continue
        try:
            value = parser(payload[env_key])
        except (TypeError, ValueError):
            return jsonify({"error": f"Invalid value for {env_key}."}), 400
        current_value = current_app.config.get(config_key)
        if current_value != value:
            changed = True
            current_app.config[config_key] = value
        updated[config_key] = value

    registry: ServiceRegistry | None = current_app.extensions.get("services")
    if registry and changed:
        if registry.is_connected:
            return jsonify({"error": "Cannot update config while connected."}), 409
        registry.reconfigure(current_app.config)
    return jsonify({
        "status": "ok",
        "config": _serialize_config(current_app.config),
    })
