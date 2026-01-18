#!/bin/bash
# APK 构建主脚本

set -e

# Save build logs for debugging
mkdir -p "${OUTPUT_DIR:-/workspace/output}"
LOG_FILE="${OUTPUT_DIR:-/workspace/output}/build.log"
exec > >(tee -a "$LOG_FILE") 2>&1

# On failure, copy Gradle problems report to output
dump_debug_reports() {
    local exit_code=$?
    if [ "$exit_code" -eq 0 ]; then
        return 0
    fi
    local debug_dir="${OUTPUT_DIR:-/workspace/output}/debug"
    mkdir -p "$debug_dir"
    if [ -f "$PROJECT_DIR/build/reports/problems/problems-report.html" ]; then
        cp "$PROJECT_DIR/build/reports/problems/problems-report.html" "$debug_dir/"
    fi
    if [ -f "$PROJECT_DIR/app/build/reports/problems/problems-report.html" ]; then
        cp "$PROJECT_DIR/app/build/reports/problems/problems-report.html" "$debug_dir/"
    fi
}
trap dump_debug_reports EXIT

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查错误并退出
check_error() {
    if [ $? -ne 0 ]; then
        log_error "$1"
        exit 1
    fi
}

ensure_gradle_wrapper_dist() {
    # 目标：如果 Gradle wrapper 分发包已缓存则直接复用；否则从镜像尝试下载到缓存目录，避免每次构建重新下载
    local wrapper_props=""
    for candidate in "android/gradle/wrapper/gradle-wrapper.properties" "gradle/wrapper/gradle-wrapper.properties"; do
        if [ -f "$candidate" ]; then
            wrapper_props="$candidate"
            break
        fi
    done

    if [ -z "$wrapper_props" ]; then
        log_warning "未找到 gradle-wrapper.properties，跳过 Gradle 分发包预取"
        return 0
    fi

    local dist_url_raw
    dist_url_raw="$(grep -E '^distributionUrl=' "$wrapper_props" | head -n 1 | cut -d'=' -f2-)"
    if [ -z "$dist_url_raw" ]; then
        log_warning "未找到 distributionUrl，跳过 Gradle 分发包预取"
        return 0
    fi

    # properties 里通常是 https\\://...，需要反转义
    local dist_url="${dist_url_raw//\\:/:}"
    local zip_name
    zip_name="$(basename "$dist_url")"
    local dist_name="${zip_name%.zip}"

    local gradle_user_home="${GRADLE_USER_HOME:-/root/.gradle}"
    local hash_dir
    hash_dir="$(node -e "const crypto=require('crypto');const url=process.argv[1];const hex=crypto.createHash('md5').update(url).digest('hex');console.log(BigInt('0x'+hex).toString(36));" "$dist_url" 2>/dev/null || true)"
    if [ -z "$hash_dir" ]; then
        log_warning "计算 Gradle wrapper hash 失败，跳过预取（将由 gradlew 自行下载）"
        return 0
    fi

    local target_dir="$gradle_user_home/wrapper/dists/$dist_name/$hash_dir"
    local ok_file="$target_dir/$zip_name.ok"

    if [ -f "$ok_file" ]; then
        log_info "Gradle wrapper 分发包已缓存：$dist_name/$hash_dir"
        return 0
    fi

    mkdir -p "$target_dir"

    local tmp="/tmp/$zip_name"
    rm -f "$tmp"

    local mirrors="${GRADLE_DIST_MIRRORS:-https://downloads.gradle.org/distributions https://services.gradle.org/distributions}"
    local downloaded=false

    # 先尝试 wrapper 配置里的原始地址
    if echo "$dist_url" | grep -qE '^https?://'; then
        log_info "尝试下载 Gradle 分发包: $dist_url"
        if curl -fL --connect-timeout 10 --retry 3 --retry-delay 2 -o "$tmp" "$dist_url"; then
            downloaded=true
        fi
    fi

    # 再尝试镜像列表
    if [ "$downloaded" != "true" ]; then
        for base in $mirrors; do
            local url="$base/$zip_name"
            log_info "尝试下载 Gradle 分发包: $url"
            if curl -fL --connect-timeout 10 --retry 3 --retry-delay 2 -o "$tmp" "$url"; then
                downloaded=true
                break
            fi
        done
    fi

    if [ "$downloaded" != "true" ] || [ ! -s "$tmp" ]; then
        log_warning "Gradle 分发包预取失败，将由 gradlew 自行下载（可能较慢）"
        rm -f "$tmp"
        return 0
    fi

    mv "$tmp" "$target_dir/$zip_name"
    (cd "$target_dir" && unzip -q "$zip_name")
    touch "$ok_file"
    rm -f "$target_dir/$zip_name.lck"
    rm -f "$target_dir/$zip_name"
    log_success "Gradle 分发包已写入缓存：$dist_name/$hash_dir"
    return 0
}

# ============================================
# 调试：打印所有环境变量
# ============================================
log_info "========== 环境变量调试 =========="
log_info "OUTPUT_FORMAT 原始值: '${OUTPUT_FORMAT:-未设置}'"
log_info "APP_NAME: '${APP_NAME:-未设置}'"
log_info "PACKAGE_NAME: '${PACKAGE_NAME:-未设置}'"
log_info "=================================="

TASK_MODE=${TASK_MODE:-convert}
TASK_MODE="$(echo "$TASK_MODE" | tr '[:upper:]' '[:lower:]')"
ANDROID_DIR="android"
PROJECT_DIR="${PROJECT_DIR:-/workspace/project}"
log_info "TASK_MODE: '${TASK_MODE}'"

# ============================================
# 步骤 0: 准备工作
# ============================================
# Step 0: prepare
# ============================================
log_info "Step 0: ????..."

if [ "$TASK_MODE" = "web" ]; then
    log_info "Step 1: ?? Web ??..."
    TEMPLATE_DIR="/workspace/templates/Tubbim"
    if [ ! -d "$TEMPLATE_DIR" ]; then
        log_error "Web template not found: $TEMPLATE_DIR"
        exit 1
    fi
    rm -rf "$PROJECT_DIR"
    mkdir -p "$PROJECT_DIR"
    cp -R "$TEMPLATE_DIR"/. "$PROJECT_DIR"/
    PROJECT_ROOT="$PROJECT_DIR"
    ANDROID_DIR="."

    if [ -z "$WEB_URL" ]; then
        log_error "WEB_URL is required for web mode"
        exit 1
    fi

    PROJECT_ROOT="$PROJECT_ROOT" node << 'NODE'
const fs = require('fs');
const path = require('path');

const projectRoot = process.env.PROJECT_ROOT || process.cwd();
const appName = process.env.APP_NAME || 'MyApp';
const packageName = process.env.PACKAGE_NAME || 'com.example.app';
const versionName = process.env.VERSION_NAME || '1.0.0';
const versionCode = process.env.VERSION_CODE || '1';
const webUrl = (process.env.WEB_URL || '').trim();
const statusBarHidden = String(process.env.STATUS_BAR_HIDDEN || '').trim().toLowerCase() === 'true';
const statusBarColorRaw = String(process.env.STATUS_BAR_COLOR || 'transparent').trim().toLowerCase();
const statusBarStyle = String(process.env.STATUS_BAR_STYLE || 'light').trim().toLowerCase();
const lightStatusBarIcons = statusBarStyle === 'dark';
const statusBarBackground =
  statusBarColorRaw === '#ffffff' || statusBarColorRaw === 'white' || statusBarColorRaw === '#ffffffff'
    ? 'white'
    : 'transparent';
const doubleClickExit = String(process.env.DOUBLE_CLICK_EXIT || '').trim().toLowerCase() !== 'false';

const stringsFile = path.join(projectRoot, 'app', 'src', 'main', 'res', 'values', 'strings.xml');
if (fs.existsSync(stringsFile)) {
  let text = fs.readFileSync(stringsFile, 'utf8');
  text = text.replace(/(<string\s+name="app_name">)(.*?)(<\/string>)/, `$1${appName}$3`);
  fs.writeFileSync(stringsFile, text, 'utf8');
}

