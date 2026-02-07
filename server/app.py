from __future__ import annotations

from pathlib import Path

from flask import Flask, abort, send_file

from dashboard import create_app as create_dashboard_app
from dashboard.extensions import socketio
from .config import MEDIA_CONFIG, SERVER_CONFIG
from mediaweb.blueprint import MediaWebConfig, create_media_blueprint


DIST_DIR = Path(__file__).resolve().parents[1] / "apps" / "frontend" / "dist"


def create_app() -> Flask:
    app = create_dashboard_app()
    media_config = MediaWebConfig(
        db_path=MEDIA_CONFIG.db_path,
        storage_endpoint=MEDIA_CONFIG.storage_endpoint,
        storage_bucket=MEDIA_CONFIG.storage_bucket,
        storage_region=MEDIA_CONFIG.storage_region,
        storage_access_key=MEDIA_CONFIG.storage_access_key,
        storage_secret_key=MEDIA_CONFIG.storage_secret_key,
        storage_session_token=MEDIA_CONFIG.storage_session_token,
    )
    app.register_blueprint(create_media_blueprint(media_config), url_prefix="/media")

    @app.get("/")
    def index():
        index_path = DIST_DIR / "index.html"
        if index_path.exists():
            return send_file(index_path)
        return (
            "前端尚未构建，请先运行前端构建输出 apps/frontend/dist 目录。",
            503,
        )

    @app.get("/<path:requested>")
    def spa_assets(requested: str):
        if (
            requested.startswith("dashboard")
            or requested.startswith("api")
            or requested.startswith("socket.io")
            or requested.startswith("media")
        ):
            abort(404)
        asset_path = DIST_DIR / requested
        if asset_path.exists():
            return send_file(asset_path)
        index_path = DIST_DIR / "index.html"
        if index_path.exists():
            return send_file(index_path)
        return (
            "前端尚未构建，请先运行前端构建输出 apps/frontend/dist 目录。",
            503,
        )

    return app


if __name__ == "__main__":
    socketio.run(
        create_app(),
        host=SERVER_CONFIG.host,
        port=SERVER_CONFIG.port,
        debug=SERVER_CONFIG.debug,
    )
