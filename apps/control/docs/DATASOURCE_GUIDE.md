# SLAM 数据源指南

本项目已移除 VRPN/UWB 定位，统一使用 SLAM 话题作为控制反馈数据源。

## 数据话题
- 位置：`slam/position`（包含 `x`, `y`, `z`）
- 航向角：`slam/yaw`（包含 `yaw`，范围 -180~180）

## 配置位置
修改 `control/config.py`：

```python
SLAM_POSE_TOPIC = "slam/position"
SLAM_YAW_TOPIC = "slam/yaw"
```

## 使用方式
- 平面位置控制：`python -m apps.control.main_plane`
- Yaw 控制：`python -m apps.control.main_yaw`

两者都会通过 `SlamDataSource` 订阅 SLAM 话题并读取实时数据。
