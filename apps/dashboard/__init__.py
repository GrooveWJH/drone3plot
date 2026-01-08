"""Dashboard application factory."""
from __future__ import annotations

import atexit
import logging
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
    from dashboard.services import ServiceRegistry
    base_path = Path(__file__).resolve().parent
    app = Flask(__name__, static_folder=str(base_path / "static"),
                template_folder=str(base_path / "templates"))
    config_class = get_config(config_name)
    app.config.from_object(config_class)
    app.config["CONFIG_FILE_LOADED"] = CONFIG_FILE_LOADED
    app.config["CONFIG_FILE_PATH"] = CONFIG_FILE_PATH

    cors_origins = app.config.get("CORS_ORIGINS", "*")
    socketio.init_app(app, async_mode="threading",
                      cors_allowed_origins=cors_origins)

    registry = ServiceRegistry(app.config)
    app.extensions["services"] = registry

    app.register_blueprint(ui_bp, url_prefix="/dashboard")
    app.register_blueprint(api_bp)

    register_socketio_events(socketio, registry)

    atexit.register(registry.shutdown)

    def _auto_connect() -> None:
        logger = logging.getLogger("dashboard")
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            try:
                logger.info("[mqtt] auto-connect attempt %d/%d", attempt, max_attempts)
                registry.connect()
                logger.info("[mqtt] auto-connect succeeded")
                return
            except Exception as exc:
                registry.shutdown()
                logger.warning("[mqtt] auto-connect failed: %s", exc)
                time.sleep(1.0)
        logger.warning("[mqtt] auto-connect aborted after %d failures; wait for control request", max_attempts)

    threading.Thread(target=_auto_connect, name="mqtt-auto-connect", daemon=True).start()

    return app
