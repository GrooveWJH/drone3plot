# Control（研发脚本/实验工具）

本目录用于无人机控制算法研发与实验验证，包含平面、垂直、Yaw 控制的独立脚本与可视化工具。  
定位：**研发脚本/实验工具**，**独立启动**，不作为服务部署。

## 依赖与准备

- Python 3.12+
- 已安装本仓库依赖（含 `pydjimqtt`）

建议安装方式：

```bash
uv sync
uv pip install -e ./thirdparty/pydjimqtt
```

## 快速开始

### 1) 平面位置控制（XY）

```bash
python -m apps.control.main_plane
```

### 2) Yaw 控制

```bash
python -m apps.control.main_yaw
```

### 3) 垂直高度控制（Z）

```bash
python -m apps.control.main_vertical
```

### 4) 完整轨迹控制

```bash
python -m apps.control.main
```

## 参数修改（配置）

所有参数集中在 `apps/control/config.py`：

### 连接配置

- `GATEWAY_SN`：网关序列号
- `MQTT_CONFIG`：MQTT 连接参数（host/port/username/password）

### DRC 控制

- `DRC_USER_ID`
- `DRC_USER_CALLSIGN`
- `DRC_OSD_FREQUENCY`
- `DRC_HSI_FREQUENCY`
- `DRC_HEARTBEAT_INTERVAL`

### SLAM 话题

- `SLAM_POSE_TOPIC`：位置话题（x/y/z）
- `SLAM_YAW_TOPIC`：航向话题（yaw）

### 轨迹控制

- `TRAJECTORY_FILE`：轨迹文件路径
- `TRAJECTORY_REQUIRE_CONFIRM`：每个航点是否需要手动确认

### 平面控制（XY）

- `CONTROL_FREQUENCY`：控制频率
- `TOLERANCE_XY`：到达阈值
- `KP_XY / KI_XY / KD_XY`
- `MAX_STICK_OUTPUT`
- `PLANE_GAIN_SCHEDULING_CONFIG`：增益调度参数
- `PLANE_ARRIVAL_STABLE_TIME`
- `PLANE_USE_RANDOM_WAYPOINTS`：是否使用随机航点
- `PLANE_RANDOM_*`：随机航点参数

### 垂直控制（Z）

- `VERTICAL_HEIGHT_SOURCE`：`slam` 或 `relative`
- `VERTICAL_TARGET_HEIGHT`
- `VERTICAL_SLAM_ZERO_AT_START`
- `VERTICAL_KP / KI / KD`
- `VERTICAL_I_ACTIVATION_ERROR`
- `VERTICAL_TOLERANCE`
- `VERTICAL_MAX_THROTTLE_OUTPUT`
- `VERTICAL_CONTROL_FREQUENCY`
- `VERTICAL_ARRIVAL_STABLE_TIME`

### Yaw 控制

- `KP_YAW / KI_YAW / KD_YAW`
- `MAX_YAW_STICK_OUTPUT`
- `TOLERANCE_YAW`
- `YAW_I_ACTIVATION_ERROR`
- `YAW_ARRIVAL_STABLE_TIME`
- `YAW_DEADZONE`
- `TARGET_YAWS`
- `AUTO_NEXT_TARGET`
- `USE_RANDOM_ANGLES`
- `RANDOM_ANGLE_MIN_DIFF`

### 日志记录

- `ENABLE_DATA_LOGGING`：是否记录 CSV

## 日志与可视化分析

### 日志输出

日志默认输出到 `data/` 目录下，按时间戳生成子目录：

- 平面控制：`data/plane/<timestamp>/plane_control_data.csv`
- Yaw 控制：`data/yaw/<timestamp>/yaw_control_data.csv`
- 垂直控制：`data/vertical/<timestamp>/vertical_control_data.csv`
- 轨迹控制（若启用）：`data/<timestamp>/control_data.csv`

每次运行会生成 `latest/` 目录副本，方便快速查看。

### 生成可视化

```bash
python -m apps.control.io.visualize data/<timestamp>
```

支持的输入目录：

- `data/20240315_143022`（平面+Yaw）
- `data/yaw/20240315_143022`（Yaw）
- `data/plane/20240315_143022`（平面）
- `data/vertical/20240315_143022`（垂直）

会输出：

- HTML 图表（交互式）
- 控制统计信息（误差/杆量/频率）

## 常见问题

### 1) 找不到 `pydjimqtt`

确认已执行：

```bash
uv pip install -e ./thirdparty/pydjimqtt
```

### 2) 没有位置数据

检查 SLAM 话题配置是否与实际一致：

```python
SLAM_POSE_TOPIC = "slam/position"
SLAM_YAW_TOPIC = "slam/yaw"
```

---

如需接入服务化流程或自动化测试，请另建模块或与 `apps/dashboard` 的控制链路分离管理。  
