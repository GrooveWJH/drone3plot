from __future__ import annotations

import logging

from dji_dashboard import create_app
from dji_dashboard.extensions import socketio

from server.config import SERVER_CONFIG, apply_dashboard_env


def main() -> None:
    apply_dashboard_env()
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    app = create_app()
    socketio.run(
        app,
        host=SERVER_CONFIG.host,
        port=SERVER_CONFIG.port,
        debug=SERVER_CONFIG.debug,
    )


if __name__ == "__main__":
    main()
