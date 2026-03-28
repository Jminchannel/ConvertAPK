#!/bin/bash
# 桌面构建入口脚本

set -e

echo "============================================"
echo "Desktop Builder Docker Container"
echo "============================================"
echo "Node Version: $(node --version)"
echo "NPM Version: $(npm --version)"
echo "Python Version: $(python3 --version 2>&1)"
echo "Wine Version: $(wine --version 2>/dev/null || echo 'wine-unavailable')"
echo "============================================"

export APP_NAME="${APP_NAME:-MyDesktopApp}"
export PACKAGE_NAME="${PACKAGE_NAME:-com.example.desktop}"
export VERSION_NAME="${VERSION_NAME:-1.0.0}"
export VERSION_CODE="${VERSION_CODE:-1}"
export TASK_MODE="${TASK_MODE:-desktop}"
export OUTPUT_FORMAT="${OUTPUT_FORMAT:-exe}"
export DESKTOP_INSTALLER_MODE="${DESKTOP_INSTALLER_MODE:-portable}"
export INPUT_DIR="${INPUT_DIR:-/workspace/input}"
export OUTPUT_DIR="${OUTPUT_DIR:-/workspace/output}"
export KEYSTORE_DIR="${KEYSTORE_DIR:-/workspace/keystore}"
export TASK_INPUT_DIR="${TASK_INPUT_DIR:-$INPUT_DIR}"
export TASK_OUTPUT_DIR="${TASK_OUTPUT_DIR:-$OUTPUT_DIR}"
export TASK_KEYSTORE_DIR="${TASK_KEYSTORE_DIR:-$KEYSTORE_DIR}"
export NPM_CONFIG_CACHE="${NPM_CONFIG_CACHE:-/data/npm-cache}"
export ELECTRON_CACHE="${ELECTRON_CACHE:-/data/electron-cache}"
export ELECTRON_BUILDER_CACHE="${ELECTRON_BUILDER_CACHE:-/data/electron-builder-cache}"
export CSC_IDENTITY_AUTO_DISCOVERY="${CSC_IDENTITY_AUTO_DISCOVERY:-false}"
export PYTHONIOENCODING="${PYTHONIOENCODING:-utf-8}"

mkdir -p "$OUTPUT_DIR" "$NPM_CONFIG_CACHE" "$ELECTRON_CACHE" "$ELECTRON_BUILDER_CACHE"

echo ""
echo "Build Configuration:"
echo "   App Name: $APP_NAME"
echo "   Package Name: $PACKAGE_NAME"
echo "   Version: $VERSION_NAME ($VERSION_CODE)"
echo "   Installer Mode: $DESKTOP_INSTALLER_MODE"
echo "   Input Dir: $TASK_INPUT_DIR"
echo "   Output Dir: $TASK_OUTPUT_DIR"
echo "============================================"
echo ""

exec python3 /workspace/scripts/desktop_build.py