let gradleFile = path.join(projectRoot, 'app', 'build.gradle.kts');
if (!fs.existsSync(gradleFile)) {
  gradleFile = path.join(projectRoot, 'app', 'build.gradle');
}
if (fs.existsSync(gradleFile)) {
  let gtext = fs.readFileSync(gradleFile, 'utf8');
  gtext = gtext.replace(/applicationId\s*=\s*"[^"]+"/, `applicationId = "${packageName}"`);
  gtext = gtext.replace(/versionCode[[:space:]]*=[[:space:]]*\d+/, `versionCode = ${versionCode}`);
  gtext = gtext.replace(/versionName[[:space:]]*=[[:space:]]*"[^"]+"/, `versionName = "${versionName}"`);
  gtext = gtext.replace(/buildConfigField\(\s*"String"\s*,\s*"WEBVIEW_URL"[\s\S]*?\)/, `buildConfigField("String", "WEBVIEW_URL", "\\"${webUrl}\\"")`);
  gtext = gtext.replace(/buildConfigField\(\s*"boolean"\s*,\s*"HIDE_STATUS_BAR"[\s\S]*?\)/, `buildConfigField("boolean", "HIDE_STATUS_BAR", "${statusBarHidden}")`);
  gtext = gtext.replace(/buildConfigField\(\s*"String"\s*,\s*"STATUS_BAR_BACKGROUND"[\s\S]*?\)/, `buildConfigField("String", "STATUS_BAR_BACKGROUND", "\\"${statusBarBackground}\\"")`);
  gtext = gtext.replace(/buildConfigField\(\s*"boolean"\s*,\s*"LIGHT_STATUS_BAR_ICONS"[\s\S]*?\)/, `buildConfigField("boolean", "LIGHT_STATUS_BAR_ICONS", "${lightStatusBarIcons}")`);
  gtext = gtext.replace(/buildConfigField\(\s*"boolean"\s*,\s*"DOUBLE_CLICK_EXIT"[\s\S]*?\)/, `buildConfigField("boolean", "DOUBLE_CLICK_EXIT", "${doubleClickExit}")`);
  fs.writeFileSync(gradleFile, gtext, 'utf8');
}
NODE

    if [ -f "$INPUT_DIR/logo.png" ]; then
        drawable_dir="$PROJECT_ROOT/app/src/main/res/drawable"
        if [ -d "$drawable_dir" ]; then
            rm -f "$drawable_dir/ic_launcher_foreground.xml"
            cp "$INPUT_DIR/logo.png" "$drawable_dir/ic_launcher_foreground.png"
            log_info "Template launcher icon updated"
        fi
    fi

    cd "$PROJECT_ROOT"
    log_success "Step 0 done"
else
    # check zip for convert mode
    ZIP_FILE=$(find $INPUT_DIR -name "*.zip" -type f | head -n 1)

    if [ -z "$ZIP_FILE" ]; then
        log_error "No ZIP found in $INPUT_DIR"
        exit 1
    fi

    log_info "Found ZIP: $ZIP_FILE"

    # create project dir
    rm -rf $PROJECT_DIR
    mkdir -p $PROJECT_DIR

    # unzip
    log_info "Unzip project..."
    unzip -q "$ZIP_FILE" -d $PROJECT_DIR
    check_error "Unzip failed"

    # find package.json
    PACKAGE_JSON=$(find $PROJECT_DIR -name "package.json" -type f | head -n 1)
    if [ -z "$PACKAGE_JSON" ]; then
        log_error "package.json not found"
        exit 1
    fi

    PROJECT_ROOT=$(dirname "$PACKAGE_JSON")
    log_info "Project root: $PROJECT_ROOT"

    cd $PROJECT_ROOT

    log_success "Step 0 done"
fi
if [ "$TASK_MODE" != "web" ]; then
# ============================================
log_info "Step 1: 构建 Web 项目..."

# 完整重装依赖的函数
reinstall_dependencies() {
    log_info "清理并重新安装所有依赖..."
    
    # 删除 node_modules 和 lock 文件
    rm -rf node_modules
    rm -f package-lock.json
    rm -f yarn.lock
    rm -f pnpm-lock.yaml
    
    # 重新安装
    npm install --legacy-peer-deps
    return $?
}

# 首次安装依赖
log_info "安装 npm 依赖..."
npm install --legacy-peer-deps
check_error "npm install 失败"

# 尝试构建
log_info "构建项目..."
BUILD_OUTPUT=$(npm run build 2>&1) && BUILD_SUCCESS=true || BUILD_SUCCESS=false

if [ "$BUILD_SUCCESS" = "true" ]; then
    log_success "项目构建成功"
else
    log_warning "首次构建失败，分析错误..."
    echo "$BUILD_OUTPUT"
    
    # 提取缺失的模块名
    MISSING_MODULES=""
    
    # 检查 Rollup/Vite 的 "resolve import" 错误
    ROLLUP_MISSING=$(echo "$BUILD_OUTPUT" | grep -oE 'resolve import "[^"]+"' | \
        sed 's/resolve import "\([^"]*\)"/\1/' | sort -u)
    if [ -n "$ROLLUP_MISSING" ]; then
        MISSING_MODULES="$ROLLUP_MISSING"
    fi
    
    # 检查 "Cannot find module" 错误
    CANNOT_FIND=$(echo "$BUILD_OUTPUT" | grep -oE "Cannot find module '[^']+'" | \
        sed "s/Cannot find module '\([^']*\)'/\1/" | sort -u)
    if [ -n "$CANNOT_FIND" ]; then
        MISSING_MODULES="$MISSING_MODULES $CANNOT_FIND"
    fi
    
    # 检查 "Module not found" 错误
    MODULE_NOT_FOUND=$(echo "$BUILD_OUTPUT" | grep -oE "Module not found[^']*'[^']+'" | \
        sed "s/.*'\([^']*\)'/\1/" | sort -u)
    if [ -n "$MODULE_NOT_FOUND" ]; then
        MISSING_MODULES="$MISSING_MODULES $MODULE_NOT_FOUND"
    fi
    
    if [ -n "$MISSING_MODULES" ]; then
        log_info "检测到缺失模块: $MISSING_MODULES"
        
        # 安装每个缺失的模块
        for module in $MISSING_MODULES; do
            # 提取包名（去掉子路径，如 'lodash/get' -> 'lodash'）
            PKG_NAME=$(echo "$module" | sed 's/\/.*//')
            # 过滤掉相对路径
            if [[ ! "$PKG_NAME" =~ ^\. ]] && [[ ! "$PKG_NAME" =~ ^/ ]]; then
                log_info "安装: $PKG_NAME"
                npm install "$PKG_NAME" --legacy-peer-deps --save 2>/dev/null || true
            fi
        done
        
        # 第二次尝试构建
        log_info "重新构建项目..."
        BUILD_OUTPUT2=$(npm run build 2>&1) && BUILD_SUCCESS2=true || BUILD_SUCCESS2=false
        
        if [ "$BUILD_SUCCESS2" = "true" ]; then
            log_success "项目构建成功"
        else
            log_warning "第二次构建仍失败，尝试完整重装依赖..."
            
            # 完整重装
            reinstall_dependencies
            check_error "依赖重装失败"
            
            # 第三次尝试构建
            log_info "最终构建尝试..."
            npm run build
            check_error "npm run build 失败"
        fi
    else
        # 没有检测到缺失模块，直接尝试完整重装
        log_warning "未检测到具体缺失模块，尝试完整重装依赖..."
        
        reinstall_dependencies
        check_error "依赖重装失败"
        
        # 再次构建
        log_info "重新构建项目..."
        npm run build
        check_error "npm run build 失败"
    fi
fi

# 确定输出目录
if [ -d "dist" ]; then
    WEB_DIR="dist"
elif [ -d "build" ]; then
    WEB_DIR="build"
else
    log_error "未找到构建输出目录 (dist 或 build)"
    exit 1
fi

log_success "Web 项目构建完成，输出目录: $WEB_DIR"

# 注入前端下载处理脚本（拦截 blob/data 下载并尝试保存）
log_info "注入前端下载处理脚本..."
node << 'NODE'
const fs = require("fs");
const path = require("path");

function readText(file) {
  try {
    return fs.readFileSync(file, "utf8");
  } catch (err) {
    return fs.readFileSync(file, "latin1");
  }
}

function writeText(file, text) {
  fs.writeFileSync(file, text, "utf8");
}

const webDir = process.env.WEB_DIR || "dist";
const indexHtml = path.join(process.cwd(), webDir, "index.html");
if (!fs.existsSync(indexHtml)) {
  process.exit(0);
}

let html = readText(indexHtml);
if (html.includes("convertapk-download-helper")) {
  process.exit(0);
}

