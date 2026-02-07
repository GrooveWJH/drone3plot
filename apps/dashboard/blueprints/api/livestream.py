"""Live streaming endpoints."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

bp = Blueprint("livestream_api", __name__)


@bp.get("/stream")
def get_stream_config():
    hub = current_app.extensions["runtime_hub"]
    stream_url = current_app.config.get("STREAM_PLACEHOLDER_URL")
    return jsonify(
        {
            "stream_url": stream_url,
            "video_id": hub.drone.streaming.video_id if hub.drone.streaming else None,
        }
    )


@bp.post("/stream/start")
def start_stream():
    hub = current_app.extensions["runtime_hub"]
    if not hub.drone.connected or not hub.drone.streaming:
        return jsonify(
            {"error": "Streaming is only available when connected to a real drone."}
        ), 409
    data = request.get_json(force=True) or {}
    rtmp_url = data.get("rtmp_url") or current_app.config.get("STREAM_PLACEHOLDER_URL")
    video_index = data.get("video_index")
    quality = data.get("video_quality")
    video_id = hub.drone.streaming.start(rtmp_url, video_index, quality)
    if not video_id:
        return jsonify({"error": "Failed to start live stream"}), 500
    return jsonify({"status": "ok", "video_id": video_id})


@bp.post("/stream/quality")
def set_stream_quality():
    hub = current_app.extensions["runtime_hub"]
    if not hub.drone.connected or not hub.drone.streaming:
        return jsonify(
            {"error": "Streaming is only available when connected to a real drone."}
        ), 409
    data = request.get_json(force=True) or {}
    quality = data.get("video_quality")
    if quality is None:
        return jsonify({"error": "video_quality is required"}), 400
    try:
        quality_value = int(quality)
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid video_quality"}), 400
    success = hub.drone.streaming.change_quality(quality_value)
    if not success:
        return jsonify({"error": "Failed to update quality"}), 500
    return jsonify({"status": "ok"})


@bp.post("/stream/stop")
def stop_stream():
    hub = current_app.extensions["runtime_hub"]
    if not hub.drone.connected or not hub.drone.streaming:
        return jsonify({"status": "noop"})
    success = hub.drone.streaming.stop()
    return jsonify({"status": "ok" if success else "failed"})
