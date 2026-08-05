#!/bin/bash
# APK Builder - 快速构建脚本
# 用法: ./build.sh [APP_NAME] [PACKAGE_NAME]

echo "============================================"
echo "APK Builder - Docker Build Script"
echo "============================================"

# 设置默认值
APP_NAME=${1:-"MyApp"}
PACKAGE_NAME=${2:-"com.example.app"}

# 检查input目录
if [ ! "$(ls -A input/*.zip 2>/dev/null)" ]; then
    echo "[ERROR] 请将项目ZIP文件放入 input 目录"
    exit 1
fi

echo ""
echo "配置信息:"
echo "  App Name: $APP_NAME"
echo "  Package: $PACKAGE_NAME"
echo ""

# 导出环境变量
export APP_NAME
export PACKAGE_NAME

# 运行Docker构建
docker-compose up --build

echo ""
echo "============================================"
echo "构建完成! 请检查 output 目录"
echo "============================================"