const script =
  "<script id=\"convertapk-download-helper\">(function(){\n" +
  "  if (window.__convertapkDownloadHelper) return;\n" +
  "  window.__convertapkDownloadHelper = true;\n" +
  "  function getAnchor(el){\n" +
  "    while (el && el.tagName !== 'A') el = el.parentElement;\n" +
  "    return el;\n" +
  "  }\n" +
  "  function getFilename(a, href){\n" +
  "    var name = (a.getAttribute('download') || a.download || '').trim();\n" +
  "    if (name) return name;\n" +
  "    try {\n" +
  "      var url = new URL(href, window.location.href);\n" +
  "      name = url.pathname.split('/').pop() || 'download';\n" +
  "    } catch (e) {\n" +
  "      name = 'download';\n" +
  "    }\n" +
  "    return name;\n" +
  "  }\n" +
  "  function readAsDataUrl(blob){\n" +
  "    return new Promise(function(resolve, reject){\n" +
  "      var reader = new FileReader();\n" +
  "      reader.onload = function(){ resolve(reader.result || ''); };\n" +
  "      reader.onerror = function(){ reject(reader.error); };\n" +
  "      reader.readAsDataURL(blob);\n" +
  "    });\n" +
  "  }\n" +
  "  async function shareFile(filename){\n" +
  "    try {\n" +
  "      var cap = window.Capacitor;\n" +
  "      if (!cap || !cap.Plugins || !cap.Plugins.Share || !cap.Plugins.Filesystem) return false;\n" +
  "      var fsPlugin = cap.Plugins.Filesystem;\n" +
  "      var uriResult = await fsPlugin.getUri({ path: filename, directory: 'DOCUMENTS' });\n" +
  "      var fileUrl = uriResult && uriResult.uri ? uriResult.uri : '';\n" +
  "      if (!fileUrl) {\n" +
  "        uriResult = await fsPlugin.getUri({ path: filename, directory: 'DATA' });\n" +
  "        fileUrl = uriResult && uriResult.uri ? uriResult.uri : '';\n" +
  "      }\n" +
  "      if (!fileUrl) return false;\n" +
  "      await cap.Plugins.Share.share({ title: filename, text: filename, url: fileUrl });\n" +
  "      return true;\n" +
  "    } catch (e) {\n" +
  "      return false;\n" +
  "    }\n" +
  "  }\n" +
  "  async function saveBlob(blob, filename){\n" +
  "    var cap = window.Capacitor;\n" +
  "    if (!cap || !cap.Plugins || !cap.Plugins.Filesystem) return false;\n" +
  "    var dataUrl = await readAsDataUrl(blob);\n" +
  "    var base64 = String(dataUrl).split(',')[1] || '';\n" +
  "    var fsPlugin = cap.Plugins.Filesystem;\n" +
  "    try {\n" +
  "      await fsPlugin.writeFile({ path: filename, data: base64, directory: 'DOCUMENTS', recursive: true });\n" +
  "      return true;\n" +
  "    } catch (e) {\n" +
  "      try {\n" +
  "        await fsPlugin.writeFile({ path: filename, data: base64, directory: 'DATA', recursive: true });\n" +
  "        return true;\n" +
  "      } catch (e2) {\n" +
  "        return false;\n" +
  "      }\n" +
  "    }\n" +
  "  }\n" +
  "  async function handleDownload(a, href){\n" +
  "    if (!href) return false;\n" +
  "    var isBlob = href.startsWith('blob:');\n" +
  "    var isData = href.startsWith('data:');\n" +
  "    if (!isBlob && !isData) {\n" +
  "      try {\n" +
  "        var url = new URL(href, window.location.href).toString();\n" +
  "        var cap = window.Capacitor;\n" +
  "        if (cap && cap.Plugins && cap.Plugins.Browser) {\n" +
  "          cap.Plugins.Browser.open({ url: url });\n" +
  "          return true;\n" +
  "        }\n" +
  "        window.open(url, '_blank');\n" +
  "        return true;\n" +
  "      } catch (e) {\n" +
  "        return false;\n" +
  "      }\n" +
  "    }\n" +
  "    try {\n" +
  "      var res = await fetch(href);\n" +
  "      var blob = await res.blob();\n" +
  "      return await saveBlob(blob, getFilename(a, href));\n" +
  "    } catch (e) {\n" +
  "      return false;\n" +
  "    }\n" +
  "  }\n" +
  "  async function shareFiles(files, title){\n" +
  "    if (!files || !files.length) return false;\n" +
  "    var file = files[0];\n" +
  "    var name = (file && file.name) || title || 'share';\n" +
  "    try {\n" +
  "      var ok = await saveBlob(file, name);\n" +
  "      if (!ok) return false;\n" +
  "      return await shareFile(name);\n" +
  "    } catch (e) {\n" +
  "      return false;\n" +
  "    }\n" +
  "  }\n" +
  "  (function(){\n" +
  "    if (!navigator) return;\n" +
  "    var cap = window.Capacitor;\n" +
  "    if (!cap || !cap.Plugins || !cap.Plugins.Share || !cap.Plugins.Filesystem) return;\n" +
  "    var origCanShare = navigator.canShare ? navigator.canShare.bind(navigator) : null;\n" +
  "    navigator.canShare = function(data){\n" +
  "      if (data && data.files && data.files.length) return true;\n" +
  "      return origCanShare ? origCanShare(data) : false;\n" +
  "    };\n" +
  "    if (navigator.share) {\n" +
  "      var origShare = navigator.share.bind(navigator);\n" +
  "      navigator.share = async function(data){\n" +
  "        if (data && data.files && data.files.length) {\n" +
  "          var ok = await shareFiles(data.files, data.title || data.text || '');\n" +
  "          if (ok) return;\n" +
  "        }\n" +
  "        return origShare(data);\n" +
  "      };\n" +
  "    } else {\n" +
  "      navigator.share = async function(data){\n" +
  "        if (data && data.files && data.files.length) {\n" +
  "          var ok = await shareFiles(data.files, data.title || data.text || '');\n" +
  "          if (ok) return;\n" +
  "        }\n" +
  "        throw new Error('share not supported');\n" +
  "      };\n" +
  "    }\n" +
  "  })();\n" +
  "  function hookJsPdfSave(){\n" +
  "    try {\n" +
  "      var JSPDF = (window.jspdf && window.jspdf.jsPDF) || window.jsPDF;\n" +
  "      if (!JSPDF || !JSPDF.API || JSPDF.API.__convertapkSavePatched) return false;\n" +
  "      var origSave = JSPDF.API.save;\n" +
  "      JSPDF.API.save = function(filename){\n" +
  "        try {\n" +
  "          var blob = this.output('blob');\n" +
  "          saveBlob(blob, filename || 'download.pdf');\n" +
  "          return;\n" +
  "        } catch (e) {\n" +
  "        }\n" +
  "        return origSave ? origSave.apply(this, arguments) : undefined;\n" +
  "      };\n" +
  "      JSPDF.API.__convertapkSavePatched = true;\n" +
  "      return true;\n" +
  "    } catch (e) {\n" +
  "      return false;\n" +
  "    }\n" +
  "  }\n" +
  "  var _pdfTries = 0;\n" +
  "  var _pdfTimer = setInterval(function(){\n" +
  "    _pdfTries += 1;\n" +
  "    if (hookJsPdfSave() || _pdfTries > 20) clearInterval(_pdfTimer);\n" +
  "  }, 500);\n" +
  "  if (navigator) {\n" +
  "    try {\n" +
  "      navigator.msSaveOrOpenBlob = function(blob, name){ saveBlob(blob, name || 'download'); return true; };\n" +
  "      navigator.msSaveBlob = function(blob, name){ saveBlob(blob, name || 'download'); return true; };\n" +
  "    } catch (e) {\n" +
  "    }\n" +
  "  }\n" +
  "  try {\n" +
  "    window.saveAs = function(blob, name){ return saveBlob(blob, name || 'download'); };\n" +
  "  } catch (e) {\n" +
  "  }\n" +
  "  var _origClick = HTMLAnchorElement.prototype.click;\n" +
  "  HTMLAnchorElement.prototype.click = function(){\n" +
  "    try {\n" +
  "      var href = this.getAttribute('href') || this.href || '';\n" +
  "      var download = this.getAttribute('download') || this.download;\n" +
  "      if (download || href.startsWith('blob:') || href.startsWith('data:')) {\n" +
  "        handleDownload(this, href);\n" +
  "        return;\n" +
  "      }\n" +
  "    } catch (e) {\n" +
  "    }\n" +
  "    return _origClick.call(this);\n" +
  "  };\n" +
  "  var _origDispatch = HTMLAnchorElement.prototype.dispatchEvent;\n" +
  "  HTMLAnchorElement.prototype.dispatchEvent = function(evt){\n" +
  "    try {\n" +
  "      if (evt && evt.type === 'click') {\n" +
  "        var href = this.getAttribute('href') || this.href || '';\n" +
  "        var download = this.getAttribute('download') || this.download;\n" +
  "        if (download || href.startsWith('blob:') || href.startsWith('data:')) {\n" +
  "          handleDownload(this, href);\n" +
  "          return true;\n" +
  "        }\n" +
  "      }\n" +
  "    } catch (e) {\n" +
  "    }\n" +
  "    return _origDispatch.call(this, evt);\n" +
  "  };\n" +
  "  document.addEventListener('click', function(e){\n" +
  "    var a = getAnchor(e.target);\n" +
  "    if (!a) return;\n" +
  "    var href = a.getAttribute('href') || '';\n" +
  "    var download = a.getAttribute('download') || a.download;\n" +
  "    if (!href) return;\n" +
  "    if (download || href.startsWith('blob:') || href.startsWith('data:')) {\n" +
  "      e.preventDefault();\n" +
  "      e.stopPropagation();\n" +
  "      handleDownload(a, href);\n" +
  "    }\n" +
  "  }, true);\n" +
  "})();</script>";

if (html.includes("</body>")) {
  html = html.replace("</body>", script + "\\n</body>");
} else {
  html += "\\n" + script;
}

writeText(indexHtml, html);
NODE

# ============================================
# 步骤 2: 初始化 Capacitor
# ============================================
log_info "Step 2: 初始化 Capacitor..."

# 检查是否已安装Capacitor
if ! grep -q "@capacitor/core" package.json; then
    log_info "安装 @capacitor/core..."
    npm install @capacitor/core --legacy-peer-deps
    check_error "安装 @capacitor/core 失败"
fi

if ! grep -q "@capacitor/cli" package.json; then
    log_info "安装 @capacitor/cli..."
    npm install -D @capacitor/cli --legacy-peer-deps
    check_error "安装 @capacitor/cli 失败"
fi

if ! grep -q "@capacitor/filesystem" package.json; then
    log_info "安装 @capacitor/filesystem..."
    npm install @capacitor/filesystem --legacy-peer-deps
    check_error "安装 @capacitor/filesystem 失败"
fi

if ! grep -q "@capacitor/browser" package.json; then
    log_info "安装 @capacitor/browser..."
    npm install @capacitor/browser --legacy-peer-deps
    check_error "安装 @capacitor/browser 失败"
fi

