# APK Builder Docker Image
# 基于Ubuntu 22.04，包含 JDK 21 + Node 22 + Android SDK 36

FROM ubuntu:22.04

LABEL maintainer="APK Converter"
LABEL description="Docker image for building APK from React/Web apps using Capacitor"

# 防止交互式提示
ENV DEBIAN_FRONTEND=noninteractive

# 设置时区
ENV TZ=Asia/Shanghai

# ============================================
# 基础工具安装
# ============================================
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    unzip \
    zip \
    git \
    dos2unix \
    software-properties-common \
    ca-certificates \
    gnupg \
    tzdata \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
    && echo $TZ > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

# ============================================
# 安装 JDK 21
# ============================================
RUN apt-get update && apt-get install -y openjdk-21-jdk \
    && rm -rf /var/lib/apt/lists/*

ENV JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64
ENV PATH=$JAVA_HOME/bin:$PATH

# ============================================
# 安装 Node.js 22
# ============================================
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# 验证Node版本
RUN node --version && npm --version

# ============================================
# 安装 Android SDK
# ============================================
ENV ANDROID_HOME=/opt/android-sdk
ENV ANDROID_SDK_ROOT=$ANDROID_HOME
ENV PATH=$PATH:$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools:$ANDROID_HOME/build-tools/36.0.0

# 创建Android SDK目录
RUN mkdir -p $ANDROID_HOME/cmdline-tools

# 下载并安装Android Command Line Tools
RUN cd /tmp \
    && wget -q https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip -O cmdline-tools.zip \
    && unzip -q cmdline-tools.zip \
    && mv cmdline-tools $ANDROID_HOME/cmdline-tools/latest \
    && rm cmdline-tools.zip

# 接受所有许可证
RUN yes | sdkmanager --licenses

# 安装必要的SDK组件
RUN sdkmanager \
    "platform-tools" \
    "platforms;android-35" \
    "build-tools;36.0.0" \
    "build-tools;35.0.0"

# ============================================
# 配置 Gradle 目录并预下载 Gradle
# ============================================
ENV GRADLE_USER_HOME=/root/.gradle

# 预下载 Gradle 到备份位置（供挂载后恢复使用）
# 因为 docker -v 挂载会覆盖容器内目录，所以需要备份
ENV GRADLE_CACHE_BACKUP=/opt/gradle-cache
RUN mkdir -p $GRADLE_CACHE_BACKUP/wrapper/dists

# Gradle Wrapper 分发包下载地址候选（空格分隔，可在运行容器时覆盖）
ENV GRADLE_DIST_MIRRORS="https://downloads.gradle.org/distributions https://services.gradle.org/distributions https://mirrors.cloud.tencent.com/gradle https://mirrors.aliyun.com/gradle https://repo.huaweicloud.com/gradle"

# 预下载常用 Gradle wrapper 分发包（最佳努力：失败不阻断镜像构建）
# 注意：Gradle Wrapper 的 hash 目录是 md5(url) 的 base36，不是 md5 hex
RUN set -e; \
    prefetch_gradle() { \
      zip="$1"; \
      canonical_url="https://services.gradle.org/distributions/$zip"; \
      dist_name="${zip%.zip}"; \
      hash_dir="$(node -e "const crypto=require('crypto');const url=process.argv[1];const hex=crypto.createHash('md5').update(url).digest('hex');console.log(BigInt('0x'+hex).toString(36));" "$canonical_url")"; \
      target_dir="$GRADLE_CACHE_BACKUP/wrapper/dists/$dist_name/$hash_dir"; \
      ok_file="$target_dir/$zip.ok"; \
      if [ -f "$ok_file" ]; then \
        echo "[Gradle] cache hit: $dist_name/$hash_dir"; \
        return 0; \
      fi; \
      mkdir -p "$target_dir"; \
      tmp="/tmp/$zip"; \
      rm -f "$tmp"; \
      for base in $GRADLE_DIST_MIRRORS; do \
        url="$base/$zip"; \
        echo "[Gradle] downloading: $url"; \
        if curl -fL --connect-timeout 10 --retry 3 --retry-delay 2 -o "$tmp" "$url"; then \
          echo "[Gradle] download ok: $url"; \
          break; \
        fi; \
      done; \
      if [ ! -s "$tmp" ]; then \
        echo "[Gradle] WARNING: prefetch failed for $zip (will download during build if needed)"; \
        return 0; \
      fi; \
      mv "$tmp" "$target_dir/$zip"; \
      (cd "$target_dir" && unzip -q "$zip"); \
      touch "$ok_file"; \
      rm -f "$target_dir/$zip.lck"; \
      rm -f "$target_dir/$zip"; \
      return 0; \
    }; \
    prefetch_gradle "gradle-8.14.3-all.zip"; \
    prefetch_gradle "gradle-8.11.1-bin.zip"

# ============================================
# 创建工作目录
# ============================================
WORKDIR /workspace

# 创建必要的目录
RUN mkdir -p /workspace/input \
    /workspace/output \
    /workspace/keystore \
    /workspace/scripts

# ============================================
# 复制构建脚本
# ============================================
COPY scripts/ /workspace/scripts/

# 转换Windows换行符为Unix格式并设置执行权限
RUN dos2unix /workspace/scripts/*.sh && chmod +x /workspace/scripts/*.sh

# ============================================
# 设置环境变量
# ============================================
ENV INPUT_DIR=/workspace/input
ENV OUTPUT_DIR=/workspace/output
ENV KEYSTORE_DIR=/workspace/keystore

# 入口点
ENTRYPOINT ["/workspace/scripts/entrypoint.sh"]

