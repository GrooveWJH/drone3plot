"""Dashboard application factory."""

from __future__ import annotations

import atexit
import logging
import os
import threading
import time
from pathlib import Path
import sys

from flask import Flask

from dashboard.blueprints.api import api_bp
from dashboard.blueprints.ui import ui_bp
from dashboard.config import CONFIG_FILE_LOADED, CONFIG_FILE_PATH, get_config
from dashboard.extensions import socketio
from dashboard.sockets.events import register_socketio_events
from dashboard.services.mission_executor import MissionExecutor
from dashboard.services.runtime_hub import RuntimeHub


def _inject_pydjimqtt_path() -> None:
    project_root = Path(__file__).resolve().parents[1]
    sdk_path = project_root / "thirdparty" / "pydjimqtt" / "src"
    if not sdk_path.exists():
        return
    sdk_str = str(sdk_path)
    if sdk_str not in sys.path:
        sys.path.insert(0, sdk_str)


def create_app(config_name: str | None = None) -> Flask:
    """Application factory used by both CLI and WSGI servers."""

    _inject_pydjimqtt_path()
    base_path = Path(__file__).resolve().parent
    app = Flask(
        __name__,
        static_folder=str(base_path / "static"),
        template_folder=str(base_path / "templates"),
    )
    config_class = get_config(config_name)
    app.config.from_object(config_class)
    app.config["CONFIG_FILE_LOADED"] = CONFIG_FILE_LOADED
    app.config["CONFIG_FILE_PATH"] = CONFIG_FILE_PATH

    cors_origins = app.config.get("CORS_ORIGINS", "*")
    socketio.init_app(app, async_mode="threading", cors_allowed_origins=cors_origins)

    runtime_hub = RuntimeHub(app.config)
    mission_executor = MissionExecutor(runtime_hub, app.config)
    app.extensions["runtime_hub"] = runtime_hub
    app.extensions["mission_executor"] = mission_executor

    app.register_blueprint(ui_bp, url_prefix="/dashboard")
    app.register_blueprint(api_bp)

    register_socketio_events(socketio, runtime_hub, mission_executor)

    def _shutdown_background() -> None:
        mission_executor.shutdown()
        runtime_hub.stop_all()

    atexit.register(_shutdown_background)

    def _auto_connect() -> None:
        logger = logging.getLogger("dashboard")
        attempt = 0
        while True:
            attempt += 1
            try:
                logger.info("[slam] auto-connect attempt %d", attempt)
                runtime_hub.start_slam()
                logger.info("[slam] auto-connect succeeded")
                return
            except Exception as exc:
                runtime_hub.slam.stop()
                logger.warning("[slam] auto-connect failed: %s", exc)
                time.sleep(2.0)

    def _should_start_auto_connect() -> bool:
        # In debug mode, Werkzeug reloader starts a parent watcher process and a
        # child serving process. Only start background workers in the child.
        if not app.debug:
            return True
        return os.environ.get("WERKZEUG_RUN_MAIN") == "true"

    if _should_start_auto_connect():
        threading.Thread(
            target=_auto_connect, name="mqtt-auto-connect", daemon=True
        ).start()

    return app