if ! grep -q "@capacitor/share" package.json; then
    log_info "安装 @capacitor/share..."
    npm install @capacitor/share --legacy-peer-deps
    check_error "安装 @capacitor/share 失败"
fi

# 创建 capacitor.config.ts
log_info "创建 Capacitor 配置..."
cat > capacitor.config.ts << EOF
import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: '${PACKAGE_NAME}',
  appName: '${APP_NAME}',
  webDir: '${WEB_DIR}',
  server: {
    androidScheme: 'https'
  }
};

export default config;
EOF

log_success "Capacitor 初始化完成"

# ============================================
# 步骤 3: 添加 Android 平台
# ============================================
log_info "Step 3: 添加 Android 平台..."

# 检查是否已安装android平台
if ! grep -q "@capacitor/android" package.json; then
    log_info "安装 @capacitor/android..."
    npm install @capacitor/android --legacy-peer-deps
    check_error "安装 @capacitor/android 失败"
fi

# 添加Android平台
if [ ! -d "android" ]; then
    log_info "添加 Android 平台..."
    npx cap add android
    check_error "添加 Android 平台失败"
else
    log_info "Android 平台已存在"
fi

log_success "Android 平台添加完成"

# ============================================
# 步骤 4: 设置应用图标
# ============================================
log_info "Step 4: 设置应用图标..."

# 安装 @capacitor/assets
log_info "安装 @capacitor/assets..."
npm install -D @capacitor/assets --legacy-peer-deps
check_error "安装 @capacitor/assets 失败"

# 创建 assets 目录
mkdir -p assets

# 检查是否有上传的图标
if [ -f "$INPUT_DIR/logo.png" ]; then
    log_info "使用上传的图标..."
    cp "$INPUT_DIR/logo.png" assets/logo.png
else
    log_warning "未找到上传的图标，将使用默认图标"
    # 创建一个默认图标（如果没有上传）
    # 可以在这里放置一个默认图标的逻辑
fi

# 检查图标文件是否存在
if [ -f "assets/logo.png" ]; then
    log_info "生成应用图标和启动画面..."
    
    # 设置背景色（可通过环境变量自定义）
    ICON_BG_COLOR=${ICON_BG_COLOR:-"#ffffff"}
    ICON_BG_COLOR_DARK=${ICON_BG_COLOR_DARK:-"#111111"}
    SPLASH_BG_COLOR=${SPLASH_BG_COLOR:-"#ffffff"}
    SPLASH_BG_COLOR_DARK=${SPLASH_BG_COLOR_DARK:-"#111111"}
    
    npx @capacitor/assets generate --android \
        --iconBackgroundColor "$ICON_BG_COLOR" \
        --iconBackgroundColorDark "$ICON_BG_COLOR_DARK" \
        --splashBackgroundColor "$SPLASH_BG_COLOR" \
        --splashBackgroundColorDark "$SPLASH_BG_COLOR_DARK"
    check_error "图标生成失败"
    
    log_success "应用图标设置完成"
else
    log_warning "跳过图标设置（未找到 assets/logo.png）"
fi

# ============================================
# 步骤 5: 同步代码
# ============================================
log_info "Step 5: 同步代码到 Android 项目..."

npx cap sync android
check_error "代码同步失败"

log_success "代码同步完成"

# 注入下载处理（外部浏览器下载）
log_info "注入 Android 下载处理..."
fi
export ANDROID_DIR="$ANDROID_DIR"
node << 'NODE'
const fs = require("fs");
const path = require("path");

function readText(file) {
  try {
    return fs.readFileSync(file, "utf8");
  } catch (err) {
    return fs.readFileSync(file, "latin1");
  }
}

function writeText(file, text) {
  fs.writeFileSync(file, text, "utf8");
}

function findMainActivity(javaRoot) {
  const stack = [javaRoot];
  while (stack.length) {
    const dir = stack.pop();
    const entries = fs.readdirSync(dir, { withFileTypes: true });
    for (const entry of entries) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        stack.push(full);
      } else if (
        entry.isFile() &&
        (entry.name === "MainActivity.java" || entry.name === "MainActivity.kt")
      ) {
        return full;
      }
    }
  }
  return null;
}

const projectRoot = process.cwd();
const androidDir = path.resolve(process.env.ANDROID_DIR || path.join(projectRoot, "android"));
const javaRoot = path.join(androidDir, "app", "src", "main", "java");
if (!fs.existsSync(javaRoot)) {
  process.exit(0);
}

const mainActivity = findMainActivity(javaRoot);
if (!mainActivity) {
  process.exit(0);
}

let text = readText(mainActivity);
const originalText = text;
const isKotlin = mainActivity.endsWith(".kt");
const packageNameRaw = String(process.env.PACKAGE_NAME || "").trim();
const doubleClickExit =
  String(process.env.DOUBLE_CLICK_EXIT || "").trim().toLowerCase() === "true";
const taskMode = String(process.env.TASK_MODE || "").trim().toLowerCase();
const allowKotlinPatch = taskMode !== "web";
const packageLineMatch = text.match(/^package\s+[^\s]+/m);
const packageLine = packageNameRaw
  ? `package ${packageNameRaw}`
  : (packageLineMatch ? packageLineMatch[0] : "package com.example.app");
let replacedKotlin = false;

if (
  isKotlin &&
  allowKotlinPatch &&
  text.includes("BridgeActivity") &&
  !text.includes("ConvertAPK: enhanced main")
) {
  text = `${packageLine}

// ConvertAPK: enhanced main
import android.app.Activity
import android.app.DownloadManager
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.os.Environment
import android.webkit.CookieManager
import android.webkit.URLUtil
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebChromeClient.FileChooserParams
import android.webkit.WebView
import android.widget.Toast
import androidx.activity.OnBackPressedCallback
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.view.ViewCompat
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowInsetsControllerCompat
import android.view.View
import android.view.WindowManager
import com.getcapacitor.BridgeActivity

class MainActivity : BridgeActivity() {
    private var lastBackPressedAt: Long = 0L
    private val doubleClickExitEnabled = ${doubleClickExit ? "true" : "false"}
    private var filePathCallback: ValueCallback<Array<Uri>>? = null
    private val fileChooserLauncher = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { result ->
        val callback = filePathCallback
        if (callback == null) return@registerForActivityResult
        val uris = if (result.resultCode == Activity.RESULT_OK) {
            val data = result.data
            val clipData = data?.clipData
            when {
                clipData != null -> Array(clipData.itemCount) { idx -> clipData.getItemAt(idx).uri }
                data?.data != null -> arrayOf(data.data!!)
                else -> emptyArray()
            }
        } else {
            emptyArray()
        }
        callback.onReceiveValue(uris)
        filePathCallback = null
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        applySystemBars()
        setupWebView()
        if (doubleClickExitEnabled) {
            onBackPressedDispatcher.addCallback(
                this,
                object : OnBackPressedCallback(true) {
                    override fun handleOnBackPressed() {
                        handleBackPressed()
                    }
                }
            )
        }
    }

    private fun setupWebView() {
        val webView = bridge?.webView ?: return
        webView.clipToPadding = false
        val root = window.decorView
        ViewCompat.setOnApplyWindowInsetsListener(root) { _, insets ->
            val nav = insets.getInsets(WindowInsetsCompat.Type.navigationBars())
            webView.setPadding(nav.left, webView.paddingTop, nav.right, nav.bottom)
            webView.post {
                val script = "(function(){var b=" + nav.bottom +
                    ";var root=document.documentElement;" +
                    "root.style.boxSizing='border-box';root.style.paddingBottom=b+'px';" +
                    "if(document.body){document.body.style.boxSizing='border-box';document.body.style.paddingBottom=b+'px';}" +
                    "})();"
                webView.evaluateJavascript(script, null)
            }
            insets
        }
        ViewCompat.requestApplyInsets(root)
        webView.webChromeClient = object : WebChromeClient() {
            override fun onShowFileChooser(
                webView: WebView?,
                filePathCallback: ValueCallback<Array<Uri>>?,
                fileChooserParams: FileChooserParams?
            ): Boolean {
                this@MainActivity.filePathCallback?.onReceiveValue(null)
                this@MainActivity.filePathCallback = filePathCallback
                val intent = try {
                    fileChooserParams?.createIntent()
                } catch (_: Exception) {
                    null
                }
                val fallback = Intent(Intent.ACTION_OPEN_DOCUMENT).apply {
                    addCategory(Intent.CATEGORY_OPENABLE)
                    addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                    type = "*/*"
                    val allowMultiple = fileChooserParams?.mode == FileChooserParams.MODE_OPEN_MULTIPLE
                    putExtra(Intent.EXTRA_ALLOW_MULTIPLE, allowMultiple)
                }
                val chooserTitle = fileChooserParams?.title ?: "Select file"
                val chooser = Intent.createChooser(intent ?: fallback, chooserTitle)
                return try {
                    fileChooserLauncher.launch(chooser)
                    true
                } catch (_: Exception) {
                    this@MainActivity.filePathCallback = null
                    false
                }
            }
        }
        webView.setDownloadListener { url, userAgent, contentDisposition, mimeType, _ ->
            try {
                val request = DownloadManager.Request(Uri.parse(url))
                request.setMimeType(mimeType)
                request.addRequestHeader("User-Agent", userAgent)
                val cookie = CookieManager.getInstance().getCookie(url)
                if (cookie != null) {
                    request.addRequestHeader("cookie", cookie)
                }
                val filename = URLUtil.guessFileName(url, contentDisposition, mimeType)
                request.setTitle(filename)
                request.setDescription(url)
                request.setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED)
                request.setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS, filename)
                val dm = getSystemService(DOWNLOAD_SERVICE) as DownloadManager
                dm.enqueue(request)
            } catch (_: Exception) {
                Toast.makeText(this, "Download failed", Toast.LENGTH_SHORT).show()
            }
        }
    }

    override fun onWindowFocusChanged(hasFocus: Boolean) {
        super.onWindowFocusChanged(hasFocus)
        if (hasFocus) {
            applySystemBars()
        }
    }

    override fun onBackPressed() {
        if (!doubleClickExitEnabled) {
            val webView = bridge?.webView
            if (webView != null && webView.canGoBack()) {
                webView.goBack()
                return
            }
            super.onBackPressed()
            return
        }
        handleBackPressed()
    }

    private fun handleBackPressed() {
        val webView = bridge?.webView
        if (webView != null && webView.canGoBack()) {
            webView.goBack()
            return
        }
        if (!doubleClickExitEnabled) {
            finish()
            return
        }
        val now = System.currentTimeMillis()
        if (now - lastBackPressedAt <= 2000) {
            finish()
        } else {
            lastBackPressedAt = now
            Toast.makeText(this@MainActivity, "Press back again to exit", Toast.LENGTH_SHORT).show()
        }
    }

    private fun applySystemBars() {
        val statusBarBackground = BuildConfig.STATUS_BAR_BACKGROUND.trim().lowercase()
        val drawBehind = statusBarBackground == "transparent"
        WindowCompat.setDecorFitsSystemWindows(window, !drawBehind)
        @Suppress("DEPRECATION")
        window.statusBarColor = if (drawBehind) android.graphics.Color.TRANSPARENT else android.graphics.Color.WHITE
        val controller = WindowInsetsControllerCompat(window, window.decorView)
        controller.isAppearanceLightStatusBars = BuildConfig.LIGHT_STATUS_BAR_ICONS
        if (BuildConfig.HIDE_STATUS_BAR) {
            window.addFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN)
            window.clearFlags(WindowManager.LayoutParams.FLAG_FORCE_NOT_FULLSCREEN)
            @Suppress("DEPRECATION")
            window.decorView.systemUiVisibility =
                View.SYSTEM_UI_FLAG_FULLSCREEN or View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
            controller.systemBarsBehavior =
                WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
            controller.hide(WindowInsetsCompat.Type.statusBars())
        } else {
            window.clearFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN)
            window.addFlags(WindowManager.LayoutParams.FLAG_FORCE_NOT_FULLSCREEN)
            @Suppress("DEPRECATION")
            window.decorView.systemUiVisibility =
                if (BuildConfig.LIGHT_STATUS_BAR_ICONS) {
                    View.SYSTEM_UI_FLAG_VISIBLE or View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR
                } else {
                    View.SYSTEM_UI_FLAG_VISIBLE
                }
            controller.show(WindowInsetsCompat.Type.statusBars())
        }
    }
}
`;
  replacedKotlin = true;
}

