# 云纵无人机自动巡检系统 MQTT 接口协议（v1）

>2026.1.5, GrooveWJH

本文件仅定义通讯协议和话题规划，不涉及具体代码实现。所有载荷统一为 JSON，编码 UTF-8。

## 1. 总体规范

### 1.1 版本与命名

采用版本化话题：

- `yundrone/v1/...`

v1 仅支持单个无人机对象。

### 1.1.1 版本兼容策略

- v1 内部字段可扩展，但不得改变既有字段语义
- 新字段应提供合理默认值，保证旧客户端可正常解析
- 若发生破坏性变更，必须升级到 v2 并保留 v1 兼容窗口

### 1.1.2 鉴权与访问控制

鉴权与访问控制策略以实际 MQTT Broker（EMQX）配置为准，包括但不限于：

- 用户名/密码或证书认证
- TLS 加密
- ACL 细化到 topic 级别的发布/订阅权限

### 1.2 QoS 与 Retain

| 类型 | QoS | Retain |
| --- | --- | --- |
| 遥测/状态类 | 0 | false |
| 告警类 | 1 | false |
| 控制类 | 1 | false |
| 请求/响应 | 1 | false |

说明：QoS 表示消息投递可靠性等级，0 为最多一次，1 为至少一次。  
说明：retain 表示 MQTT Broker 是否保留并向新订阅者立即推送“最后一条消息”。本协议中全部为 false。

### 1.3 发布频率与节流策略

| 话题 | 频率 | 备注 |
| --- | --- | --- |
| `yundrone/v1/drone/telemetry` | 10Hz | - |
| `yundrone/v1/drone/status` | 1Hz | - |
| `yundrone/v1/drone/alerts` | 5Hz | 有告警时立即触发 |
| `yundrone/v1/mission/info` | 2Hz | 执行任务时 |
| `yundrone/v1/media/live` | 1Hz | 地址变更时立即触发 |

### 1.4 通用字段

所有系统返回的数据包含：

- `ts`: 毫秒时间戳（int）

仅请求/响应类需要：

- `req_id`: 请求 ID，用于请求与回执/响应一一对应

`mission_name` 作为任务唯一标识符，系统不允许创建同名任务。

### 1.5 数据类型与单位

| 字段 | 单位/范围 |
| --- | --- |
| `position` | 米（m） |
| `distance_m` | 米（m） |
| `battery.percent` | 百分比（0–100） |
| `euler_deg` | 角度制（degree） |

### 1.6 话题权限矩阵

| 方向 | 话题 |
| --- | --- |
| 仅发布 | `yundrone/v1/drone/telemetry`、`yundrone/v1/drone/status`、`yundrone/v1/drone/alerts`、`yundrone/v1/mission/info`、`yundrone/v1/media/live` |
| 仅请求 | `yundrone/v1/mission/list/request`、`yundrone/v1/mission/trajectory/request`、`yundrone/v1/media/picture/request`、`yundrone/v1/mission/control` |
| 仅响应 | `yundrone/v1/mission/list/response`、`yundrone/v1/mission/trajectory/response`、`yundrone/v1/media/picture/response`、`yundrone/v1/mission/control/ack` |

### 1.7 在线状态与保活

在线状态由 `yundrone/v1/drone/status` 的 `flight_mode` 反映；当设备离线时应发布 `flight_mode = -1`。

## 2. 话题与载荷

### 2.1 无人机遥测与状态

#### 2.1.1 `yundrone/v1/drone/telemetry`（发布）

包含电量 + 姿态/位置。

```json
{
  "ts": 1736150000123,
  "battery": {
    "percent": 56
  },
  "pose": {
    "position": {"x": 1.2, "y": -0.3, "z": 5.6},
    "attitude": {
      "euler_deg": {"roll": 0.1, "pitch": 0.2, "yaw": 35.6},
      "quaternion": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0}
    }
  }
}
```

说明：

- 坐标系：ROS2 ENU（East, North, Up）
- 角度：以 degree 表示 roll/pitch/yaw，四元数与欧拉角同时发送

#### 2.1.2 `yundrone/v1/drone/status`（发布）

飞行模式与工作状态。

```json
{
  "ts": 1736150000123,
  "flight_mode": 0
}
```

枚举：

- `-1` 未连接
- `0` 待机
- `1` 飞行中

### 2.2 告警

#### 2.2.1 `yundrone/v1/drone/alerts`（发布）

电量低告警、障碍物告警等。

```json
{
  "ts": 1736150000123,
  "battery_low": false,
  "obstacles": [
    {"direction_deg": 0, "distance_m": 2.1},
    {"direction_deg": 45, "distance_m": 1.8},
    {"direction_deg": 90, "distance_m": 2.5},
    {"direction_deg": 135, "distance_m": 1.6},
    {"direction_deg": 180, "distance_m": 2.0},
    {"direction_deg": 225, "distance_m": 2.3},
    {"direction_deg": 270, "distance_m": 1.9},
    {"direction_deg": 315, "distance_m": 2.4}
  ]
}
```

说明：

- `battery_low` 触发条件：电量 < 20%
- `obstacles` 可为空数组，仅上报 `distance_m <= 2.5` 的告警，同时最多 8 个方向

### 2.3 任务信息与任务列表

#### 2.3.1 `yundrone/v1/mission/info`（发布）

当前执行任务的状态。

```json
{
  "ts": 1736150000123,
  "mission_name": "warehouse_sweep",
  "progress": {
    "current_index": 12,
    "total": 40,
    "percent": 30
  }
}
```

