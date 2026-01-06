"""Application configuration objects."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Type


CONFIG_FILE_LOADED = False
CONFIG_FILE_PATH: str | None = None


def _load_config_file(config_path: Path) -> None:
    global CONFIG_FILE_LOADED, CONFIG_FILE_PATH
    if not config_path.exists():
        return
    for raw_line in config_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key and key not in os.environ:
            os.environ[key] = value
    CONFIG_FILE_LOADED = True
    CONFIG_FILE_PATH = str(config_path)


config_env_path = os.getenv("DASHBOARD_CONFIG_FILE")
if config_env_path:
    _load_config_file(Path(config_env_path))


@dataclass
class BaseConfig:
    """Default configuration shared across environments."""

    SECRET_KEY: str = os.getenv("DASHBOARD_SECRET_KEY", "dev-secret-key")
    GATEWAY_SN: str = os.getenv("DJI_GATEWAY_SN", "9N9CN2B00121JN")
    MQTT_HOST: str = os.getenv("DJI_MQTT_HOST", "192.168.20.186")
    MQTT_PORT: int = int(os.getenv("DJI_MQTT_PORT", "1883"))
    MQTT_USERNAME: str = os.getenv("DJI_MQTT_USERNAME", "admin")
    MQTT_PASSWORD: str = os.getenv("DJI_MQTT_PASSWORD", "yundrone123")
    STREAM_PLACEHOLDER_URL: str = os.getenv("STREAM_PLACEHOLDER_URL", "")
    DEFAULT_VIDEO_INDEX: str = os.getenv("DJI_VIDEO_INDEX", "normal-0")
    DEFAULT_VIDEO_QUALITY: int = int(os.getenv("DJI_VIDEO_QUALITY", "0"))
    DRC_USER_ID: str = os.getenv("DJI_USER_ID", "pilot_0")
    DRC_USER_CALLSIGN: str = os.getenv("DJI_USER_CALLSIGN", "Pilot 0")
    DRC_OSD_FREQUENCY: int = int(os.getenv("DJI_DRC_OSD_FREQUENCY", "30"))
    DRC_HSI_FREQUENCY: int = int(os.getenv("DJI_DRC_HSI_FREQUENCY", "10"))
    DRC_HEARTBEAT_INTERVAL: float = float(os.getenv("DJI_DRC_HEARTBEAT_INTERVAL", "1.0"))
    SLAM_POSE_TOPIC: str = os.getenv("DJI_SLAM_POSE_TOPIC", "slam/position")
    SLAM_YAW_TOPIC: str = os.getenv("DJI_SLAM_YAW_TOPIC", "slam/yaw")
    SLAM_STATUS_TOPIC: str = os.getenv("DJI_SLAM_STATUS_TOPIC", "slam/status")
    SLAM_FREQUENCY_TOPIC: str = os.getenv("DJI_SLAM_FREQUENCY_TOPIC", "slam/frequency")
    TRAJECTORY_MQTT_TOPIC: str = os.getenv("DJI_TRAJECTORY_TOPIC", "uav/trajectory")
    TRAJECTORY_PUBLISH_RATE: float = float(os.getenv("DJI_TRAJECTORY_PUBLISH_RATE", "1"))
    TELEMETRY_POLL_HZ: float = float(os.getenv("TELEMETRY_POLL_HZ", "2"))
    SOCKET_RATE_LIMIT: float = float(os.getenv("TELEMETRY_SOCKET_RATE", "0.5"))
    POSE_SOCKET_RATE: float = float(os.getenv("POSE_SOCKET_RATE", "0.2"))
    CORS_ORIGINS: str | list[str] = os.getenv("DASHBOARD_CORS_ORIGINS", "*")
    AVAILABLE_LENSES: tuple[str, ...] = ("zoom", "wide", "ir")


class DevelopmentConfig(BaseConfig):
    DEBUG: bool = True


class ProductionConfig(BaseConfig):
    DEBUG: bool = False
    

_CONFIG_MAP: dict[str | None, Type[BaseConfig]] = {
    None: DevelopmentConfig,
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}


def get_config(name: str | None) -> Type[BaseConfig]:
    """Return the config class for the provided name."""

    return _CONFIG_MAP.get(name, DevelopmentConfig)