const statusBarHidden =
  String(process.env.STATUS_BAR_HIDDEN || "").trim().toLowerCase() === "true";
const statusBarColorRaw = String(process.env.STATUS_BAR_COLOR || "transparent").trim();
const statusBarColorLower = statusBarColorRaw.toLowerCase();
const statusBarIsWhite =
  statusBarColorLower === "white" ||
  statusBarColorLower === "#ffffff" ||
  statusBarColorLower === "#ffffffff";

if (!replacedKotlin && !(isKotlin && !allowKotlinPatch)) {
  const importSuffix = isKotlin ? "" : ";";
  const imports = [
    `import android.content.Intent${importSuffix}`,
    `import android.net.Uri${importSuffix}`,
    `import android.os.Bundle${importSuffix}`,
    `import android.webkit.WebView${importSuffix}`,
  ];
  if (!isKotlin) {
    imports.push(`import android.view.View${importSuffix}`);
    imports.push(`import androidx.core.view.ViewCompat${importSuffix}`);
    imports.push(`import androidx.core.view.WindowInsetsCompat${importSuffix}`);
    imports.push(`import androidx.core.graphics.Insets${importSuffix}`);
  }
  if (statusBarHidden || statusBarIsWhite) {
    imports.push(`import android.os.Build${importSuffix}`);
    imports.push(`import android.view.View${importSuffix}`);
    imports.push(`import android.view.WindowInsets${importSuffix}`);
  }
  if (doubleClickExit) {
    imports.push(`import android.widget.Toast${importSuffix}`);
    imports.push(`import androidx.activity.OnBackPressedCallback${importSuffix}`);
  }

  const lines = text.split(/\r?\n/);
  let insertAt = 1;
  for (let i = 0; i < lines.length; i++) {
    if (lines[i].startsWith("import ")) {
      insertAt = i + 1;
    }
  }
  for (const imp of imports) {
    if (!lines.includes(imp)) {
      lines.splice(insertAt, 0, imp);
      insertAt++;
    }
  }
  text = lines.join("\n");
}

if (isKotlin && !replacedKotlin && allowKotlinPatch) {
  const hasBackPress = text.includes("ConvertAPK: back-press dispatcher");
  const backPressSnippet = doubleClickExit && !hasBackPress
    ? "        // ConvertAPK: back-press dispatcher\n" +
      "        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {\n" +
      "            override fun handleOnBackPressed() {\n" +
      "                val webView = bridge?.webView\n" +
      "                if (webView != null && webView.canGoBack()) {\n" +
      "                    webView.goBack()\n" +
      "                    return\n" +
      "                }\n" +
      "                val now = System.currentTimeMillis()\n" +
      "                if (now - lastBackPressedAt < 2000) {\n" +
      "                    finish()\n" +
      "                } else {\n" +
      "                    lastBackPressedAt = now\n" +
      "                    Toast.makeText(this@MainActivity, \"Press back again to exit\", Toast.LENGTH_SHORT).show()\n" +
      "                }\n" +
      "            }\n" +
      "        })\n"
    : "";

  const hasBackPressField = originalText.includes("lastBackPressedAt");
  if (doubleClickExit && !originalText.includes("ConvertAPK: back-press state") && !hasBackPressField) {
    const result = insertAfterClassOpen(
      text,
      "    // ConvertAPK: back-press state\n" +
        "    private var lastBackPressedAt: Long = 0L\n"
    );
    text = result.text;
  }

  if (text.includes("override fun onCreate(")) {
    const marker = "super.onCreate(savedInstanceState)";
    if (text.includes(marker) && backPressSnippet.trim().length) {
      text = text.replace(marker, marker + "\n" + backPressSnippet.trimEnd());
    }
  } else if (backPressSnippet.trim().length) {
    const insert =
      "    override fun onCreate(savedInstanceState: Bundle?) {\n" +
      "        super.onCreate(savedInstanceState)\n" +
      backPressSnippet +
      "    }\n\n";
    const idx = text.lastIndexOf("}");
    if (idx !== -1) {
      text = text.slice(0, idx) + insert + text.slice(idx);
    }
  }
}

