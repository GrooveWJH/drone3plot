"""Flask extension instances."""

from __future__ import annotations

from flask_socketio import SocketIO

socketio = SocketIO(logger=False, engineio_logger=False)
