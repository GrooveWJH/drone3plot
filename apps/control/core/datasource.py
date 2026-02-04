"""
SLAM 数据源抽象层
统一提供位置(x, y, z) 与 yaw 角的获取接口。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional, Tuple

from pydjimqtt.core.mqtt_client import MQTTClient

from .pose_service import PoseService


class DataSource(ABC):
    """数据源抽象基类"""

    @abstractmethod
    def get_position(self) -> Optional[Tuple[float, float, float]]:
        """获取位置数据 (x, y, z)"""
        raise NotImplementedError

    @abstractmethod
    def get_yaw(self) -> Optional[float]:
        """获取航向角（度，范围 [-180, 180]）"""
        raise NotImplementedError

    @abstractmethod
    def stop(self) -> None:
        """停止数据源"""
        raise NotImplementedError


class SlamDataSource(DataSource):
    """SLAM 数据源（slam/position + slam/yaw）"""

    def __init__(
        self, mqtt_client: MQTTClient, pose_topic: str, yaw_topic: str
    ) -> None:
        self.pose_service = PoseService(mqtt_client, pose_topic, yaw_topic)

    def _latest_valid(self) -> Optional[Tuple[float, float, float, float]]:
        pose = self.pose_service.latest()
        x = pose.get("x")
        y = pose.get("y")
        z = pose.get("z")
        yaw = pose.get("yaw")
        if x is None or y is None or z is None or yaw is None:
            return None
        return (x, y, z, yaw)

    def get_position(self) -> Optional[Tuple[float, float, float]]:
        latest = self._latest_valid()
        if latest is None:
            return None
        x, y, z, _ = latest
        return (x, y, z)

    def get_yaw(self) -> Optional[float]:
        latest = self._latest_valid()
        if latest is None:
            return None
        return latest[3]

    def stop(self) -> None:
        # PoseService uses MQTTClient callbacks; no extra cleanup needed.
        return None


def create_datasource(
    mqtt_client: MQTTClient, pose_topic: str, yaw_topic: str
) -> DataSource:
    """创建 SLAM 数据源"""
    return SlamDataSource(mqtt_client, pose_topic, yaw_topic)
