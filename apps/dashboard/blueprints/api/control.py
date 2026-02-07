"""Control API endpoints."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from dashboard.domain.models import StickCommand

bp = Blueprint("control_api", __name__)
_legacy_status_warned = False


def _runtime_state_payload(hub) -> dict:
    slam = hub.slam.status()
    drone = hub.drone.status()
    return {
        "slam": {
            "connected": slam.connected,
            "host": slam.host,
            "port": slam.port,
            "topics": slam.topics,
        },
        "drone": {
            "state": drone.state,
            "connected": drone.connected,
            "gateway_sn": drone.gateway_sn,
            "host": drone.host,
            "port": drone.port,
            "drc_state": drone.drc_state,
            "last_error": drone.drc_error,
        },
    }


@bp.get("/drone/status")
def drone_status():
    hub = current_app.extensions["runtime_hub"]
    return jsonify(_runtime_state_payload(hub))


@bp.post("/drone/connect")
def drone_connect():
    hub = current_app.extensions["runtime_hub"]
    ok, error = hub.connect_drone()
    if not ok:
        return jsonify({"error": error}), 400
    payload = _runtime_state_payload(hub)
    current_app.logger.info(
        "[runtime=drone] state=%s gateway_sn=%s mqtt=%s:%s",
        payload["drone"]["state"],
        payload["drone"]["gateway_sn"],
        payload["drone"]["host"],
        payload["drone"]["port"],
    )
    return jsonify(payload)


@bp.post("/drone/disconnect")
def drone_disconnect():
    hub = current_app.extensions["runtime_hub"]
    ok, error = hub.disconnect_drone()
    if not ok:
        return jsonify({"error": error}), 500
    return jsonify(_runtime_state_payload(hub))


@bp.post("/drone/auth/request")
def drone_auth_request():
    hub = current_app.extensions["runtime_hub"]
    status = hub.drone.status()
    if not status.connected or not hub.drone.drc:
        return jsonify({"error": "Drone runtime not connected."}), 409

    req_id = request.headers.get("X-Request-Id") or "n/a"
    current_app.logger.info(
        "[req_id=%s][runtime=drone] auth/request state=%s gateway_sn=%s mqtt=%s:%s",
        req_id,
        status.state,
        status.gateway_sn,
        status.host,
        status.port,
    )

    result = hub.drone.drc.request_control()
    if result.get("state") == "error":
        return jsonify({"error": result.get("last_error", "request_control failed")}), 400
    return jsonify(_runtime_state_payload(hub))


@bp.post("/drone/auth/confirm")
def drone_auth_confirm():
    hub = current_app.extensions["runtime_hub"]
    if not hub.drone.connected or not hub.drone.drc:
        return jsonify({"error": "Drone runtime not connected."}), 409

    try:
        result = hub.drone.drc.confirm_control()
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 400

    if result.get("state") == "error":
        return jsonify({"error": result.get("last_error", "confirm_control failed")}), 500

    return jsonify(_runtime_state_payload(hub))


@bp.get("/control/auth/status")
def control_auth_status():
    global _legacy_status_warned
    if not _legacy_status_warned:
        current_app.logger.warning(
            "[deprecation] GET /api/control/auth/status removed; use /api/drone/status"
        )
        _legacy_status_warned = True
    return (
        jsonify(
            {
                "error": (
                    "Deprecated endpoint removed. Use /api/drone/status. "
                    "Please hard-refresh the dashboard page."
                )
            }
        ),
        410,
    )


@bp.post("/control/auth/request")
def control_auth_request():
    current_app.logger.warning(
        "[deprecation] POST /api/control/auth/request removed; use /api/drone/auth/request"
    )
    return (
        jsonify(
            {
                "error": (
                    "Deprecated endpoint removed. Use /api/drone/auth/request. "
                    "Please hard-refresh the dashboard page."
                )
            }
        ),
        410,
    )


@bp.post("/control/auth/confirm")
def control_auth_confirm():
    current_app.logger.warning(
        "[deprecation] POST /api/control/auth/confirm removed; use /api/drone/auth/confirm"
    )
    return (
        jsonify(
            {
                "error": (
                    "Deprecated endpoint removed. Use /api/drone/auth/confirm. "
                    "Please hard-refresh the dashboard page."
                )
            }
        ),
        410,
    )


@bp.post("/control/stick")
def stick_control():
    hub = current_app.extensions["runtime_hub"]
    mission_executor = current_app.extensions.get("mission_executor")
    if mission_executor and mission_executor.is_running():
        return (
            jsonify({"error": "mission_running", "message": "Mission is running."}),
            409,
        )
    if not hub.drone.connected or not hub.drone.control:
        return jsonify({"error": "Drone runtime not connected."}), 409
    command = StickCommand(**(request.get_json(force=True) or {}))
    ticks = hub.drone.control.send_stick_command(command)
    return jsonify({"status": "ok", "ticks": ticks})
