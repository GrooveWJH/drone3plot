from __future__ import annotations

import logging

from dashboard import create_app
from dashboard.extensions import socketio

from server.config import SERVER_CONFIG


def main() -> None:
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
