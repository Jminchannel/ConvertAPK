@echo off
REM APK Builder - Windows 快速构建脚本
REM 用法: build.bat [APP_NAME] [PACKAGE_NAME]

setlocal enabledelayedexpansion

echo ============================================
echo APK Builder - Docker Build Script
echo ============================================

REM 设置默认值
if "%1"=="" (
    set APP_NAME=MyApp
) else (
    set APP_NAME=%1
)

if "%2"=="" (
    set PACKAGE_NAME=com.example.app
) else (
    set PACKAGE_NAME=%2
)

REM 检查input目录是否有zip文件
if not exist "input\*.zip" (
    echo [ERROR] 请将项目ZIP文件放入 input 目录
    exit /b 1
)

echo.
echo 配置信息:
echo   App Name: %APP_NAME%
echo   Package: %PACKAGE_NAME%
echo.

REM 运行Docker构建
docker-compose up --build

echo.
echo ============================================
echo 构建完成! 请检查 output 目录
echo ============================================

pause







