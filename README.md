# drone3plot

无人机任务规划与点云三维预览平台，包含 Web 前端、Flask 控制台与图片浏览器三大板块。

## 目录结构
- `apps/frontend/`：React + Vite 前端
- `server/`：Flask 主服务（挂载 dashboard 与 mediaweb）
- `apps/dashboard/`：无人机连接与控制台页面
- `apps/mediaweb/`：图片库页面（SQLite + MinIO）
- `doc/`：技术文档与协议说明
- `videostream/`：直播相关配置与下载脚本

## 开发模式
```bash
pnpm --dir apps/frontend install
uv sync
uv pip install -e ./thirdparty/pydjimqtt

uv run python main.py --log-level info
pnpm --dir apps/frontend dev
```

前端开发地址：`http://localhost:5173`  
后端服务地址：`http://127.0.0.1:5050`

## 生产构建
```bash
pnpm --dir apps/frontend build
uv run python main.py --log-level info
```

## 常用脚本
```bash
pnpm --dir apps/frontend analyze:pointcloud
pnpm --dir apps/frontend analyze:las-color
```

## 文档
- 使用说明：`doc/usage.md`
- MQTT 协议：`doc/api/mqtt_spec.md`
- 点云流程：`doc/pointcloud_pipeline.md`
- 状态机：`doc/mission_state_machine.md`、`doc/drc_state_machine.md`
