# AGENTS.md（ConvertAPK-EXE）

本文档用于指导 AI/开发者在本仓库进行改动时，能快速理解“用户端 + 构建端 + 桌面端”的整体关系，减少误改和回归。

## 1. 项目通用编码规范（必须遵守）

### 1.1 General Coding Standards for Projects
- All comments must be in Chinese.
- When writing code, strive for best practices to avoid low-quality code.
- The generated code should be reviewed to prevent security issues and page crashes.
- Variables, functions, and methods should be named using camelCase.
- All files must be encoded in UTF-8 (without BOM).
- If Chinese comments have garbled characters and contain "??", then replace them with Chinese comments.

### 1.2 项目通用编码规范
- 所有注释必须使用中文。
- 编写代码应尽可能做到最佳实践，避免低质量代码。
- 生成的代码需审查以避免安全问题与页面崩溃。
- 变量、函数与方法优先使用小驼峰命名（camelCase）。
- Python 模块若已采用 snake_case，保持文件内风格一致，避免无意义重命名。
- 所有文件必须使用 UTF-8 编码（无 BOM）。
- 若中文注释出现乱码并包含“??”，必须替换为正常中文注释。

## 2. 仓库架构总览

- `apps/web/frontend`：用户端前端（Vue 3 + Vite），负责上传、配置、任务创建、日志查看、下载产物。
- `apps/web/backend`：用户端后端（FastAPI），负责任务管理、构建编排、环境准备、文件读写、与可选外部管理端同步。
- `apps/desktop-electron`：Electron 桌面壳，负责启动本地后端并加载用户端界面。
- `workers/apk-worker`：Docker 构建器（Node/JDK/Android SDK/Capacitor），负责实际 APK/AAB 产物生成。
- `templates/android`：Android 模板工程与资源。
- `data`：运行时数据（任务、日志、输出、缓存）。

## 3. 服务端口与访问关系

- 用户端后端：`http://localhost:8000`
- 用户端前端开发：`http://localhost:3000`
- Docker 部署默认：
- 用户前端 `8080`
- 用户后端 `8000`

关键通讯关系：
- 用户端后端可通过 `ADMIN_API_URL` + `ADMIN_CLIENT_TOKEN` 调用外部管理端客户端接口。
- 外部管理端客户端接口通过 `X-Client-Token` 鉴权。

## 4. 各子系统常见改动入口

### 4.1 用户端前端
- API 封装：`apps/web/frontend/src/api/index.js`
- 应用入口：`apps/web/frontend/src/App.vue`
- 页面壳与状态上下文：`apps/web/frontend/src/app/AppShell.vue`、`apps/web/frontend/src/app/appStateContext.js`
- 页面区域：`apps/web/frontend/src/features/build/`、`apps/web/frontend/src/features/tasks/`、`apps/web/frontend/src/features/dialogs/`
- 核心状态与业务逻辑：`apps/web/frontend/src/composables/useAppState.js`
- 公共工具：`apps/web/frontend/src/utils/appShared.js`

### 4.2 用户端后端
- 入口与路由：`apps/web/backend/app/main.py`（`main.py` 仅保留旧启动方式兼容）
- 任务/配置模型：`apps/web/backend/app/domain/models.py`
- 构建调度与队列：`apps/web/backend/app/services/builder.py`
- 本地构建实现：`apps/web/backend/app/services/local_builder.py`
- 环境准备：`apps/web/backend/app/services/env_setup.py`
- 管理端通讯：`apps/web/backend/app/services/admin_client.py`

### 4.3 构建端与桌面端
- Docker 构建镜像：`workers/apk-worker/Dockerfile`
- 构建脚本：`workers/apk-worker/scripts/`
- Electron 主进程：`apps/desktop-electron/main.js`
- Electron 预加载：`apps/desktop-electron/preload.js`

## 5. 本地开发与联调流程

### 5.1 用户端（Web）
- 后端：
- `cd apps/web/backend`
- `pip install -r requirements.txt`
- `python -m uvicorn app.main:app --reload --port 8000`
- 前端：
- `cd apps/web/frontend`
- `npm install`
- `npm run dev`

### 5.2 一体化 Docker
- 启动：`docker compose up -d --build`
- 仅构建 apk-builder 镜像：`docker compose --profile builder build apk-builder`
- Windows 数据卷映射配置：`docker-compose.windows.yml`

### 5.3 桌面端
- 开发：`cd apps/desktop-electron && npm run dev`
- 打包：`cd apps/desktop-electron && npm run dist`
- 便捷本地联调脚本：`scripts/dev-local.ps1`

## 6. 接口与数据约定（改接口时必看）

- 用户端任务接口集中在 `apps/web/backend/app/main.py`。
- 用户端任务数据包含 `client_id` 维度，改动时不得破坏隔离逻辑。
- 任务状态流转以 `pending/processing/success/failed` 为准，前后端必须一致。

## 7. 安全要求（强约束）

- 禁止提交任何真实密钥、口令、Token、数据库账号到仓库。
- `.env`、日志、调试输出中禁止泄露敏感值。
- 新增下载/文件接口必须做路径约束，防止目录穿越。
- 上传接口必须校验文件类型、后缀、大小和异常分支。
- 外部管理端鉴权逻辑（JWT / `X-Client-Token`）不可绕过。
- 对外错误信息不得直接暴露完整堆栈与敏感配置。

## 8. 禁止误改范围

默认不要改以下内容，除非任务明确要求：
- `**/node_modules/**`
- `**/dist/**`
- `build/**`
- `data/**`（运行态数据）
- 纯构建产物、临时文件、日志文件

## 9. 提交前检查清单

- 编码检查：UTF-8 无 BOM，中文注释无乱码。
- 风格检查：命名风格与文件现有风格保持一致。
- 功能回归：用户端任务创建、构建、下载链路可用。
- 外部管理端已配置时，验证任务同步、公告、反馈和版本检查可用。
- 安全检查：无硬编码密钥，无鉴权绕过，无明显路径风险。

## 10. 变更策略建议

- 先定位最小改动点，再实施最小变更。
- 变更接口时同步检查调用方，避免单边改动。
- 涉及构建链路时，优先验证 `apk/aab`、签名、日志回传、队列状态。
- 涉及 Electron 时，同时验证开发模式与打包模式。

---

当需求描述不完整时，优先先判断改动归属：
- 用户端前端
- 用户端后端
- 构建端
- 桌面端

再进入对应目录实施，避免跨系统误改。
