#!/bin/bash
# APK Builder 入口脚本

set -e

echo "============================================"
echo "🚀 APK Builder Docker Container"
echo "============================================"
echo "Java Version: $(java -version 2>&1 | head -n 1)"
echo "Node Version: $(node --version)"
echo "NPM Version: $(npm --version)"
echo "Android SDK: $ANDROID_HOME"
echo "============================================"

# 检查必要的环境变量
if [ -z "$APP_NAME" ]; then
    APP_NAME="MyApp"
    echo "⚠️ APP_NAME not set, using default: $APP_NAME"
fi

if [ -z "$PACKAGE_NAME" ]; then
    PACKAGE_NAME="com.example.app"
    echo "⚠️ PACKAGE_NAME not set, using default: $PACKAGE_NAME"
fi

# 导出环境变量供子脚本使用
export APP_NAME
export PACKAGE_NAME
export VERSION_NAME=${VERSION_NAME:-"1.0.0"}
export VERSION_CODE=${VERSION_CODE:-1}
export OUTPUT_FORMAT=${OUTPUT_FORMAT:-"apk"}
export KEYSTORE_PASSWORD=${KEYSTORE_PASSWORD:-"android"}
export KEY_ALIAS=${KEY_ALIAS:-"key0"}
export KEY_PASSWORD=${KEY_PASSWORD:-"android"}

echo ""
echo "📋 Build Configuration:"
echo "   App Name: $APP_NAME"
echo "   Package Name: $PACKAGE_NAME"
echo "   Version: $VERSION_NAME ($VERSION_CODE)"
echo "   Output Format: $OUTPUT_FORMAT"
echo "============================================"
echo ""

# ============================================
# 恢复预下载的 Gradle wrapper 缓存
# 当挂载了外部目录到 /root/.gradle 时，容器内预下载的缓存会被覆盖
# 使用符号链接方式恢复，瞬间完成
# ============================================
GRADLE_CACHE_BACKUP="${GRADLE_CACHE_BACKUP:-/opt/gradle-cache}"
GRADLE_USER_HOME="${GRADLE_USER_HOME:-/root/.gradle}"
GRADLE_WRAPPER_DIR="$GRADLE_USER_HOME/wrapper/dists"

if [ -d "$GRADLE_CACHE_BACKUP/wrapper/dists" ]; then
    mkdir -p "$GRADLE_WRAPPER_DIR"
    
    # 遍历备份中的每个 Gradle 版本
    for VERSION_DIR in "$GRADLE_CACHE_BACKUP/wrapper/dists"/*; do
        if [ -d "$VERSION_DIR" ]; then
            VERSION_NAME_DIR=$(basename "$VERSION_DIR")
            TARGET_VERSION_DIR="$GRADLE_WRAPPER_DIR/$VERSION_NAME_DIR"

            # 旧逻辑会把整个版本目录链接到 /opt，导致相同版本但不同镜像(URL hash 不同)的下载写入 /opt
            # 容器重建后会丢失；这里确保版本目录为真实目录，新 hash 缓存可落在持久化的 $GRADLE_USER_HOME 中
            if [ -L "$TARGET_VERSION_DIR" ]; then
                echo "🔁 迁移 Gradle wrapper 缓存目录: $VERSION_NAME_DIR"
                rm "$TARGET_VERSION_DIR"
            fi

            mkdir -p "$TARGET_VERSION_DIR"

            # 将预下载的 hash 目录逐个链接进来（保留版本目录为真实目录）
            for HASH_DIR in "$VERSION_DIR"/*; do
                if [ -d "$HASH_DIR" ]; then
                    HASH_NAME=$(basename "$HASH_DIR")
                    TARGET_HASH_DIR="$TARGET_VERSION_DIR/$HASH_NAME"
                    if [ ! -e "$TARGET_HASH_DIR" ]; then
                        echo "🔗 链接 Gradle wrapper 缓存: $VERSION_NAME_DIR/$HASH_NAME"
                        ln -s "$HASH_DIR" "$TARGET_HASH_DIR"
                    fi
                fi
            done
        fi
    done
    echo "✅ Gradle wrapper 缓存已就绪"
fi

# 如果传入了命令，执行命令；否则执行构建脚本
if [ "$1" = "build" ] || [ -z "$1" ]; then
    exec /workspace/scripts/build.sh
elif [ "$1" = "shell" ]; then
    exec /bin/bash
else
    exec "$@"
fi




