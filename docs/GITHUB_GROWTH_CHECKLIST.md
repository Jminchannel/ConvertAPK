# GitHub 增长与仓库包装清单

这份清单用于把 ConvertAPK 的 GitHub 仓库包装成更容易被发现、理解、试用和收藏的项目页。

## 仓库 About 建议

Description：

```text
Convert Web projects, PWA, Vue/React/Vite apps, and HTML pages into Android APK/AAB packages with Docker-based build logs and signing options.
```

Website：

```text
https://gentsergame.com/
```

Topics：

```text
android
apk
aab
webview
capacitor
pwa
vite
vue
react
docker
fastapi
electron
web-to-apk
apk-builder
app-release
```

## Social Preview 建议

GitHub 仓库设置路径：

```text
Settings -> General -> Social preview -> Edit
```

推荐尺寸：

```text
1280 x 640 px
```

推荐文案：

```text
ConvertAPK
Web projects to Android APK/AAB
Docker build logs, signing options, and app release workflow
```

画面建议：

- 左侧放 ConvertAPK 名称和一句话定位。
- 右侧放上传 ZIP、配置应用、生成 APK/AAB 的三步流程。
- 背景保持干净，避免过暗或过花。
- 使用实色背景，方便在不同社交平台展示。

## README 首屏检查

- [ ] 10 秒内能看懂项目解决什么问题。
- [ ] 首屏包含在线体验地址。
- [ ] 首屏包含适合人群。
- [ ] 包含 Star History 或其他社区反馈图表。
- [ ] 快速启动命令不超过 5 步。
- [ ] 合规提醒清楚，但不压过核心价值。
- [ ] 有常见问题，尤其是 Docker、HTML 模式、源码 ZIP 模式、管理端公网暴露。

## README 图表组件

Star History 图表：

```markdown
[![Star History Chart](https://api.star-history.com/svg?repos=Jminchannel/ConvertAPK&type=Date)](https://www.star-history.com/#Jminchannel/ConvertAPK&Date)
```

这个图表适合放在 `Community` 区块。等仓库 Star 数继续增长后，它会比静态文字更直观地展示项目热度。

## Release 发布建议

Release 标题示例：

```text
ConvertAPK v0.1.0 - Web-to-APK/AAB Docker build workflow
```

Release 描述模板：

````markdown
## Highlights

- Package authorized Web projects, PWA, Vite/Vue/React apps, or HTML pages into Android APK/AAB.
- Configure app name, package name, icon, splash screen, orientation, status bar, and signing options.
- Run Docker-based Android builds with task logs and downloadable artifacts.
- Manage tasks, announcements, feedback, releases, and overview stats from the admin panel.

## Quick Start

```bash
git clone https://github.com/Jminchannel/ConvertAPK.git
cd ConvertAPK
cp admin/backend/.env.example admin/backend/.env
docker compose --profile builder build apk-builder
docker compose up -d --build
```

## Links

- Website: https://gentsergame.com/
- Documentation: https://github.com/Jminchannel/ConvertAPK#readme
```
````

## 推广文案

中文短文案：

```text
我做了一个开源 Web-to-APK/AAB 工具 ConvertAPK，可以把授权的 Web 项目、PWA、Vite/Vue/React 项目或单页 HTML 打包成 Android APK/AAB。它支持 Docker 构建、构建日志、签名配置和管理端任务看板，适合学习 Android 发布流程或搭建内部打包工具。

在线体验：https://gentsergame.com/
GitHub：https://github.com/Jminchannel/ConvertAPK
```

英文短文案：

```text
I built ConvertAPK, an open-source Web-to-APK/AAB tool for packaging authorized Web projects, PWA, Vite/Vue/React apps, and HTML pages into Android APK/AAB packages. It includes Docker-based builds, build logs, signing options, and an admin dashboard for task management.

Website: https://gentsergame.com/
GitHub: https://github.com/Jminchannel/ConvertAPK
```

## 30 天目标

- GitHub Stars：100+
- 真实构建任务：100+
- 成功下载产物：20+
- README 到在线站点点击率：10%+
- 上传到创建任务转化率：20%+
- 构建成功率：60%+

如果访问量上升但任务创建少，优先优化首页和 README 的信任感。如果任务创建多但成功少，优先优化构建兼容性和失败诊断。
