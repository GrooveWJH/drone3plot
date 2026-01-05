import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent
server_root = project_root / "server"
sys.path.insert(0, str(server_root))

from server import create_app
from server.config import SERVER_CONFIG, apply_dashboard_env
from dji_dashboard.extensions import socketio  # type: ignore[import-not-found]


def main() -> None:
    apply_dashboard_env()
    app = create_app()
    socketio.run(
        app,
        host=SERVER_CONFIG.host,
        port=SERVER_CONFIG.port,
        debug=SERVER_CONFIG.debug,
    )


if __name__ == "__main__":
    main()
