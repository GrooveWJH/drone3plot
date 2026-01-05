"""Dashboard application factory."""
from __future__ import annotations

import atexit
from pathlib import Path
import sys

from flask import Flask

from dji_dashboard.blueprints.api import api_bp
from dji_dashboard.blueprints.ui import ui_bp
from dji_dashboard.config import CONFIG_FILE_LOADED, CONFIG_FILE_PATH, get_config
from dji_dashboard.extensions import socketio
from dji_dashboard.sockets.events import register_socketio_events


def _inject_pydjimqtt_path() -> None:
    project_root = Path(__file__).resolve().parents[2]
    sdk_path = project_root / "thirdparty" / "pydjimqtt" / "src"
    if not sdk_path.exists():
        return
    sdk_str = str(sdk_path)
    if sdk_str not in sys.path:
        sys.path.insert(0, sdk_str)


def create_app(config_name: str | None = None) -> Flask:
    """Application factory used by both CLI and WSGI servers."""

    _inject_pydjimqtt_path()
    from dji_dashboard.services import ServiceRegistry
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

    return app