if (!isKotlin) {
  const hasDownloadListener = text.includes("setDownloadListener");
  const snippet = hasDownloadListener
    ? ""
    :
    "        WebView webView = getBridge().getWebView();\n" +
    "        if (webView != null) {\n" +
    "            webView.setDownloadListener((url, userAgent, contentDisposition, mimeType, contentLength) -> {\n" +
    "                try {\n" +
    "                    Intent intent = new Intent(Intent.ACTION_VIEW);\n" +
    "                    intent.setData(Uri.parse(url));\n" +
    "                    intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);\n" +
    "                    startActivity(intent);\n" +
    "                } catch (Exception ignored) {\n" +
    "                }\n" +
    "            });\n" +
    "            webView.setClipToPadding(false);\n" +
    "            View decor = getWindow().getDecorView();\n" +
    "            ViewCompat.setOnApplyWindowInsetsListener(decor, (v, insets) -> {\n" +
    "                Insets nav = insets.getInsets(WindowInsetsCompat.Type.navigationBars());\n" +
    "                webView.setPadding(nav.left, webView.getPaddingTop(), nav.right, nav.bottom);\n" +
    "                webView.post(() -> webView.evaluateJavascript(\n" +
    "                    \"(function(){var b=\" + nav.bottom + \";\" +\n" +
    "                    \"var root=document.documentElement;\" +\n" +
    "                    \"root.style.boxSizing='border-box';root.style.paddingBottom=b+'px';\" +\n" +
    "                    \"if(document.body){document.body.style.boxSizing='border-box';document.body.style.paddingBottom=b+'px';}\" +\n" +
    "                    \"})();\", null));\n" +
    "                return insets;\n" +
    "            });\n" +
    "            ViewCompat.requestApplyInsets(decor);\n" +
    "        }\n";

  const hasStatusSnippet = text.includes("ConvertAPK: status bar");
  const statusSnippet = !hasStatusSnippet
    ? statusBarHidden
      ? "        // ConvertAPK: status bar\n" +
        "        applyStatusBarHidden();\n"
      : statusBarIsWhite
        ? "        // ConvertAPK: status bar\n" +
          "        applyStatusBarVisibleWhite();\n"
        : ""
    : "";

  const backPressSnippet = doubleClickExit && !text.includes("ConvertAPK: back-press dispatcher")
    ? "        // ConvertAPK: back-press dispatcher\n" +
      "        getOnBackPressedDispatcher().addCallback(this, new OnBackPressedCallback(true) {\n" +
      "            @Override\n" +
      "            public void handleOnBackPressed() {\n" +
      "                android.webkit.WebView webView = getBridge() != null ? getBridge().getWebView() : null;\n" +
      "                if (webView != null && webView.canGoBack()) {\n" +
      "                    webView.goBack();\n" +
      "                    return;\n" +
      "                }\n" +
      "                long now = System.currentTimeMillis();\n" +
      "                if (now - lastBackPressedAt < 2000) {\n" +
      "                    finish();\n" +
      "                } else {\n" +
      "                    lastBackPressedAt = now;\n" +
      "                    Toast.makeText(MainActivity.this, \"Press back again to exit\", Toast.LENGTH_SHORT).show();\n" +
      "                }\n" +
      "            }\n" +
      "        });\n"
    : "";

  if (text.includes("protected void onCreate(Bundle savedInstanceState)")) {
    const marker = "super.onCreate(savedInstanceState);";
    if (text.includes(marker)) {
      const injected = snippet.trimEnd() +
        (statusSnippet ? "\n" + statusSnippet.trimEnd() : "") +
        (backPressSnippet ? "\n" + backPressSnippet.trimEnd() : "");
      if (injected.trim().length) {
        text = text.replace(marker, marker + "\n" + injected);
      }
    }
  } else {
    const insert =
      "    @Override\n" +
      "    protected void onCreate(Bundle savedInstanceState) {\n" +
      "        super.onCreate(savedInstanceState);\n" +
      snippet +
      statusSnippet +
      backPressSnippet +
      "    }\n\n";
    const idx = text.lastIndexOf("}");
    if (idx !== -1) {
      if ((snippet + statusSnippet).trim().length) {
        text = text.slice(0, idx) + insert + text.slice(idx);
      }
    }
  }
}

function insertAfterClassOpen(src, insert) {
  const re = /class\s+MainActivity\b[^{]*\{/m;
  const match = src.match(re);
  if (match) {
    const idx = src.indexOf(match[0]) + match[0].length;
    return { text: src.slice(0, idx) + "\n" + insert + src.slice(idx), inserted: true };
  }
  const idx = src.lastIndexOf("}");
  if (idx !== -1) {
    return { text: src.slice(0, idx) + insert + src.slice(idx), inserted: true };
  }
  return { text: src, inserted: false };
}

if (!isKotlin) {
  let hasBackPressField = originalText.includes("lastBackPressedAt");
  if (doubleClickExit && !originalText.includes("ConvertAPK: back-press state") && !hasBackPressField) {
    const result = insertAfterClassOpen(
      text,
      "    // ConvertAPK: back-press state\n" +
        "    private long lastBackPressedAt = 0L;\n"
    );
    text = result.text;
    if (result.inserted) {
      hasBackPressField = true;
    }
  }

  if (statusBarHidden && !originalText.includes("ConvertAPK: status bar helper")) {
    const helper = 
      "    // ConvertAPK: status bar helper\n" +
      "    private void applyStatusBarHidden() {\n" +
      "        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.R) {\n" +
      "            getWindow().setDecorFitsSystemWindows(false);\n" +
      "            android.view.WindowInsetsController controller = getWindow().getInsetsController();\n" +
      "            if (controller != null) {\n" +
      "                controller.hide(android.view.WindowInsets.Type.statusBars());\n" +
      "                controller.setSystemBarsBehavior(android.view.WindowInsetsController.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE);\n" +
      "            }\n" +
      "        } else {\n" +
      "            android.view.View decorView = getWindow().getDecorView();\n" +
      "            int flags = android.view.View.SYSTEM_UI_FLAG_FULLSCREEN\n" +
      "                | android.view.View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN\n" +
      "                | android.view.View.SYSTEM_UI_FLAG_LAYOUT_STABLE\n" +
      "                | android.view.View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY;\n" +
      "            decorView.setSystemUiVisibility(flags);\n" +
      "        }\n" +
      "    }\n";
    const result = insertAfterClassOpen(text, helper);
    text = result.text;
  }

  if (!statusBarHidden && statusBarIsWhite && !originalText.includes("ConvertAPK: status bar white")) {
    const helper =
      "    // ConvertAPK: status bar white\n" +
      "    private void applyStatusBarVisibleWhite() {\n" +
      "        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.R) {\n" +
      "            getWindow().setDecorFitsSystemWindows(true);\n" +
      "            android.view.WindowInsetsController controller = getWindow().getInsetsController();\n" +
      "            if (controller != null) {\n" +
      "                controller.setSystemBarsAppearance(android.view.WindowInsetsController.APPEARANCE_LIGHT_STATUS_BARS,\n" +
      "                    android.view.WindowInsetsController.APPEARANCE_LIGHT_STATUS_BARS);\n" +
      "            }\n" +
      "        } else {\n" +
      "            android.view.View decorView = getWindow().getDecorView();\n" +
      "            int flags = android.view.View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR\n" +
      "                | android.view.View.SYSTEM_UI_FLAG_LAYOUT_STABLE;\n" +
      "            decorView.setSystemUiVisibility(flags);\n" +
      "        }\n" +
      "        getWindow().setStatusBarColor(android.graphics.Color.parseColor(\"#FFFFFF\"));\n" +
      "    }\n";
    const result = insertAfterClassOpen(text, helper);
    text = result.text;
  }

  if (statusBarHidden && !text.includes("ConvertAPK: status bar focus")) {
    const focusHandler =
      "    // ConvertAPK: status bar focus\n" +
      "    @Override\n" +
      "    public void onWindowFocusChanged(boolean hasFocus) {\n" +
      "        super.onWindowFocusChanged(hasFocus);\n" +
      "        if (hasFocus) {\n" +
      "            applyStatusBarHidden();\n" +
      "        }\n" +
      "    }\n\n";
    const idx = text.lastIndexOf("}");
    if (idx !== -1) {
      text = text.slice(0, idx) + focusHandler + text.slice(idx);
    }
  }

  if (!statusBarHidden && statusBarIsWhite && !text.includes("ConvertAPK: status bar focus white")) {
    const focusHandler =
      "    // ConvertAPK: status bar focus white\n" +
      "    @Override\n" +
      "    public void onWindowFocusChanged(boolean hasFocus) {\n" +
      "        super.onWindowFocusChanged(hasFocus);\n" +
      "        if (hasFocus) {\n" +
      "            applyStatusBarVisibleWhite();\n" +
      "        }\n" +
      "    }\n\n";
    const idx = text.lastIndexOf("}");
    if (idx !== -1) {
      text = text.slice(0, idx) + focusHandler + text.slice(idx);
    }
  }

  if (doubleClickExit && hasBackPressField && !text.includes("ConvertAPK: double-click-exit")) {
    const onBackPressed =
      "    // ConvertAPK: double-click-exit\n" +
      "    @Override\n" +
      "    public void onBackPressed() {\n" +
      "        android.webkit.WebView webView = getBridge() != null ? getBridge().getWebView() : null;\n" +
      "        if (webView != null && webView.canGoBack()) {\n" +
      "            webView.goBack();\n" +
      "            return;\n" +
      "        }\n" +
      "        long now = System.currentTimeMillis();\n" +
      "        if (now - lastBackPressedAt < 2000) {\n" +
      "            super.onBackPressed();\n" +
      "        } else {\n" +
      "            lastBackPressedAt = now;\n" +
      "            Toast.makeText(this, \"Press back again to exit\", Toast.LENGTH_SHORT).show();\n" +
      "        }\n" +
      "    }\n\n";
    const idx = text.lastIndexOf("}");
    if (idx !== -1) {
      text = text.slice(0, idx) + onBackPressed + text.slice(idx);
    }
  }
}

writeText(mainActivity, text);

let themeNames = [];
const manifest = path.join(androidDir, "app", "src", "main", "AndroidManifest.xml");
if (fs.existsSync(manifest)) {
  let mtext = readText(manifest);
  let changed = false;

  // Ensure INTERNET permission (required for WebView apps)
  if (!mtext.includes("android.permission.INTERNET")) {
    const insertLine = "    <uses-permission android:name=\"android.permission.INTERNET\" />\n";
    if (mtext.includes("<application")) {
      mtext = mtext.replace("<application", insertLine + "<application");
    } else {
      const manifestTag = mtext.match(/<manifest\b[^>]*>/);
      const idx = manifestTag ? mtext.indexOf(manifestTag[0]) + manifestTag[0].length : mtext.indexOf(">");
      if (idx !== -1) {
        mtext = mtext.slice(0, idx + 1) + "\n" + insertLine + mtext.slice(idx + 1);
      }
    }
    changed = true;
  }

  // Screen orientation: portrait / landscape -> force on MainActivity, auto -> remove/skip.
  const orientationRaw = String(process.env.SCREEN_ORIENTATION || process.env.ORIENTATION || "")
    .trim()
    .toLowerCase();
  const desired =
    orientationRaw === "portrait" || orientationRaw === "landscape" ? orientationRaw : "auto";

  // Permissions: comma-separated, supports both short and full names.
  const permsRaw = String(process.env.PERMISSIONS || "").trim();
  const perms = permsRaw
    ? permsRaw.split(",").map((item) => item.trim()).filter(Boolean)
    : [];
  const fullPerms = perms.map((perm) => {
    if (perm.startsWith("android.permission.")) return perm;
    if (perm.includes(".")) return perm;
    return `android.permission.${perm}`;
  });

  const activityRe = /<activity\b[^>]*\bandroid:name="([^"]*MainActivity)"[^>]*>/g;
  mtext = mtext.replace(activityRe, (tag) => {
    let updated = tag;
    if (desired === "auto") {
      updated = updated.replace(/\sandroid:screenOrientation="[^"]*"/g, "");
    } else if (/\bandroid:screenOrientation=/.test(updated)) {
      updated = updated.replace(
        /\bandroid:screenOrientation="[^"]*"/,
        `android:screenOrientation="${desired}"`
      );
    } else {
      // Insert before the closing '>' (keep '/>' if it exists).
      updated = updated.replace(/\s*\/?>$/, (end) => {
        const suffix = end.includes("/>") ? " />" : ">";
        return ` android:screenOrientation="${desired}"${suffix}`;
      });
    }
    if (updated !== tag) changed = true;
    return updated;
  });

  // Insert requested permissions before <application> (without duplicates).
  const toAdd = [];
  for (const perm of fullPerms) {
    if (!perm) continue;
    if (mtext.includes(`android:name="${perm}"`)) continue;
    toAdd.push(`    <uses-permission android:name="${perm}" />`);
  }
  if (toAdd.length) {
    const block = toAdd.join("\n") + "\n";
    if (mtext.includes("<application")) {
      mtext = mtext.replace("<application", block + "<application", 1);
    } else {
      const manifestTag = mtext.match(/<manifest\b[^>]*>/);
      const idx = manifestTag ? mtext.indexOf(manifestTag[0]) + manifestTag[0].length : mtext.indexOf(">");
      if (idx !== -1) {
        mtext = mtext.slice(0, idx + 1) + "\n" + block + mtext.slice(idx + 1);
      }
    }
    changed = true;
  }

  themeNames = [];
  const themeRe = /android:theme="@(android:)?style\/([^"]+)"/g;
  let themeMatch;
  while ((themeMatch = themeRe.exec(mtext)) !== null) {
    if (themeMatch[2]) themeNames.push(themeMatch[2]);
  }

  if (changed) {
    writeText(manifest, mtext);
  }
}

