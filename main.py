import argparse
import logging
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent
server_root = project_root / "server"
apps_root = project_root / "apps"
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
if str(server_root) not in sys.path:
    sys.path.insert(0, str(server_root))
if str(apps_root) not in sys.path:
    sys.path.insert(0, str(apps_root))

from server import create_app
from server.config import SERVER_CONFIG, apply_dashboard_env
from dashboard.extensions import socketio  # type: ignore[import-not-found]


def main() -> None:
    parser = argparse.ArgumentParser(description="Drone3Plot server")
    parser.add_argument(
        "--log-level",
        default="info",
        choices=["debug", "info", "warning", "error"],
        help="Log verbosity for server output",
    )
    args = parser.parse_args()

    log_level = args.log_level.lower()
    logging.basicConfig(level=getattr(logging, log_level.upper(), logging.INFO))
    if log_level != "debug":
        logging.getLogger("werkzeug").setLevel(logging.ERROR)

    apply_dashboard_env()
    app = create_app()
    if log_level != "debug":
        app.logger.setLevel(logging.WARNING)
    socketio.run(
        app,
        host=SERVER_CONFIG.host,
        port=SERVER_CONFIG.port,
        debug=SERVER_CONFIG.debug,
        log_output=log_level == "debug",
    )


if __name__ == "__main__":
    main()
