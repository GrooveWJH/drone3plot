"""Aggregate API blueprint."""

from __future__ import annotations

from flask import Blueprint

from . import camera, config, control, livestream, telemetry, logs, trajectory

api_bp = Blueprint("api", __name__, url_prefix="/api")
api_bp.register_blueprint(telemetry.bp)
api_bp.register_blueprint(camera.bp)
api_bp.register_blueprint(control.bp)
api_bp.register_blueprint(livestream.bp)
api_bp.register_blueprint(config.bp)
api_bp.register_blueprint(logs.bp)
api_bp.register_blueprint(trajectory.bp)
