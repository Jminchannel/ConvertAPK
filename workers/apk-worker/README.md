# APK Worker - Docker APK 构建器

将 React/Web 应用通过 Capacitor 转换为 Android APK 的 Docker 容器。

## 环境配置

Docker 镜像包含：
- **JDK 21** - Java 开发环境
- **Node.js 22** - JavaScript 运行时
- **Android SDK 36** - Android 构建工具
- **Capacitor CLI** - Web 到原生应用转换

## 目录结构

```
workers/apk-worker/
├── Dockerfile              # Docker 镜像定义
├── docker-compose.yml      # Docker Compose 配置
├── .env.example            # 环境变量示例
├── scripts/
│   ├── entrypoint.sh       # 容器入口脚本
│   └── build.sh            # APK 构建主脚本
├── input/                  # 放置源码ZIP文件
├── output/                 # 构建输出的APK
└── keystore/               # 签名密钥（可选）
```

## 快速开始

### 1. 构建 Docker 镜像

```bash
cd workers/apk-worker
docker-compose build
```

或使用 docker 命令：

```bash
docker build -t apk-builder:latest .
```

### 2. 准备项目文件

将 React/Web 项目的 ZIP 文件放入 `input/` 目录：

```bash
cp your-react-app.zip ./input/
```

### 3. 配置环境变量

复制并编辑环境变量文件：

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```env
APP_NAME=MyApp
PACKAGE_NAME=com.example.myapp
VERSION_NAME=1.0.0
VERSION_CODE=1
KEYSTORE_PASSWORD=your_password
KEY_ALIAS=key0
KEY_PASSWORD=your_password
```

### 4. 运行构建

使用 docker-compose：

```bash
docker-compose up
```

或使用 docker run（建议挂载 `/root/.gradle` 以复用 Gradle 缓存，避免重复下载）：

```bash
docker run --rm \
  -e APP_NAME="MyApp" \
  -e PACKAGE_NAME="com.example.myapp" \
  -e VERSION_NAME="1.0.0" \
  -e VERSION_CODE="1" \
  -v $(pwd)/input:/workspace/input \
  -v $(pwd)/output:/workspace/output \
  -v $(pwd)/keystore:/workspace/keystore \
  -v gradle-cache:/root/.gradle \
  apk-builder:latest
```

### 5. 获取构建结果

构建完成后，APK 文件将在 `output/` 目录中：

```bash
ls -la output/
# MyApp-v1.0.0.apk
```

## 构建流程

构建脚本会自动执行以下步骤：

1. **解压项目** - 解压 input 目录中的 ZIP 文件
2. **安装依赖** - 运行 `npm install`
3. **构建 Web** - 运行 `npm run build`
4. **初始化 Capacitor** - 配置 Capacitor
5. **添加 Android** - 添加 Android 平台
6. **同步代码** - 运行 `npx cap sync`
7. **配置 Android** - 创建 local.properties
8. **构建 APK** - 运行 Gradle assembleRelease
9. **生成密钥** - 如果没有提供，自动生成
10. **对齐 APK** - 使用 zipalign 优化
11. **签名 APK** - 使用 apksigner 签名

## 自定义签名密钥

如果你有自己的签名密钥，将 keystore 文件放入 `keystore/` 目录并命名为 `release.keystore`：

```bash
cp your-release.keystore ./keystore/release.keystore
```

并在 `.env` 中配置相应的密码和别名。

## 手动生成密钥

如果需要手动生成密钥库：

```bash
keytool -genkeypair -v \
  -keystore release.keystore \
  -alias key0 \
  -keyalg RSA \
  -keysize 2048 \
  -validity 10000
```

## 进入容器调试

如果需要进入容器进行调试：

```bash
docker-compose run --rm apk-builder shell
```

或：

```bash
docker run -it --rm \
  -v $(pwd)/input:/workspace/input \
  -v $(pwd)/output:/workspace/output \
  -v gradle-cache:/root/.gradle \
  apk-builder:latest shell
```

## 支持的项目类型

- React (Vite)
- React (Create React App)
- Vue.js
- 其他可以构建为静态网页的前端项目

## 常见问题

### Q: 构建失败提示找不到 package.json？
A: 确保 ZIP 文件中包含 package.json，且不要嵌套太深的目录。

### Q: Gradle 构建失败？
A: 检查项目的 Node.js 版本要求是否与 Docker 环境兼容。

### Q: 签名失败？
A: 检查密钥库密码和密钥别名是否正确配置。

## 资源限制

默认配置限制内存使用为 4GB，如果构建大型项目可能需要调整：

```yaml
# docker-compose.yml
deploy:
  resources:
    limits:
      memory: 8G
```

## 技术栈

- Ubuntu 22.04
- OpenJDK 21
- Node.js 22
- Android SDK (API 35, Build Tools 36.0.0)
- Capacitor 8.x







