"""Live streaming endpoints."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

bp = Blueprint("livestream_api", __name__)


@bp.get("/stream")
def get_stream_config():
    registry = current_app.extensions["services"]
    stream_url = current_app.config.get("STREAM_PLACEHOLDER_URL")
    return jsonify(
        {
            "stream_url": stream_url,
            "video_id": registry.streaming.video_id if registry.streaming else None,
        }
    )


@bp.post("/stream/start")
def start_stream():
    registry = current_app.extensions["services"]
    if not registry.streaming:
        return jsonify(
            {"error": "Streaming is only available when connected to a real drone."}
        ), 400
    data = request.get_json(force=True) or {}
    rtmp_url = data.get("rtmp_url") or current_app.config.get("STREAM_PLACEHOLDER_URL")
    video_index = data.get("video_index")
    quality = data.get("video_quality")
    video_id = registry.streaming.start(rtmp_url, video_index, quality)
    if not video_id:
        return jsonify({"error": "Failed to start live stream"}), 500
    return jsonify({"status": "ok", "video_id": video_id})


@bp.post("/stream/quality")
def set_stream_quality():
    registry = current_app.extensions["services"]
    if not registry.streaming:
        return jsonify(
            {"error": "Streaming is only available when connected to a real drone."}
        ), 400
    data = request.get_json(force=True) or {}
    quality = data.get("video_quality")
    if quality is None:
        return jsonify({"error": "video_quality is required"}), 400
    try:
        quality_value = int(quality)
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid video_quality"}), 400
    success = registry.streaming.change_quality(quality_value)
    if not success:
        return jsonify({"error": "Failed to update quality"}), 500
    return jsonify({"status": "ok"})


@bp.post("/stream/stop")
def stop_stream():
    registry = current_app.extensions["services"]
    if not registry.streaming:
        return jsonify({"status": "noop"})
    success = registry.streaming.stop()
    return jsonify({"status": "ok" if success else "failed"})
