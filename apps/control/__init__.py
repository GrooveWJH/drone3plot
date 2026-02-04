"""
PID控制系统模块

模块化结构：
- config.py: 配置参数（包括Yaw专用配置）
- core/pid.py: PID控制器
- io/logger.py: 参数化数据记录器
- core/controller.py: 平面控制器、平面+Yaw控制器、Yaw单独控制器
- main_plane.py: 平面控制主程序入口
- main_vertical.py: 垂直高度控制主程序入口
- main_yaw.py: Yaw单独控制主程序入口
- io/visualize.py: 通用数据可视化工具
"""

from .core.pid import PIDController
from .core.controller import (
    PlaneController,
    PlaneYawController,
    YawOnlyController,
    quaternion_to_yaw,
    normalize_angle,
    get_yaw_error,
)
from .io.logger import DataLogger
from . import config

__all__ = [
    "PIDController",
    "PlaneController",
    "PlaneYawController",
    "YawOnlyController",
    "DataLogger",
    "quaternion_to_yaw",
    "normalize_angle",
    "get_yaw_error",
    "config",
]
