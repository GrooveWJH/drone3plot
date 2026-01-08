# 使用说明

本文档描述日常开发与部署的推荐流程，默认在 macOS/Linux 环境下操作。

## 依赖准备
- Node.js 18+、pnpm
- Python 3.12、uv

可选依赖：
- MQTT Broker（默认 `127.0.0.1:1883`）
- MinIO（用于图片库访问）

## 配置入口
主要配置集中在 `server/config.py`：
- `DashboardConfig`：无人机 MQTT、视频流、SLAM 话题等默认值
- `ServerConfig`：Flask 监听地址与端口
- `MediaConfig`：SQLite 路径、MinIO 连接信息

如果需要使用真实数据，请先更新 `MediaConfig.db_path` 与 MinIO 相关字段。

## 开发模式
1. 安装依赖
```bash
pnpm --dir apps/frontend install
uv sync
uv pip install -e ./thirdparty/pydjimqtt
```

2. 启动后端
```bash
uv run python main.py --log-level info
```

3. 启动前端
```bash
pnpm --dir apps/frontend dev
```

4. 访问
- 前端：`http://localhost:5173`
- 后端：`http://127.0.0.1:5050`

## 生产构建
```bash
pnpm --dir apps/frontend build
uv run python main.py --log-level info
```

构建产物位于 `apps/frontend/dist/`，由 Flask 自动托管。

## 图片库（mediaweb）
图片库挂载在 `/media/` 路径，依赖以下配置：
- `MediaConfig.db_path`：SQLite 数据库路径
- `MediaConfig.storage_*`：MinIO 或兼容对象存储配置

如果数据库不存在或表缺失，页面会提示未找到数据库。

## 直播（videostream）
`videostream/` 提供 mediamtx 下载脚本与示例配置：
```bash
./videostream/get-mediamtx.sh
```

按需修改 `videostream/mediamtx.yml` 并启动 mediamtx 服务。

## 日志等级
运行参数 `--log-level` 支持：`debug | info | warning | error`。  
非 `debug` 时会压制部分 Flask 请求日志。