// Status bar configuration (styles.xml/themes.xml)
// - STATUS_BAR_HIDDEN=true  -> fullscreen
// - STATUS_BAR_COLOR=transparent|#FFFFFF
// - STATUS_BAR_STYLE=dark|light (dark = dark icons for light background)
const styleFiles = [];
const resDir = path.join(androidDir, "app", "src", "main", "res");
if (fs.existsSync(resDir)) {
  const entries = fs.readdirSync(resDir, { withFileTypes: true });
  for (const entry of entries) {
    if (!entry.isDirectory()) continue;
    if (!entry.name.startsWith("values")) continue;
    for (const name of ["styles.xml", "themes.xml"]) {
      const candidate = path.join(resDir, entry.name, name);
      if (fs.existsSync(candidate)) {
        styleFiles.push(candidate);
      }
    }
  }
}

const hidden = String(process.env.STATUS_BAR_HIDDEN || "")
  .trim()
  .toLowerCase() === "true";
const style = String(process.env.STATUS_BAR_STYLE || "light").trim().toLowerCase(); // dark | light
let colorRaw = String(process.env.STATUS_BAR_COLOR || "transparent").trim();
if (!colorRaw) colorRaw = "transparent";
const colorLower = colorRaw.toLowerCase();
const statusBarColor =
  colorLower === "transparent" || colorLower === "@android:color/transparent"
    ? "@android:color/transparent"
    : colorLower === "white"
      ? "#FFFFFF"
      : colorRaw;
const lightStatusBar = style === "dark"; // windowLightStatusBar=true => dark icons
const styleNames = ["AppTheme", "AppTheme.NoActionBar", "Theme.App", "Theme.App.NoActionBar"];
if (typeof themeNames !== "undefined" && themeNames.length) {
  for (const name of themeNames) {
    if (!styleNames.includes(name)) {
      styleNames.push(name);
    }
  }
}

