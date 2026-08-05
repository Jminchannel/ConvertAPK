# 职责边界与工程化保障设计

## 目标

在不改变用户端 API 路径、请求与响应字段、任务状态语义或既有页面交互的前提下，拆分前端集中状态逻辑和后端集中路由逻辑，并让质量校验在本地与 GitHub Actions 中一致执行。

## 范围与约束

- 只处理当前 GitHub 源码中的 `apps/web`、`workers/apk-worker`、`.github` 与关联文档。
- 不迁移到 TypeScript，不引入 Pinia、Vue Router 或新的后端框架。
- 保持 `/api/*` 路径、Pydantic 请求响应模型、`pending/processing/success/failed` 状态和桌面端启动方式兼容。
- 保持 `apps/web/backend/main.py` 的旧启动兼容入口；正式 ASGI 入口仍为 `app.main:app`。
- 不修改运行态 `data/`、构建产物、密钥或原始本地 `main` 工作区内容。

## 前端设计

`App.vue` 继续只负责创建根状态和加载 `AppShell`。`useAppState.js` 改为协调器：只组合各领域 composable，并向现有页面上下文暴露同名状态和方法。

新增的领域 composable 放在 `src/features/<feature>/composables/`：

- `build`：构建模式、应用配置、权限、签名、快速生成和创建任务。
- `uploads`：ZIP/HTML/图标/签名文件上传、大小校验、CDN 链接扫描和本地化选择。
- `tasks`：任务列表、分页、启动/取消/重试、日志、下载和桌面产物心跳。
- `auth`：登录、短信验证码、GitHub 登录、会话同步和退出。
- `ui`：主题、语言、移动端导航、弹窗、确认框、Toast 和窗口控制。
- `billing`：公告、构建额度、支付订单、捐赠和反馈。

各 composable 只依赖显式传入的共享状态或 API 模块；禁止 feature 之间直接读取另一个 feature 的内部 ref。跨功能流程由 `useAppState` 显式组装，以保持现有 `AppShell`、`BuildWorkspace`、`TaskWorkspace` 与弹窗组件不需要改写调用名称。

## 后端设计

`app/main.py` 只创建 FastAPI 应用、注册 CORS、中间件、启动钩子与 API 路由。路由按资源归入 `app/api/routes/`：

- `auth.py`：注册、密码/短信/GitHub 登录、会话与退出。
- `uploads.py`：项目、HTML、图标、签名上传与外链扫描。
- `tasks.py`：创建、查询、更新、启动、取消、重试、日志、产物下载与诊断。
- `operations.py`：队列、环境、系统、版本、GitHub 统计和 URL 探测。
- `adminhub.py`：公告、功能开关、额度、支付、更新检查和反馈。

跨路由的运行态数据、路径解析和生命周期放入 `app/core/`；任务创建、文件处理、认证、配额和支付等业务行为放入已有或新增的 `app/services/`；Pydantic 模型继续放在 `app/domain/`。路由模块只做参数校验、调用服务和返回 HTTP 响应，不直接读写全局任务字典或文件系统。

为降低迁移风险，先抽取无状态或低耦合端点并使用路由契约测试锁定路径，再逐组迁移任务链路。每一组迁移完成后，`main.py` 中对应路由必须删除，不能保留重复注册。

## 工程化设计

前端新增 ESLint（Vue 3 推荐规则）和 Vitest。优先为新拆出的 composable 写单元测试，并保留现有结构测试作为目录契约。`package.json` 提供：

- `lint`：检查 Vue/JavaScript 源码。
- `test:unit`：运行 Vitest。
- `test`：运行结构测试和单元测试。
- `check`：依次执行 lint、test 与 build。

后端继续使用标准库 `unittest`，为路由注册、服务边界和关键错误分支补充测试。GitHub Actions 工作流在推送 `main`、提交 Pull Request 与手动触发时执行：前端 `npm ci && npm run check`、后端单元测试、构建器单元测试、Docker Compose 配置解析，以及依赖审计。审计只报告高危生产依赖；无法联网的环境不得让本地验证脚本失效。

## 验收标准

1. 前端根组件不包含业务状态实现；每个拆出的 feature 至少有一个可独立运行的单元测试。
2. 后端 `main.py` 不再定义业务端点；所有已发布路由保持原路径、方法与响应模型。
3. `python -m unittest`、前端 `npm run check`、构建器测试与 Compose 配置校验通过。
4. GitHub Actions 使用与本地一致的命令，并能在干净 checkout 上执行。
5. 桌面端开发启动、Docker 后端入口和 PyInstaller 配置仍指向 `app.main:app` 或兼容入口。

## 风险控制

- 每次只迁移一类功能，先写失败的契约或单元测试，再移动实现。
- 任务、上传和下载链路涉及文件与运行态数据；迁移中统一复用现有路径约束、鉴权和状态检查，禁止为拆分引入新的绕过分支。
- 依赖审计与 lint 先在干净 checkout 验证基线，再纳入 CI，避免将既有告警误判为新回归。
