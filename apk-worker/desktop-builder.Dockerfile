FROM electronuserland/builder:wine

LABEL maintainer="APK Converter"
LABEL description="Docker image for building Windows Electron EXE from ZIP web apps"

USER root

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Asia/Shanghai

RUN apt-get update && apt-get install -y \
    python3 \
    ca-certificates \
    dos2unix \
    unzip \
    zip \
    git \
    tzdata \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
    && echo $TZ > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY web/backend/local_builder.py /app/web/backend/local_builder.py
COPY web/backend/env_setup.py /app/web/backend/env_setup.py
COPY templates/ /app/templates/
COPY desktop/build/icon.ico /app/desktop/build/icon.ico
COPY apk-worker/scripts/desktop-entrypoint.sh /workspace/scripts/desktop-entrypoint.sh
COPY apk-worker/scripts/desktop_build.py /workspace/scripts/desktop_build.py

RUN mkdir -p /workspace/input \
    /workspace/output \
    /workspace/keystore \
    /workspace/scripts \
    /data/npm-cache \
    /data/electron-cache \
    /data/electron-builder-cache \
    && dos2unix /workspace/scripts/desktop-entrypoint.sh \
    && chmod +x /workspace/scripts/desktop-entrypoint.sh

ENV PYTHONPATH=/app/web/backend
ENV INPUT_DIR=/workspace/input
ENV OUTPUT_DIR=/workspace/output
ENV KEYSTORE_DIR=/workspace/keystore
ENV NPM_CONFIG_CACHE=/data/npm-cache
ENV ELECTRON_CACHE=/data/electron-cache
ENV ELECTRON_BUILDER_CACHE=/data/electron-builder-cache
ENV CSC_IDENTITY_AUTO_DISCOVERY=false

ENTRYPOINT ["/workspace/scripts/desktop-entrypoint.sh"]