function escapeRegExp(str) {
  return String(str).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function patchStylesFile(filePath) {
  if (!fs.existsSync(filePath)) return false;
  let stext = readText(filePath);
  const original = stext;

  function patchStyleBlock(styleName, items) {
    const re = new RegExp(
      `(<style\\\\b[^>]*\\\\bname="${escapeRegExp(styleName)}"[^>]*>)([\\\\s\\\\S]*?)(</style>)`
    );
    const match = stext.match(re);
    if (!match) return false;
    let inner = match[2] || "";
    inner = inner.replace(/\s*<item\s+name="android:windowFullscreen">[\s\S]*?<\/item>\s*/g, "\n");
    inner = inner.replace(/\s*<item\s+name="android:windowTranslucentStatus">[\s\S]*?<\/item>\s*/g, "\n");
    inner = inner.replace(/\s*<item\s+name="android:statusBarColor">[\s\S]*?<\/item>\s*/g, "\n");
    inner = inner.replace(/\s*<item\s+name="android:windowLightStatusBar">[\s\S]*?<\/item>\s*/g, "\n");
    const insert = items.length ? "\n        " + items.join("\n        ") + "\n" : "\n";
    const updated = match[1] + insert + inner.replace(/^\n+/, "\n") + match[3];
    stext = stext.replace(match[0], updated);
    return true;
  }

  const items = [];
  if (hidden) {
    items.push('<item name="android:windowFullscreen">true</item>');
  } else {
    items.push('<item name="android:windowFullscreen">false</item>');
    items.push('<item name="android:windowTranslucentStatus">false</item>');
    items.push(`<item name="android:statusBarColor">${statusBarColor}</item>`);
    items.push(
      `<item name="android:windowLightStatusBar">${lightStatusBar ? "true" : "false"}</item>`
    );
  }

  let patched = false;
  for (const name of styleNames) {
    if (patchStyleBlock(name, items)) patched = true;
  }
  if (patched && stext !== original) {
    writeText(filePath, stext);
  }
  return patched;
}

for (const filePath of styleFiles) {
  patchStylesFile(filePath);
}

// Layout patch removed: rely on theme + window flags to avoid status bar overlap.
NODE

# ============================================
# 步骤 6: 配置 Android 项目
# ============================================
log_info "Step 6: 配置 Android 项目..."

# 创建 local.properties
cat > "$ANDROID_DIR/local.properties" << EOF
sdk.dir=$ANDROID_HOME
EOF

log_info "已创建 local.properties"

# 修改版本号
GRADLE_FILE="$ANDROID_DIR/app/build.gradle"
if [ ! -f "$GRADLE_FILE" ]; then
    GRADLE_FILE="$ANDROID_DIR/app/build.gradle.kts"
fi
if [ -f "$GRADLE_FILE" ]; then
    if echo "$GRADLE_FILE" | grep -q '\.kts$'; then
        sed -i "s/versionName[[:space:]]*=[[:space:]]*\".*\"/versionName = \"$VERSION_NAME\"/" "$GRADLE_FILE"
        sed -i "s/versionCode[[:space:]]*=[[:space:]]*[0-9]\+/versionCode = $VERSION_CODE/" "$GRADLE_FILE"
    else
        sed -i "s/versionName \".*\"/versionName \"$VERSION_NAME\"/" "$GRADLE_FILE"
        sed -i "s/versionCode .*/versionCode $VERSION_CODE/" "$GRADLE_FILE"
    fi
    log_info "???????"
fi

log_success "Android 项目配置完成"

# ============================================
# 步骤 7: 构建 Release APK
# ============================================
OUTPUT_FORMAT="${OUTPUT_FORMAT:-apk}"
OUTPUT_FORMAT="$(echo "$OUTPUT_FORMAT" | tr '[:upper:]' '[:lower:]')"
if [ "$OUTPUT_FORMAT" != "apk" ] && [ "$OUTPUT_FORMAT" != "aab" ]; then
    OUTPUT_FORMAT="apk"
fi

if [ "$OUTPUT_FORMAT" = "aab" ]; then
    log_info "Step 7: 构建 Release AAB..."
else
    log_info "Step 7: 构建 Release APK..."
fi

cd "$ANDROID_DIR"

# Ensure gradlew exists (web mode may miss wrapper if template copy failed)
if [ ! -f "gradlew" ]; then
    TEMPLATE_DIR="/workspace/templates/Tubbim"
    if [ -f "$TEMPLATE_DIR/gradlew" ]; then
        log_warning "gradlew missing; restoring from template"
        cp "$TEMPLATE_DIR/gradlew" .
        if [ -d "$TEMPLATE_DIR/gradle" ] && [ ! -d "gradle" ]; then
            cp -R "$TEMPLATE_DIR/gradle" .
        fi
    fi
fi
if [ ! -f "gradlew" ]; then
    log_error "gradlew not found in $ANDROID_DIR"
    exit 1
fi



# 给 gradlew 执行权限
chmod +x gradlew

# 如果已缓存 Gradle wrapper 分发包就复用，否则尝试从镜像预取
ensure_gradle_wrapper_dist

# 配置国内 Maven 镜像（降低 Maven Central 卡住的概率）
GRADLE_INIT_SCRIPT="/tmp/gradle-mirrors.init.gradle"
cat > "$GRADLE_INIT_SCRIPT" << 'EOF'
settingsEvaluated {
    it.dependencyResolutionManagement.repositoriesMode.set(RepositoriesMode.PREFER_PROJECT)
}
allprojects {
    repositories {
        maven { url = uri('https://maven.aliyun.com/repository/google') }
        maven { url = uri('https://maven.aliyun.com/repository/central') }
        maven { url = uri('https://maven.aliyun.com/repository/gradle-plugin') }
        maven { url = uri('https://maven.aliyun.com/repository/public') }
        google()
        mavenCentral()
    }
}
EOF
GRADLE_INIT_ARGS=(--init-script "$GRADLE_INIT_SCRIPT")

# 构建 release APK（带详细日志和优化参数）
log_info "开始 Gradle 构建（可能需要几分钟下载依赖）..."

# 设置 Gradle 参数
export GRADLE_OPTS="-Xmx2g -XX:MaxMetaspaceSize=512m -XX:+HeapDumpOnOutOfMemoryError"

if [ "$OUTPUT_FORMAT" = "aab" ]; then
    # 执行构建，添加 --info 查看详细日志，--stacktrace 查看错误栈
    ./gradlew bundleRelease "${GRADLE_INIT_ARGS[@]}" \
        --no-daemon \
        --stacktrace \
        --warning-mode all \
        -Dorg.gradle.jvmargs="-Xmx2048m -XX:MaxMetaspaceSize=512m" \
        -Dorg.gradle.parallel=false \
        -Dorg.gradle.caching=false
        
    check_error "AAB 构建失败"

    # 找到生成的 AAB
    AAB_PATH=$(find . -name "*.aab" -path "*/release/*" | head -n 1)

    if [ -z "$AAB_PATH" ]; then
        log_error "未找到生成的AAB文件"
        exit 1
    fi

    log_success "AAB 构建完成: $AAB_PATH"
else
    # 执行构建，添加 --info 查看详细日志，--stacktrace 查看错误栈
    ./gradlew assembleRelease "${GRADLE_INIT_ARGS[@]}" \
        --no-daemon \
        --stacktrace \
        --warning-mode all \
        -Dorg.gradle.jvmargs="-Xmx2048m -XX:MaxMetaspaceSize=512m" \
        -Dorg.gradle.parallel=false \
        -Dorg.gradle.caching=false
        
    check_error "APK 构建失败"

    # 找到生成的 APK
    APK_OUT_DIR="$(pwd)/app/build/outputs/apk/release"
    APK_PATH=$(find "$APK_OUT_DIR" -maxdepth 1 -name "*.apk" -type f 2>/dev/null | head -n 1)
    if [ -z "$APK_PATH" ]; then
        APK_PATH=$(find . -name "*.apk" -path "*/release/*" -type f | head -n 1)
    fi

    if [ -z "$APK_PATH" ] || [ ! -f "$APK_PATH" ]; then
        log_error "??????APK??"
        ls -la "$APK_OUT_DIR" 2>/dev/null || true
        exit 1
    fi

    log_success "APK ????: $APK_PATH"
fi

cd ..

# ============================================
# 步骤 8: 生成/使用密钥库
# ============================================
log_info "Step 8: 准备签名密钥..."

KEYSTORE_FILE="$KEYSTORE_DIR/release.keystore"

# 定义生成新keystore的函数
generate_keystore() {
    log_info "生成新的签名密钥..."
    keytool -genkeypair -v \
        -keystore "$KEYSTORE_FILE" \
        -alias "$KEY_ALIAS" \
        -keyalg RSA \
        -keysize 2048 \
        -validity 10000 \
        -storepass "$KEYSTORE_PASSWORD" \
        -keypass "$KEY_PASSWORD" \
        -dname "CN=APK Builder, OU=Dev, O=Company, L=City, ST=State, C=CN"
    check_error "密钥生成失败"
    log_success "签名密钥生成完成"
}

# 检查是否复用签名密钥
if [ "$KEYSTORE_REUSED" = "true" ]; then
    log_info "使用复用的签名密钥（用于应用更新）..."
    if [ ! -f "$KEYSTORE_FILE" ]; then
        log_error "复用签名模式下密钥库文件不存在！"
        exit 1
    fi
    # 验证密码
    if ! keytool -list -keystore "$KEYSTORE_FILE" -storepass "$KEYSTORE_PASSWORD" > /dev/null 2>&1; then
        log_error "复用签名模式下密钥库密码不匹配！请检查密码配置。"
        exit 1
    fi
    log_success "复用签名密钥验证成功"
else
    # 非复用模式：如果没有密钥库则生成新的
    if [ ! -f "$KEYSTORE_FILE" ]; then
        generate_keystore
    else
        log_info "检测到现有密钥库，验证密码..."
        # 验证keystore密码是否正确
        if keytool -list -keystore "$KEYSTORE_FILE" -storepass "$KEYSTORE_PASSWORD" > /dev/null 2>&1; then
            log_success "密钥库密码验证成功"
        else
            log_warning "密钥库密码不匹配，将重新生成密钥库..."
            rm -f "$KEYSTORE_FILE"
            generate_keystore
        fi
    fi
fi

# ============================================
# 步骤 9: 对齐 APK / 准备 AAB 输出
# ============================================
if [ "$OUTPUT_FORMAT" = "aab" ]; then
    log_info "Step 9: 准备 AAB 输出..."
else
    log_info "Step 9: 对齐 APK (zipalign)..."
fi

cd "$ANDROID_DIR"

FINAL_OUTPUT=""

if [ "$OUTPUT_FORMAT" = "aab" ]; then
    # 复制 AAB 到输出目录
    UNSIGNED_AAB="$OUTPUT_DIR/app-release-unsigned.aab"
    SIGNED_AAB="$OUTPUT_DIR/${APP_NAME}-v${VERSION_NAME}.aab"
    cp "$AAB_PATH" "$UNSIGNED_AAB"
    check_error "复制 AAB 失败"
    log_success "AAB 输出已准备"
else
    # 复制 APK 到临时位置
    UNSIGNED_APK="$OUTPUT_DIR/app-release-unsigned.apk"
    ALIGNED_APK="$OUTPUT_DIR/app-release-aligned.apk"
    SIGNED_APK="$OUTPUT_DIR/${APP_NAME}-v${VERSION_NAME}.apk"
    cp "$APK_PATH" "$UNSIGNED_APK"

    # 使用 zipalign 对齐
    zipalign -p -f -v 4 "$UNSIGNED_APK" "$ALIGNED_APK"
    check_error "APK 对齐失败"

    log_success "APK 对齐完成"
fi

# ============================================
# 步骤 10: 签名 APK / AAB
# ============================================
if [ "$OUTPUT_FORMAT" = "aab" ]; then
    log_info "Step 10: 签名 AAB (jarsigner)..."

    # AAB 使用 jarsigner（AAB 本质是 zip/jar 格式）
    jarsigner \
        -digestalg SHA-256 \
        -sigalg SHA256withRSA \
        -keystore "$KEYSTORE_FILE" \
        -storepass "$KEYSTORE_PASSWORD" \
        -keypass "$KEY_PASSWORD" \
        -signedjar "$SIGNED_AAB" \
        "$UNSIGNED_AAB" \
        "$KEY_ALIAS"
    check_error "AAB 签名失败"

    # 验证签名
    log_info "验证 AAB 签名..."
    jarsigner -verify -verbose -certs "$SIGNED_AAB"
    check_error "AAB 签名验证失败"

    log_success "AAB 签名完成"
    FINAL_OUTPUT="$SIGNED_AAB"
else
    log_info "Step 10: 签名 APK (apksigner)..."

    apksigner sign \
        --ks "$KEYSTORE_FILE" \
        --ks-key-alias "$KEY_ALIAS" \
        --ks-pass pass:"$KEYSTORE_PASSWORD" \
        --key-pass pass:"$KEY_PASSWORD" \
        --v1-signing-enabled true \
        --v2-signing-enabled true \
        --v3-signing-enabled true \
        --out "$SIGNED_APK" \
        "$ALIGNED_APK"
    check_error "APK 签名失败"

    # 验证签名
    log_info "验证 APK 签名..."
    apksigner verify --verbose "$SIGNED_APK"
    check_error "APK 签名验证失败"

    log_success "APK 签名完成"
    FINAL_OUTPUT="$SIGNED_APK"
fi

# ============================================
# 清理临时文件
# ============================================
log_info "清理临时文件..."
rm -f "$UNSIGNED_APK" "$ALIGNED_APK" "$UNSIGNED_AAB" 2>/dev/null || true

# ============================================
# 完成
# ============================================
echo ""
echo "============================================"
if [ "$OUTPUT_FORMAT" = "aab" ]; then
    log_success "🎉 AAB 构建完成!"
else
    log_success "🎉 APK 构建完成!"
fi
echo "============================================"
echo ""
echo "📦 输出文件: $FINAL_OUTPUT"
echo "📊 文件大小: $(du -h "$FINAL_OUTPUT" | cut -f1)"
echo ""
echo "============================================"
