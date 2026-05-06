# ConvertAPK-EXE

ConvertAPK-EXE 是一套把 Web 应用打包为 Android APK/AAB 与桌面安装包的完整工具链，包含用户端、管理端、构建端和 Electron/Tauri 桌面端。用户可以上传 ZIP 或 HTML，配置应用名称、包名、图标、版本、签名等信息，然后通过本地或 Docker 构建器生成产物。

示例视频：[Bilibili BV1XakbBGE16](https://www.bilibili.com/video/BV1XakbBGE16/)

## 功能特性

- 上传 Web 项目 ZIP 或单页 HTML，一键创建构建任务。
- 支持配置应用名、包名、版本号、图标、签名、启动页、状态栏、横竖屏等参数。
- 支持 APK/AAB 构建、任务队列、构建日志、失败诊断和产物下载。
- 用户端后端可在 Docker 模式下调用宿主机 Docker 中的 `apk-builder` 镜像完成 Android 构建。
- 管理端支持任务看板、公告、反馈、版本发布、文件管理和概览统计。
- Electron/Tauri 桌面端可启动本地后端并加载用户端界面，适合 Windows 本地使用。

## 技术栈

- 用户端前端：Vue 3 + Vite
- 用户端后端：FastAPI + Pydantic
- 管理端前端：Vue 3 + Vite
- 管理端后端：FastAPI + SQLAlchemy + PostgreSQL
- 构建端：Docker + Node.js + JDK + Android SDK + Capacitor
- 桌面端：Electron + electron-builder + Tauri

## 目录结构

```text
.
├── web/                       用户端前后端
│   ├── frontend/              用户端 Vue 前端
│   └── backend/               用户端 FastAPI 后端
├── admin/                     管理端前后端
│   ├── frontend/              管理端 Vue 前端
│   └── backend/               管理端 FastAPI 后端
├── apk-worker/                Android/桌面构建镜像与构建脚本
├── desktop/                   Electron 桌面壳
├── templates/                 Android 模板工程与资源
├── docs/                      额外部署文档
├── scripts/                   本地联调脚本
├── data/                      运行时数据，默认不提交
├── docker-compose.yml         Docker 一体化编排
└── docker-compose.windows.yml Windows 数据卷路径覆盖
```

## 服务端口

| 服务 | 本地开发地址 | Docker 默认地址 |
| --- | --- | --- |
| 用户端前端 | `http://localhost:3000` | `http://localhost:8080` |
| 用户端后端 | `http://localhost:8000` | `http://localhost:8000` |
| 管理端前端 | 本机开发访问 | 生产环境不要公网暴露 |
| 管理端后端 | 本机开发访问 | 生产环境不要公网暴露 |

## 环境要求

Docker 部署推荐：

- Linux：Ubuntu 22.04/24.04 或其他支持 Docker Compose 的发行版。
- Windows：Windows 10/11 + Docker Desktop，建议使用 WSL2 后端。
- CPU/内存：最低 2C/4G，推荐 4C/8G 以上。
- 磁盘：建议预留 20GB 以上，首次构建会下载 Gradle、Node、Android 依赖。

本地开发推荐：

- Python 3.10+
- Node.js 18+
- Docker 与 Docker Compose
- 如使用本地构建模式，需要配置 JDK、Android SDK、Node.js 等工具链。

## Docker 一体化部署

### 1. 获取代码

```bash
git clone <your-repo-url>
cd ConvertAPK-EXE
```

### 2. 准备环境变量

管理端后端在 Compose 中会读取 `admin/backend/.env`，首次部署可以从示例文件复制，确保 `env_file` 文件存在：

```bash
cp admin/backend/.env.example admin/backend/.env
```

注意：当前 `docker-compose.yml` 同时在 `environment` 中写入了默认测试值，Compose 的 `environment` 会覆盖 `admin/backend/.env`。生产环境请直接修改 `docker-compose.yml` 中的这些值，或改成 `${变量名}` 后放到根目录 `.env` 中统一管理：

```dotenv
ADMIN_USER=admin
ADMIN_PASS=请改成强密码
JWT_SECRET=请改成长随机字符串
CLIENT_TOKEN=请改成长随机字符串
POSTGRES_PASSWORD=请改成数据库强密码
```

同时需要同步修改：

- `admin-db` 的 `POSTGRES_PASSWORD`
- `admin-backend` 的 `DATABASE_URL` 数据库密码
- `admin-backend` 的 `CLIENT_TOKEN`
- `backend` 的 `ADMIN_CLIENT_TOKEN`

其中 `ADMIN_CLIENT_TOKEN` 与 `CLIENT_TOKEN` 必须完全一致。默认 `docker-compose.yml` 中两者都是 `client-secret`，只适合本地测试。

如需 GitHub 登录，Docker Compose 默认会读取根目录 `.env` 参与变量替换。可以参考 `.env.local.example` 创建根目录 `.env`：

```bash
cp .env.local.example .env
```

然后按实际域名配置：

```dotenv
AUTH_GITHUB_CLIENT_ID=your_github_oauth_client_id
AUTH_GITHUB_CLIENT_SECRET=your_github_oauth_client_secret
AUTH_GITHUB_CALLBACK_URL=https://example.com/api/auth/github/callback
AUTH_DEFAULT_RETURN_URL=https://example.com/
AUTH_REDIRECT_ALLOWED_ORIGINS=https://example.com
```

### 3. 准备数据目录

Linux 默认数据卷绑定到 `/data`：

```bash
sudo mkdir -p /data/convertapk/gradle-cache
sudo mkdir -p /data/convertapk-admin/db
sudo mkdir -p /data/convertapk-admin/storage
```

Windows 使用 `docker-compose.windows.yml` 覆盖数据卷路径，当前配置指向：

```text
D:/Apps/ConvertAPK-EXE/data
```

如果项目不在这个目录，请先修改 `docker-compose.windows.yml` 中的 `device` 路径。

### 4. 构建构建器镜像

后端在 Docker 模式下会通过宿主机 Docker 调用 `apk-builder:latest`。首次部署或构建镜像变更后，需要先构建：

```bash
docker compose --profile builder build apk-builder
```

如果需要构建 Electron 桌面安装包，也构建桌面构建器：

```bash
docker compose --profile builder build desktop-builder
```

### 5. 启动服务

Linux：

```bash
docker compose up -d --build
```

Windows：

```powershell
docker compose -f docker-compose.yml -f docker-compose.windows.yml up -d --build
```

查看服务状态：

```bash
docker compose ps
```

查看日志：

```bash
docker compose logs -f backend
docker compose logs -f admin-backend
```

生产部署建议将 `admin-backend` 与 `admin-frontend` 的 `ports` 绑定到 `127.0.0.1`，或删除对外 `ports` 映射，仅保留容器内服务通信。需要远程管理时，再通过 VPN、SSH 隧道、堡垒机或带 IP 白名单的内网反向代理进入。

### 6. 访问系统

- 用户端：`http://服务器IP:8080`
- 用户端 API：`http://服务器IP:8000/docs`

管理端仅建议在内网、VPN、SSH 隧道或堡垒机环境访问，不建议直接暴露公网端口。生产部署时请限制管理端前后端端口的入站访问，或移除对外端口映射后通过内网反向代理访问。

Docker 部署时，管理端默认账号取自 `docker-compose.yml` 中的 Compose 环境变量：

```text
用户名：admin
密码：admin123
```

生产环境请务必修改默认密码、`JWT_SECRET`、`CLIENT_TOKEN` 和数据库密码。

## Ubuntu 快速部署示例

```bash
apt update
apt install -y docker.io docker-compose-plugin git
systemctl enable --now docker

git clone <your-repo-url>
cd ConvertAPK-EXE

cp admin/backend/.env.example admin/backend/.env
mkdir -p /data/convertapk/gradle-cache /data/convertapk-admin/db /data/convertapk-admin/storage

docker compose --profile builder build apk-builder
docker compose up -d --build
```

如启用防火墙：

```bash
ufw allow 8080/tcp
ufw allow 8000/tcp
```

更细的 Ubuntu 用户构建端说明见 [docs/DEPLOY_UBUNTU.md](docs/DEPLOY_UBUNTU.md)。

## 反向代理与 HTTPS

生产环境建议只对外暴露前端站点，通过 Nginx/Caddy 反代到容器端口，并启用 HTTPS。示例：

```nginx
server {
    listen 80;
    server_name example.com;

    client_max_body_size 200m;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

管理端如需远程访问，建议只允许 VPN/内网来源访问，或通过带强鉴权与 IP 白名单的独立反向代理入口访问，不要直接开放管理端容器端口到公网。

## 本地开发

### 用户端

后端：

```powershell
cd web/backend
pip install -r requirements.txt
python main.py
```

前端：

```powershell
cd web/frontend
npm install
npm run dev
```

访问：`http://localhost:3000`

### 管理端

后端：

```powershell
cd admin/backend
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --host 127.0.0.1
```

前端：

```powershell
cd admin/frontend
npm install
npm run dev
```

访问终端输出的本机开发地址，不要将管理端开发服务绑定到公网网卡。

### 桌面端

开发模式：

```powershell
cd desktop
npm install
npm run dev
```

一键启动本地后端与桌面端：

```powershell
.\scripts\dev-local.ps1
```

打包 Windows 安装包前，先构建用户端前端并准备后端产物，再执行：

```powershell
cd desktop
npm run dist
```

## 常用运维命令

升级代码并重建：

```bash
git pull
docker compose --profile builder build apk-builder
docker compose up -d --build
```

停止服务但保留数据卷：

```bash
docker compose down
```

停止服务并删除容器网络，不删除绑定目录中的数据：

```bash
docker compose down --remove-orphans
```

备份关键数据：

```bash
tar -czf convertapk-data-backup.tgz /data/convertapk /data/convertapk-admin
```

## 关键环境变量

| 变量 | 所属服务 | 说明 |
| --- | --- | --- |
| `APK_BUILDER_MODE` | 用户端后端 | 构建模式，Docker 部署使用 `docker`，Windows 本地默认 `local` |
| `APK_BUILDER_IMAGE` | 用户端后端 | APK 构建器镜像，默认 `apk-builder:latest` |
| `DESKTOP_BUILDER_IMAGE` | 用户端后端 | 桌面构建器镜像，默认 `desktop-builder:latest` |
| `APK_BUILDER_DATA_DIR` | 用户端后端 | 任务、日志、输出数据目录 |
| `APK_BUILDER_TEMPLATES_DIR` | 用户端后端 | Android 模板目录 |
| `ADMIN_API_URL` | 用户端后端 | 管理端后端地址 |
| `ADMIN_CLIENT_TOKEN` | 用户端后端 | 用户端上报管理端的客户端 Token |
| `CLIENT_TOKEN` | 管理端后端 | 管理端校验客户端上报的 Token |
| `DATABASE_URL` | 管理端后端 | PostgreSQL 连接串 |
| `ADMIN_USER` | 管理端后端 | 初始化管理员用户名 |
| `ADMIN_PASS` | 管理端后端 | 初始化管理员密码 |
| `JWT_SECRET` | 管理端后端 | 管理端 JWT 签名密钥 |
| `AUTH_GITHUB_CLIENT_ID` | 用户端后端 | GitHub OAuth Client ID |
| `AUTH_GITHUB_CLIENT_SECRET` | 用户端后端 | GitHub OAuth Client Secret |
| `OPENROUTER_API_KEY` | 用户端后端 | 构建失败诊断使用的 OpenRouter Key，可选 |

## 常见问题

### 构建任务提示找不到 Docker

确认宿主机已安装 Docker，且 `backend` 服务已挂载 `/var/run/docker.sock`。当前 `docker-compose.yml` 已包含该挂载。

### 第一次构建很慢

首次构建会下载 npm、Gradle、Android 依赖。Compose 已将 Gradle 缓存挂载到 `convertapk-gradle-cache`，后续构建会明显加快。

### 用户端能打开但任务无法同步到管理端

检查 `ADMIN_API_URL` 是否能从 `backend` 容器访问，并确认 `ADMIN_CLIENT_TOKEN` 与管理端的 `CLIENT_TOKEN` 完全一致。

### 管理端无法登录

检查 `admin-backend` 日志，确认数据库已启动且 `ADMIN_USER`、`ADMIN_PASS` 配置正确。首次启动会自动创建管理员账号。

### 上传大文件失败

Docker 前端 Nginx 默认 `client_max_body_size` 为 `200m`。如需上传更大 ZIP，请同步调整 `web/frontend/nginx.conf` 和外层反向代理的上传限制。

### Windows 数据目录没有生效

确认启动命令包含 `-f docker-compose.yml -f docker-compose.windows.yml`，并检查 `docker-compose.windows.yml` 中的 `device` 是否为当前项目真实路径。

## 安全提醒

- 不要提交真实 `.env`、数据库密码、Token、证书、签名文件和 keystore。
- 对外部署时建议只暴露前端入口，并通过 HTTPS 反向代理访问。
- 管理端前端和后端不要直接暴露公网，建议使用防火墙、VPN、SSH 隧道或 IP 白名单限制访问。
- 下载、上传、构建产物目录属于运行态数据，升级前建议备份。