#### 2.3.2 任务列表请求/响应

- 请求：`yundrone/v1/mission/list/request`
- 响应：`yundrone/v1/mission/list/response`

请求：

```json
{
  "req_id": "req-8b7f",
  "ts": 1736150000123,
  "action": "list"
}
```

响应（任务名列表）：

```json
{
  "req_id": "req-8b7f",
  "ts": 1736150000456,
  "missions": [
    {"mission_name": "warehouse_sweep"},
    {"mission_name": "grid_scan_01"},
    {"mission_name": "dock_return"},
    {"mission_name": "road_follow"},
    {"mission_name": "pipeline_check"},
    {"mission_name": "roof_inspection"},
    {"mission_name": "default_trajectory"}
  ]
}
```

错误响应示例：

```json
{
  "req_id": "req-8b7f",
  "ts": 1736150000456,
  "code": "ERR_BAD_REQUEST",
  "message": "invalid request"
}
```

#### 2.3.3 单个任务轨迹请求/响应

用于获取某个任务的完整轨迹数据，字段与当前源码一致，参考 `public/trajectories/default_trajectory.json`，不含点云坐标转换。

- 请求：`yundrone/v1/mission/trajectory/request`
- 响应：`yundrone/v1/mission/trajectory/response`

请求：

```json
{
  "req_id": "req-3c9a",
  "ts": 1736150000123,
  "mission_name": "default_trajectory"
}
```

响应（示意）：

```json
{
  "req_id": "req-3c9a",
  "ts": 1736150000456,
  "mission_name": "default_trajectory",
  "trajectory": {
    "name": "默认航线",
    "createdAt": "2025-01-01T00:00:00Z",
    "waypoints": [
      {"x": 0, "y": 0, "z": 0, "yaw": 0, "takePhoto": false},
      {"x": 5, "y": 0, "z": 2, "yaw": 15, "takePhoto": true}
    ]
  }
}
```

错误响应示例：

```json
{
  "req_id": "req-3c9a",
  "ts": 1736150000456,
  "code": "ERR_NO_MISSION",
  "message": "mission not found"
}
```

### 2.4 媒体

#### 2.4.1 `yundrone/v1/media/live`（发布）

可见光与热成像流地址。

```json
{
  "ts": 1736150000123,
  "visible_url": "http://.../live/stream.m3u8",
  "thermal_url": "http://.../thermal/stream.m3u8"
}
```

#### 2.4.2 图片请求/响应

- 请求：`yundrone/v1/media/picture/request`
- 响应：`yundrone/v1/media/picture/response`

请求列表：

```json
{"req_id": "req-1d6c", "ts": 1736150000123, "action": "list"}
```

响应列表（直接原图地址，无缩略图）：

```json
{
  "req_id": "req-1d6c",
  "ts": 1736150000456,
  "items": [
    {"id": 12, "name": "img_001.jpg", "ts": 1736150000123, "url": "http://.../img_001.jpg"},
    {"id": 13, "name": "img_002.jpg", "ts": 1736150001123, "url": "http://.../img_002.jpg"},
    {"id": 14, "name": "img_003.jpg", "ts": 1736150002123, "url": "http://.../img_003.jpg"}
  ]
}
```

错误响应示例：

```json
{
  "req_id": "req-1d6c",
  "ts": 1736150000456,
  "code": "ERR_BAD_REQUEST",
  "message": "invalid request"
}
```

请求单图：

```json
{"req_id": "req-4f20", "ts": 1736150000123, "action": "get", "id": 12}
```

响应单图：

```json
{"req_id": "req-4f20", "ts": 1736150000456, "url": "http://.../img_001.jpg"}
```

错误响应示例：

```json
{"req_id": "req-4f20", "ts": 1736150000456, "code": "ERR_NOT_FOUND", "message": "image not found"}
```

### 2.5 任务控制

#### 2.5.1 `yundrone/v1/mission/control`（下行）

所有控制指令必须有回执。

请求示例：

```json
{ "req_id": "req-a102", "ts": 1736150000123, "action": "start", "mission_name": "default_trajectory" }
{ "req_id": "req-b7e1", "ts": 1736150000123, "action": "pause" }
{ "req_id": "req-19df", "ts": 1736150000123, "action": "resume" }
{ "req_id": "req-5c44", "ts": 1736150000123, "action": "return_home" }
```

#### 2.5.2 `yundrone/v1/mission/control/ack`（回执）

统一回执结构：

```json
{
  "req_id": "req-a102",
  "ts": 1736150000456,
  "accepted": true,
  "code": "OK",
  "message": "start accepted"
}
```

错误码：

| 错误码 | 含义 |
| --- | --- |
| `OK` | 成功 |
| `ERR_BAD_REQUEST` | 请求格式错误 |
| `ERR_NO_MISSION` | 未指定或找不到任务 |
| `ERR_ALREADY_RUNNING` | 已在执行中 |
| `ERR_NOT_STARTED` | 当前未执行任务 |
| `ERR_INVALID_STATE` | 状态不允许该操作 |

动作与回执：

| action | 成功 | 失败 |
| --- | --- | --- |
| `start` | `OK` | `ERR_NO_MISSION` / `ERR_ALREADY_RUNNING` |
| `pause` | `OK` | `ERR_NOT_STARTED` |
| `resume` | `OK` | `ERR_NOT_STARTED` |
| `return_home` | `OK` | `ERR_INVALID_STATE` |

若任务未开始就发送 `pause` / `resume` / `return_home`，返回 `ERR_NOT_STARTED`。
