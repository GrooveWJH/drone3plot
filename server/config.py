from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class DashboardConfig:
    # gateway_sn: str = "9N9CN2B00121JN"
    gateway_sn: str = "9N9CN2J0012CXY"
    mqtt_host: str = "127.0.0.1"
    mqtt_port: int = 1883
    mqtt_username: str = "admin"
    mqtt_password: str = "yundrone123"
    stream_placeholder_url: str = ""
    default_video_index: str = "normal-0"
    default_video_quality: int = 0
    drc_user_id: str = "pilot_0"
    drc_user_callsign: str = "Pilot 0"
    drc_osd_frequency: int = 30
    drc_hsi_frequency: int = 10
    drc_heartbeat_interval: float = 1.0
    slam_pose_topic: str = "slam/position"
    slam_yaw_topic: str = "slam/yaw"
    slam_status_topic: str = "slam/status"
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
    mapping = {
        "DJI_GATEWAY_SN": DASHBOARD_CONFIG.gateway_sn,
        "DJI_MQTT_HOST": DASHBOARD_CONFIG.mqtt_host,
        "DJI_MQTT_PORT": str(DASHBOARD_CONFIG.mqtt_port),
        "DJI_MQTT_USERNAME": DASHBOARD_CONFIG.mqtt_username,
        "DJI_MQTT_PASSWORD": DASHBOARD_CONFIG.mqtt_password,
        "STREAM_PLACEHOLDER_URL": DASHBOARD_CONFIG.stream_placeholder_url,
        "DJI_VIDEO_INDEX": DASHBOARD_CONFIG.default_video_index,
        "DJI_VIDEO_QUALITY": str(DASHBOARD_CONFIG.default_video_quality),
        "DJI_USER_ID": DASHBOARD_CONFIG.drc_user_id,
        "DJI_USER_CALLSIGN": DASHBOARD_CONFIG.drc_user_callsign,
        "DJI_DRC_OSD_FREQUENCY": str(DASHBOARD_CONFIG.drc_osd_frequency),
        "DJI_DRC_HSI_FREQUENCY": str(DASHBOARD_CONFIG.drc_hsi_frequency),
        "DJI_DRC_HEARTBEAT_INTERVAL": str(DASHBOARD_CONFIG.drc_heartbeat_interval),
        "DJI_SLAM_POSE_TOPIC": DASHBOARD_CONFIG.slam_pose_topic,
        "DJI_SLAM_YAW_TOPIC": DASHBOARD_CONFIG.slam_yaw_topic,
        "DJI_SLAM_STATUS_TOPIC": DASHBOARD_CONFIG.slam_status_topic,
        "TELEMETRY_POLL_HZ": str(DASHBOARD_CONFIG.telemetry_poll_hz),
        "TELEMETRY_SOCKET_RATE": str(DASHBOARD_CONFIG.telemetry_socket_rate),
        "POSE_SOCKET_RATE": str(DASHBOARD_CONFIG.pose_socket_rate),
        "DASHBOARD_CORS_ORIGINS": DASHBOARD_CONFIG.cors_origins,
    }
    for key, value in mapping.items():
        os.environ[key] = value
