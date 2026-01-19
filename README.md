# ConvertAPK-EXE

把 Web 应用（React/Vue 等）一键转换为 Android APK 的完整方案，包含：
- 用户侧 Web 控制台（上传、配置、构建、下载）
- Docker 构建器（Capacitor + Android SDK）
- 桌面端（Electron，打包本地 UI + 后端）
- 管理端（任务与存储管理）

## 功能一览
- 上传 ZIP 源码，一键生成 APK
- 自定义应用名、包名、版本号、签名信息
- 构建任务管理与状态追踪
- 后端调用宿主机 Docker 完成构建
- 可选管理端（用户/任务/存储）

## 目录结构
```
.
├── web/                 # 用户 Web 控制台（前后端）
├── apk-worker/          # Docker APK 构建器（Capacitor + Android SDK）
├── desktop/             # Electron 桌面端
├── admin/               # 管理端（前后端）
├── docs/                # 部署文档
└── docker-compose.yml   # 一键启动（Web + Admin）
```


示例
Bilibili视频：https://www.bilibili.com/video/BV1XakbBGE16/

## 技术栈
- 前端：Vue 3 + Vite
- 后端：FastAPI + Pydantic
- 构建：Docker + Capacitor + Android SDK
- 桌面端：Electron
