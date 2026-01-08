# 云纵自动巡检系统 MQTT 接口协议（v1）

>2026.1.7 - GrooveWJH

定义通讯协议和话题规划。所有载荷统一为 JSON，编码 UTF-8。

## 目录

- [1. 总体规范](#1-总体规范)
  - [1.1 版本与命名](#11-版本与命名)
  - [1.1.1 版本兼容策略](#111-版本兼容策略)
  - [1.1.2 鉴权与访问控制](#112-鉴权与访问控制)
  - [1.2 QoS 与 Retain](#12-qos-与-retain)
  - [1.3 发布频率与节流策略](#13-发布频率与节流策略)
  - [1.4 通用字段](#14-通用字段)
  - [1.4.1 请求有效期与重复处理](#141-请求有效期与重复处理)
  - [1.5 数据类型与单位](#15-数据类型与单位)
  - [1.6 话题权限矩阵](#16-话题权限矩阵)
  - [1.7 在线状态与保活](#17-在线状态与保活)
- [2. 话题与载荷](#2-话题与载荷)
  - [2.1 无人机遥测与状态](#21-无人机遥测与状态)
    - [2.1.1 yundrone/v1/drone/telemetry（发布）](#211-yundronev1dronetelemetry发布)
    - [2.1.2 yundrone/v1/drone/status（发布）](#212-yundronev1dronestatus发布)
  - [2.2 告警](#22-告警)
    - [2.2.1 yundrone/v1/drone/alerts（发布）](#221-yundronev1dronealerts发布)
  - [2.3 任务信息与任务列表](#23-任务信息与任务列表)
    - [2.3.1 yundrone/v1/mission/info（发布）](#231-yundronev1missioninfo发布)
    - [2.3.2 任务列表请求/响应](#232-任务列表请求响应)
    - [2.3.3 单个任务轨迹请求/响应](#233-单个任务轨迹请求响应)
  - [2.4 媒体](#24-媒体)
    - [2.4.1 直播流请求/响应](#241-直播流请求响应)
    - [2.4.2 图片请求/响应](#242-图片请求响应)
  - [2.5 任务控制](#25-任务控制)
    - [2.5.1 yundrone/v1/mission/control（下行）](#251-yundronev1missioncontrol下行)
    - [2.5.2 yundrone/v1/mission/control/ack（回执）](#252-yundronev1missioncontrolack回执)
  - [2.6 云台控制](#26-云台控制)
    - [2.6.1 yundrone/v1/gimbal/control（下行）](#261-yundronev1gimbalcontrol下行)
    - [2.6.2 yundrone/v1/gimbal/control/ack（回执）](#262-yundronev1gimbalcontrolack回执)
  - [2.7 镜头切换](#27-镜头切换)
    - [2.7.1 yundrone/v1/media/lens/control（下行）](#271-yundronev1medialenscontrol下行)
    - [2.7.2 yundrone/v1/media/lens/control/ack（回执）](#272-yundronev1medialenscontrolack回执)
- [3. 错误码](#3-错误码)

## 1. 总体规范

### 1.1 版本与命名

采用版本化话题：

- `yundrone/v1/...`

v1 仅支持单个无人机对象。

### 1.1.1 版本兼容策略

- v1 将长期兼容；客户端需忽略未知字段
- 若发生破坏性变更，将发布 v2，并在文档中说明迁移时间窗口

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
| `yundrone/v1/media/live/response` | 按请求 | - |

### 1.4 通用字段

所有系统返回的数据包含：

- `ts`: 毫秒时间戳（int）
- `code`: 状态码（`OK` 表示成功，其他为错误码，取值见第 3 章）

仅请求/响应类需要：

- `req_id`: 请求 ID，用于请求与回执/响应一一对应

`mission_name` 作为任务唯一标识符，系统不允许创建同名任务。

### 1.4.1 请求有效期与重复处理

- `req_id` 有效期：30 秒内有效，超过视为过期请求。
- 重复请求处理：若 `req_id` 在最近的5个请求里出现重复，系统则直接返回同一回执，不重复执行。

### 1.5 数据类型与单位

各话题字段的类型、单位与范围直接写在对应的字段表中；通用字段在 1.4 中统一约定。

### 1.6 话题权限矩阵

| 方向 | 话题 |
| --- | --- |
| 仅发布 | `yundrone/v1/drone/telemetry`<br>`yundrone/v1/drone/status`<br>`yundrone/v1/drone/alerts`<br>`yundrone/v1/mission/info` |
| 仅请求 | `yundrone/v1/mission/list/request`<br>`yundrone/v1/mission/trajectory/request`<br>`yundrone/v1/media/picture/request`<br>`yundrone/v1/media/live/request`<br>`yundrone/v1/mission/control`<br>`yundrone/v1/gimbal/control`<br>`yundrone/v1/media/lens/control` |
| 仅响应 | `yundrone/v1/mission/list/response`<br>`yundrone/v1/mission/trajectory/response`<br>`yundrone/v1/media/picture/response`<br>`yundrone/v1/media/live/response`<br>`yundrone/v1/mission/control/ack`<br>`yundrone/v1/gimbal/control/ack`<br>`yundrone/v1/media/lens/control/ack` |

### 1.7 在线状态与保活

在线状态由 `yundrone/v1/drone/status` 的 `flight_mode` 反映；当设备离线时发布 `flight_mode = -1`。

## 2. 话题与载荷

### 2.1 无人机遥测与状态

#### 2.1.1 `yundrone/v1/drone/telemetry`（发布）

包含电量 + 姿态/位置（坐标系：ENU， 参考ROS世界坐标系）。

字段：

| 字段 | 类型 | 单位/范围 | 说明 |
| --- | --- | --- | --- |
| `ts` | int | ms | 毫秒时间戳 |
| `code` | string | - | `OK` 或错误码 |
| `battery.percent` | int | 0–100 | 电量百分比 |
| `pose.position.x` | number | m | 位置 X |
| `pose.position.y` | number | m | 位置 Y |
| `pose.position.z` | number | m | 位置 Z |
| `pose.attitude.euler_deg.roll` | number | deg | 横滚 |
| `pose.attitude.euler_deg.pitch` | number | deg | 俯仰 |
| `pose.attitude.euler_deg.yaw` | number | deg | 航向 |
| `pose.attitude.quaternion.x` | number | - | 四元数 |
| `pose.attitude.quaternion.y` | number | - | 四元数 |
| `pose.attitude.quaternion.z` | number | - | 四元数 |
| `pose.attitude.quaternion.w` | number | - | 四元数 |

```json
{
  "ts": 1736150000123,
  "code": "OK",
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

字段：

| 字段 | 类型 | 单位/范围 | 说明 |
| --- | --- | --- | --- |
| `ts` | int | ms | 毫秒时间戳 |
| `code` | string | - | `OK` 或错误码 |
| `flight_mode` | int | -1/0/1 | 飞行状态 |

```json
{
  "ts": 1736150000123,
  "code": "OK",
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

字段：

| 字段 | 类型 | 单位/范围 | 说明 |
| --- | --- | --- | --- |
| `ts` | int | ms | 毫秒时间戳 |
| `code` | string | - | `OK` 或错误码 |
| `battery_low` | bool | - | 电量告警 |
| `obstacles[].direction_deg` | number | deg | 方向角 |
| `obstacles[].distance_m` | number | m | 距离 |

```json
{
  "ts": 1736150000123,
  "code": "OK",
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
- `direction_deg` 以 ENU 的 X 轴正方向为 0°

### 2.3 任务信息与任务列表

#### 2.3.1 `yundrone/v1/mission/info`（发布）

当前执行任务的状态。

字段：

| 字段 | 类型 | 单位/范围 | 说明 |
| --- | --- | --- | --- |
| `ts` | int | ms | 毫秒时间戳 |
| `code` | string | - | `OK` 或错误码 |
| `mission_name` | string \| null | - | 任务名 |
| `progress` | object \| null | - | 进度信息 |
| `progress.current_index` | int | >=0 | 当前索引 |
| `progress.total` | int | >0 | 任务总点数 |
| `progress.percent` | int | 0–100 | 进度 |

```json
{
  "ts": 1736150000123,
  "code": "OK",
  "mission_name": "warehouse_sweep",
  "progress": {
    "current_index": 12,
    "total": 40,
    "percent": 30
  }
}
```

说明：

- `current_index` 从 0 开始
- `percent` 为整数（0–100）
- 无任务执行时返回 `mission_name: null` 且 `progress: null`

空闲态示例：

```json
{
  "ts": 1736150000123,
  "code": "OK",
  "mission_name": null,
  "progress": null
}
```

#### 2.3.2 任务列表请求/响应

- 请求：`yundrone/v1/mission/list/request`
- 响应：`yundrone/v1/mission/list/response`

请求：

字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `req_id` | string | 是 | 请求 ID |
| `ts` | int | 是 | 毫秒时间戳 |
| `action` | string | 是 | 固定为 `list` |

```json
{
  "req_id": "req-8b7f",
  "ts": 1736150000123,
  "action": "list"
}
```

响应（任务名列表）：

字段：

| 字段 | 类型 | 单位/范围 | 说明 |
| --- | --- | --- | --- |
| `req_id` | string | - | 请求 ID |
| `ts` | int | ms | 毫秒时间戳 |
| `code` | string | - | `OK` 或错误码 |
| `missions[].mission_name` | string | - | 任务名 |

```json
{
  "req_id": "req-8b7f",
  "ts": 1736150000456,
  "code": "OK",
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
  "code": "ERR_MISSION_BAD_REQUEST"
}
```

#### 2.3.3 单个任务轨迹请求/响应

用于获取某个任务的完整轨迹数据，字段与当前源码一致（v1），参考 `apps/frontend/public/trajectories/default_trajectory.json`，不含点云坐标转换。

- 请求：`yundrone/v1/mission/trajectory/request`
- 响应：`yundrone/v1/mission/trajectory/response`

请求：

字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `req_id` | string | 是 | 请求 ID |
| `ts` | int | 是 | 毫秒时间戳 |
| `action` | string | 是 | 固定为 `get` |
| `mission_name` | string | 是 | 任务名 |

```json
{
  "req_id": "req-3c9a",
  "ts": 1736150000123,
  "action": "get",
  "mission_name": "default_trajectory"
}
```

响应（示意）：

字段：

| 字段 | 类型 | 单位/范围 | 说明 |
| --- | --- | --- | --- |
| `req_id` | string | - | 请求 ID |
| `ts` | int | ms | 毫秒时间戳 |
| `code` | string | - | `OK` 或错误码 |
| `mission_name` | string | - | 任务名 |
| `trajectory.name` | string | - | 轨迹名 |
| `trajectory.createdAt` | string | ISO 8601 (UTC) | 创建时间 |
| `trajectory.waypoints[].x` | number | m | X |
| `trajectory.waypoints[].y` | number | m | Y |
| `trajectory.waypoints[].z` | number | m | Z |
| `trajectory.waypoints[].yaw` | number | deg | 航向 |
| `trajectory.waypoints[].takePhoto` | bool | - | 拍照 |

```json
{
  "req_id": "req-3c9a",
  "ts": 1736150000456,
  "code": "OK",
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
  "code": "ERR_MISSION_NOT_FOUND"
}
```

### 2.4 媒体

#### 2.4.1 直播流请求/响应

- 请求：`yundrone/v1/media/live/request`
- 响应：`yundrone/v1/media/live/response`

直播流格式：HLS（`.m3u8`）/ RTMP 播放地址。
`stream_type` 枚举：`visible`（可见光）、`thermal`（热成像）。
`hls_url` 与 `rtmp_url` 同时存在或同时为空。

请求示例：

字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `req_id` | string | 是 | 请求 ID |
| `ts` | int | 是 | 毫秒时间戳 |
| `action` | string | 是 | 固定为 `get` |

```json
{
  "req_id": "req-3e21",
  "ts": 1736150000123,
  "action": "get"
}
```

说明：请求一次响应一次。

响应示例：

字段：

| 字段 | 类型 | 单位/范围 | 说明 |
| --- | --- | --- | --- |
| `req_id` | string | - | 请求 ID |
| `ts` | int | ms | 毫秒时间戳 |
| `code` | string | - | `OK` 或错误码 |
| `stream_type` | string \| null | visible/thermal | 直播类型 |
| `hls_url` | string \| null | - | HLS 播放地址 |
| `rtmp_url` | string \| null | - | RTMP 播放地址 |

```json
{
  "req_id": "req-3e21",
  "ts": 1736150000456,
  "code": "OK",
  "stream_type": "visible",
  "hls_url": "http://.../live/stream.m3u8",
  "rtmp_url": "rtmp://.../live/stream"
}
```

错误响应示例：

```json
{
  "req_id": "req-3e21",
  "ts": 1736150000456,
  "code": "ERR_MEDIA_LIVE_NOT_READY",
  "stream_type": null,
  "hls_url": null,
  "rtmp_url": null
}
```

#### 2.4.2 图片请求/响应

- 请求：`yundrone/v1/media/picture/request`
- 响应：`yundrone/v1/media/picture/response`

列表请求（时间范围）：

字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `req_id` | string | 是 | 请求 ID |
| `ts` | int | 是 | 毫秒时间戳 |
| `action` | string | 是 | 固定为 `list` |
| `since_ts` | int | 是 | 起始时间戳 |
| `until_ts` | int | 是 | 结束时间戳 |

```json
{
  "req_id": "req-1d6c",
  "ts": 1736150000123,
  "action": "list",
  "since_ts": 1736150000000,
  "until_ts": 1736153600000
}
```

注意：返回数据最多展示20个条目，对于用户请求的时间范围内大于20条目的，则返回未展示的条目以及第21条的时间戳信息(`next_since_ts`)。

响应列表（图片地址）：

字段：

| 字段 | 类型 | 单位/范围 | 说明 |
| --- | --- | --- | --- |
| `req_id` | string | - | 请求 ID |
| `ts` | int | ms | 毫秒时间戳 |
| `code` | string | - | `OK` 或错误码 |
| `items[].id` | int | - | 图片 ID |
| `items[].name` | string | - | 文件名 |
| `items[].ts` | int | ms | 图片时间戳 |
| `items[].url` | string | - | 原图地址 |
| `remaining_count` | int | >=0 | 剩余数量 |
| `next_since_ts` | int | ms | 下一次起始 |

```json
{
  "req_id": "req-1d6c",
  "ts": 1736150000456,
  "code": "OK",
  "items": [
    {"id": 12, "name": "img_001.jpg", "ts": 1736150000123, "url": "http://.../img_001.jpg"},
    {"id": 13, "name": "img_002.jpg", "ts": 1736150001123, "url": "http://.../img_002.jpg"},
    {"id": 14, "name": "img_003.jpg", "ts": 1736150002123, "url": "http://.../img_003.jpg"}
  ],
  "remaining_count": 42,
  "next_since_ts": 1736150003123
}
```

说明：

- 服务端单次最多返回 20 条
- `since_ts` / `until_ts` 为开区间
- `items` 按 `ts` 升序返回
- `remaining_count` 表示本次时间范围内未返回的剩余数量
- `next_since_ts` 表示未返回图片中的最小时间戳（用于下一次分页请求的 `since_ts`）
- 若 `items` 为空，`remaining_count` 为 0，`next_since_ts` 为 null

错误响应示例：

```json
{
  "req_id": "req-1d6c",
  "ts": 1736150000456,
  "code": "ERR_MEDIA_BAD_REQUEST"
}
```

请求单图：

字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `req_id` | string | 是 | 请求 ID |
| `ts` | int | 是 | 毫秒时间戳 |
| `action` | string | 是 | 固定为 `get` |
| `id` | int | 是 | 图片 ID |

```json
{"req_id": "req-4f20", "ts": 1736150000123, "action": "get", "id": 12}
```

响应单图：

字段：

| 字段 | 类型 | 单位/范围 | 说明 |
| --- | --- | --- | --- |
| `req_id` | string | - | 请求 ID |
| `ts` | int | ms | 毫秒时间戳 |
| `code` | string | - | `OK` 或错误码 |
| `url` | string | - | 原图地址 |

```json
{"req_id": "req-4f20", "ts": 1736150000456, "code": "OK", "url": "http://.../img_001.jpg"}
```

错误响应示例：

```json
{"req_id": "req-4f20", "ts": 1736150000456, "code": "ERR_MEDIA_NOT_FOUND"}
```

### 2.5 任务控制

#### 2.5.1 `yundrone/v1/mission/control`（下行）

所有控制指令必须有回执。

请求示例：

字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `req_id` | string | 是 | 请求 ID |
| `ts` | int | 是 | 毫秒时间戳 |
| `action` | string | 是 | `start` / `pause` / `resume` / `return_home` |
| `mission_name` | string | 是 | 任务名 |

```json
{ "req_id": "req-a102", "ts": 1736150000123, "action": "start", "mission_name": "default_trajectory" }
{ "req_id": "req-b7e1", "ts": 1736150000123, "action": "pause", "mission_name": "default_trajectory" }
{ "req_id": "req-19df", "ts": 1736150000123, "action": "resume", "mission_name": "default_trajectory" }
{ "req_id": "req-5c44", "ts": 1736150000123, "action": "return_home", "mission_name": "default_trajectory" }
```

#### 2.5.2 `yundrone/v1/mission/control/ack`（回执）

统一回执结构：

字段：

| 字段 | 类型 | 单位/范围 | 说明 |
| --- | --- | --- | --- |
| `req_id` | string | - | 请求 ID |
| `ts` | int | ms | 毫秒时间戳 |
| `code` | string | - | `OK` 或错误码 |

```json
{
  "req_id": "req-a102",
  "ts": 1736150000456,
  "code": "OK"
}
```

错误码：

| 错误码 | 含义 |
| --- | --- |
| `OK` | 成功 |
| `ERR_MISSION_BAD_REQUEST` | 请求格式错误 |
| `ERR_MISSION_NOT_FOUND` | 未指定或找不到任务 |
| `ERR_MISSION_ALREADY_RUNNING` | 已在执行中 |
| `ERR_MISSION_NOT_STARTED` | 当前未执行任务 |
| `ERR_MISSION_INVALID_STATE` | 状态不允许该操作 |

动作与回执：

| action | 成功 | 失败 |
| --- | --- | --- |
| `start` | `OK` | `ERR_MISSION_NOT_FOUND` / `ERR_MISSION_ALREADY_RUNNING` |
| `pause` | `OK` | `ERR_MISSION_NOT_STARTED` |
| `resume` | `OK` | `ERR_MISSION_NOT_STARTED` |
| `return_home` | `OK` | `ERR_MISSION_INVALID_STATE` |

若任务未开始就发送 `pause` / `resume` / `return_home`，返回 `ERR_MISSION_NOT_STARTED`。

### 2.6 云台控制

当前仅支持俯仰回中与俯仰向下。

#### 2.6.1 `yundrone/v1/gimbal/control`（下行）

请求示例：

字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `req_id` | string | 是 | 请求 ID |
| `ts` | int | 是 | 毫秒时间戳 |
| `action` | string | 是 | `pitch_center` / `pitch_down` |

```json
{ "req_id": "req-4a9c", "ts": 1736150000123, "action": "pitch_center" }
{ "req_id": "req-8d1b", "ts": 1736150000123, "action": "pitch_down" }
```

#### 2.6.2 `yundrone/v1/gimbal/control/ack`（回执）

字段：

| 字段 | 类型 | 单位/范围 | 说明 |
| --- | --- | --- | --- |
| `req_id` | string | - | 请求 ID |
| `ts` | int | ms | 毫秒时间戳 |
| `code` | string | - | `OK` 或错误码 |

```json
{
  "req_id": "req-4a9c",
  "ts": 1736150000456,
  "code": "OK"
}
```

错误码：`OK`、`ERR_GIMBAL_BAD_REQUEST`、`ERR_GIMBAL_INVALID_STATE`。

### 2.7 镜头切换

镜头类型枚举：`thermal`（红外）、`wide`（广角）、`zoom`（变焦）。

#### 2.7.1 `yundrone/v1/media/lens/control`（下行）

请求示例：

字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `req_id` | string | 是 | 请求 ID |
| `ts` | int | 是 | 毫秒时间戳 |
| `action` | string | 是 | 固定为 `switch` |
| `lens` | string | 是 | `thermal` / `wide` / `zoom` |

```json
{ "req_id": "req-61d3", "ts": 1736150000123, "action": "switch", "lens": "thermal" }
{ "req_id": "req-2a8f", "ts": 1736150000123, "action": "switch", "lens": "wide" }
{ "req_id": "req-9c10", "ts": 1736150000123, "action": "switch", "lens": "zoom" }
```

#### 2.7.2 `yundrone/v1/media/lens/control/ack`（回执）

字段：

| 字段 | 类型 | 单位/范围 | 说明 |
| --- | --- | --- | --- |
| `req_id` | string | - | 请求 ID |
| `ts` | int | ms | 毫秒时间戳 |
| `code` | string | - | `OK` 或错误码 |

```json
{
  "req_id": "req-61d3",
  "ts": 1736150000456,
  "code": "OK"
}
```

错误码：`OK`、`ERR_LENS_BAD_REQUEST`、`ERR_LENS_INVALID_STATE`。

## 3. 错误码

错误码统一采用 `ERR_{DOMAIN}_XXX` 命名，便于快速识别来源模块。

| 错误码 | 含义 |
| --- | --- |
| `OK` | 成功 |
| `ERR_MISSION_BAD_REQUEST` | 任务请求格式错误 |
| `ERR_MISSION_NOT_FOUND` | 任务不存在 |
| `ERR_MISSION_ALREADY_RUNNING` | 任务已在执行中 |
| `ERR_MISSION_NOT_STARTED` | 任务未开始 |
| `ERR_MISSION_INVALID_STATE` | 任务状态不允许该操作 |
| `ERR_MEDIA_BAD_REQUEST` | 媒体请求格式错误 |
| `ERR_MEDIA_NOT_FOUND` | 媒体资源不存在 |
| `ERR_MEDIA_LIVE_NOT_READY` | 直播未就绪 |
| `ERR_GIMBAL_BAD_REQUEST` | 云台请求格式错误 |
| `ERR_GIMBAL_INVALID_STATE` | 云台状态不允许该操作 |
| `ERR_LENS_BAD_REQUEST` | 镜头请求格式错误 |
| `ERR_LENS_INVALID_STATE` | 镜头状态不允许该操作 |
