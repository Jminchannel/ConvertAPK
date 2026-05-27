# ConvertAPK

[![Website](https://img.shields.io/badge/Website-gentsergame.com-0f766e)](https://gentsergame.com/)
[![GitHub stars](https://img.shields.io/github/stars/Jminchannel/ConvertAPK?style=social)](https://github.com/Jminchannel/ConvertAPK)
[![Docker](https://img.shields.io/badge/Docker-supported-2563eb)](#docker-快速启动)

ConvertAPK 是一套把 **Web 项目、PWA、单页 HTML** 打包成 **Android APK/AAB** 的开源工具链，也包含管理端、构建端和 Electron/Tauri 桌面端能力。它适合开发者、小团队和工具站作者快速验证自己的 Web 应用在 Android WebView/Capacitor 容器中的发布效果。

在线体验：[https://gentsergame.com/](https://gentsergame.com/)

示例视频：[Bilibili BV1XakbBGE16](https://www.bilibili.com/video/BV1XakbBGE16/)

## 适合谁

- 想把 Vite、Vue、React、PWA 或静态 HTML 项目快速打包成 Android 安装包的开发者。
- 想学习 Android 打包、签名、AAB、WebView、Capacitor 和 Docker 构建链路的人。
- 想搭建自用 Web-to-APK/AAB 工具站或内部打包平台的小团队。
- 想通过构建日志定位 Gradle、npm、资源文件、签名配置问题的项目维护者。

## 主要能力

- 上传 Web 项目 ZIP 或单页 HTML 后创建构建任务。
- 配置应用名、包名、版本号、图标、启动页、状态栏、横竖屏和签名信息。
- 支持 APK/AAB 构建、任务队列、构建日志、失败诊断和产物下载。
- 支持 Docker 构建器，后端可调用宿主机 Docker 中的 `apk-builder:latest` 镜像完成 Android 构建。
- 提供管理端任务看板、公告、反馈、版本发布、文件管理和概览统计。
- 提供 Electron/Tauri 桌面端，用于本地启动后端并加载用户端界面。

## 快速体验

访问在线站点：

```text
https://gentsergame.com/
```

推荐先上传一个你拥有完整授权的简单 Web 项目，例如 Vite/Vue/React 项目构建源码 ZIP，或一个单页 HTML 文件。创建任务后可以在页面中查看构建日志并下载 APK/AAB 产物。

## Docker 快速启动

```bash
git clone https://github.com/Jminchannel/ConvertAPK.git
cd ConvertAPK

cp admin/backend/.env.example admin/backend/.env

docker compose --profile builder build apk-builder
docker compose up -d --build
```

启动后访问：

```text
用户端：http://localhost:8080
用户端 API：http://localhost:8000/docs
```

如果需要 Windows 数据卷映射：

```bash
docker compose -f docker-compose.yml -f docker-compose.windows.yml up -d --build
```

## 本地开发

用户端后端：

```bash
cd web/backend
pip install -r requirements.txt
python main.py
```

用户端前端：

```bash
cd web/frontend
npm install
npm run dev
```

管理端后端：

```bash
cd admin/backend
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --host 127.0.0.1 --port 9001
```

管理端前端：

```bash
cd admin/frontend
npm install
npm run dev
```

桌面端：

```bash
cd desktop
npm install
npm run dev
```

也可以使用便捷脚本：

```powershell
.\scripts\dev-local.ps1
```

## 项目结构

```text
.
├── web/                       用户端前后端
│   ├── frontend/              用户端 Vue 3 + Vite 前端
│   └── backend/               用户端 FastAPI 后端
├── admin/                     管理端前后端
│   ├── frontend/              管理端 Vue 3 + Vite 前端
│   └── backend/               管理端 FastAPI + SQLAlchemy 后端
├── apk-worker/                Android/桌面构建镜像与脚本
├── desktop/                   Electron 桌面壳
├── templates/                 Android 模板工程与资源
├── docs/                      部署、接口和运营文档
├── scripts/                   本地联调脚本
├── data/                      运行时数据，默认不提交
├── docker-compose.yml         Docker 一体化编排
└── docker-compose.windows.yml Windows 数据卷路径覆盖
```

## 技术栈

- 前端：Vue 3、Vite
- 后端：FastAPI、Pydantic、SQLAlchemy
- 构建端：Docker、Node.js、JDK、Android SDK、Capacitor、Gradle
- 桌面端：Electron、Tauri
- 数据库：PostgreSQL

## 常见问题

### 第一次构建为什么很慢？

首次构建会下载 npm、Gradle 和 Android 依赖。Compose 已将 Gradle 缓存挂载到 `convertapk-gradle-cache`，后续构建会明显加快。

### 构建任务提示找不到 Docker 怎么办？

确认宿主机已安装 Docker，且后端容器能访问 `/var/run/docker.sock`。Docker 部署模式下，后端会通过宿主机 Docker 调用 `apk-builder:latest`。

### 上传 React/Vite/Vue 项目应该选什么模式？

如果 ZIP 中包含 `package.json`，通常应使用源码转换构建链路，而不是单页 HTML 模式。HTML 模式更适合已经整理好的单页 HTML 或静态页面。

### 管理端可以直接暴露到公网吗？

不建议。生产环境应只对外暴露用户端入口，管理端建议通过 VPN、SSH 隧道、堡垒机、内网反向代理或 IP 白名单访问。

## 安全与合规

本项目只适用于学习、研究、内部工具和合法授权的应用打包场景。使用者必须确保上传的代码、素材、图标、签名文件和第三方资源均拥有合法授权，并遵守所在地法律法规、应用商店规则和第三方平台服务协议。

严禁利用本项目从事以下行为：

1. 制作、打包或分发钓鱼、诈骗、木马、病毒、后门等恶意程序。
2. 伪装、仿冒他人应用、品牌、平台或官方客户端。
3. 未经授权打包、修改、破解或二次分发他人应用。
4. 收集、窃取、上传或滥用用户隐私数据。
5. 绕过应用商店、系统安全机制或平台审核规则。
6. 其他违反法律法规、公序良俗或平台协议的行为。

不要提交真实 `.env`、数据库密码、Token、证书、签名文件或 keystore。生产环境必须修改默认账号、JWT 密钥、客户端 Token 和数据库密码。

## 更多文档

- Ubuntu 部署：[docs/DEPLOY_UBUNTU.md](docs/DEPLOY_UBUNTU.md)
- GitHub 增长清单：[docs/GITHUB_GROWTH_CHECKLIST.md](docs/GITHUB_GROWTH_CHECKLIST.md)

## 参与贡献

欢迎提交问题、改进建议和 Pull Request。贡献前请阅读 [CONTRIBUTING.md](CONTRIBUTING.md)，安全问题请参考 [SECURITY.md](SECURITY.md)。

如果这个项目对你有帮助，欢迎给仓库点一个 Star，并把在线站点分享给需要 Web-to-APK/AAB 工具的开发者。

## Community

如果这个项目对你有帮助，欢迎 Star、Issue 或 Pull Request。下面的图表会自动展示仓库 Star 增长趋势，适合在 README 底部直观看到社区反馈。

[![Star History Chart](https://api.star-history.com/svg?repos=Jminchannel/ConvertAPK&type=Date)](https://www.star-history.com/#Jminchannel/ConvertAPK&Date)
