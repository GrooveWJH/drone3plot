from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DashboardConfig:
    gateway_sn: str = ""
    mqtt_host: str = ""
    mqtt_port: int = 0
    mqtt_username: str = ""
    mqtt_password: str = ""
    stream_placeholder_url: str = ""
    default_video_index: str = "normal-0"
    default_video_quality: int = 0
    drc_user_id: str = ""
    drc_user_callsign: str = ""
    drc_osd_frequency: int = 30
    drc_hsi_frequency: int = 10
    drc_heartbeat_interval: float = 1.0
    slam_pose_topic: str = "slam/position"
    slam_yaw_topic: str = "slam/yaw"
    slam_status_topic: str = "slam/status"
    slam_mqtt_host: str = "127.0.0.1"
    slam_mqtt_port: int = 1883
    slam_mqtt_username: str = ""
    slam_mqtt_password: str = ""
    telemetry_poll_hz: float = 2.0
    telemetry_socket_rate: float = 0.5
    pose_socket_rate: float = 0.2
    cors_origins: str = "*"


@dataclass(frozen=True)
class ServerConfig:
    host: str = "127.0.0.1"
    port: int = 5050
    debug: bool = True


@dataclass(frozen=True)
class MediaConfig:
    db_path: str = (
        "/Users/groove/Project/work/YunDrone/DJI/MediaServer-CloudAPI/data/media.db"
    )
    storage_endpoint: str = "http://127.0.0.1:9000"
    storage_bucket: str = "media"
    storage_region: str = "us-east-1"
    storage_access_key: str = "minioadmin"
    storage_secret_key: str = "minioadmin"
    storage_session_token: str = ""


DASHBOARD_CONFIG = DashboardConfig()
SERVER_CONFIG = ServerConfig()
MEDIA_CONFIG = MediaConfig()


def apply_dashboard_env() -> None:
    # Intentionally no-op: dashboard MQTT/DRC credentials now come only from web input.
    return None
