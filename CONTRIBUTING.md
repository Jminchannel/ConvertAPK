# 贡献指南

感谢你愿意参与 ConvertAPK。这个项目涉及用户端、管理端、构建端和桌面端，提交改动前请先确认影响范围，尽量保持变更小而清晰。

## 适合贡献的方向

- 修复 Web-to-APK/AAB 构建失败问题。
- 改进上传、配置、日志、下载等用户体验。
- 补充 Docker、Ubuntu、Windows、桌面端部署文档。
- 增强合法授权、路径校验、文件校验和敏感信息保护。
- 增加常见框架的构建兼容性，例如 Vite、Vue、React、PWA、静态 HTML。
- 优化管理端任务列表、统计看板、反馈和版本发布流程。

## 开发前准备

1. Fork 仓库并创建独立分支。
2. 阅读 README 和相关 `docs/` 文档。
3. 根据改动范围启动对应子系统。
4. 不要提交 `.env`、日志、运行态数据、构建产物、证书、Token、keystore。

## 本地验证建议

用户端前端：

```bash
cd web/frontend
npm install
npm run build
```

用户端后端：

```bash
cd web/backend
pip install -r requirements.txt
python -m py_compile main.py builder.py local_builder.py models.py admin_client.py
```

管理端前端：

```bash
cd admin/frontend
npm install
npm run build
```

管理端后端：

```bash
cd admin/backend
pip install -r requirements.txt
python -m py_compile app/main.py
```

如果改动了 `apk-worker/scripts/` 或 Android 模板，请重新构建 `apk-builder:latest` 并至少跑一次真实构建任务。

## Pull Request 要求

- 描述本次改动解决了什么问题。
- 说明影响范围，例如用户端前端、用户端后端、管理端、构建端或桌面端。
- 列出已执行的验证命令。
- 如果涉及界面，请附截图或录屏。
- 如果涉及安全、上传、下载或鉴权，请说明风险控制点。

## 合规边界

本项目只适用于合法授权的学习、研究、内部工具和应用打包场景。请不要提交任何支持钓鱼、盗版、恶意软件、绕过平台审核或侵犯第三方权益的功能。

## 贡献许可

除非另有书面约定，你提交到本仓库的贡献将按照仓库根目录 [LICENSE](LICENSE) 中的 `ConvertAPK Source-Available Non-Commercial License v1.0` 授权。提交贡献前，请确认你有权提交相关代码、文档或素材。
