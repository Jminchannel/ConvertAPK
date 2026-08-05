#!/bin/bash
# APK 构建主脚本

set -e

# 保存构建日志，便于排查失败原因
mkdir -p "${OUTPUT_DIR:-/workspace/output}"
LOG_FILE="${OUTPUT_DIR:-/workspace/output}/build.log"
exec > >(tee -a "$LOG_FILE") 2>&1

# 模板根目录可由后端在 Docker 数据卷模式下覆盖
TEMPLATE_ROOT="${TEMPLATES_DIR:-/workspace/templates}"

# 失败时复制 Gradle 问题报告到输出目录
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

SIGNATURE_VERIFY_TIMEOUT_SECONDS="${SIGNATURE_VERIFY_TIMEOUT_SECONDS:-120}"

# 后置签名校验只做摘要验证，并加超时保护，避免校验阶段长时间占用构建队列
runSignatureVerification() {
    local label="$1"
    shift
    local output=""
    local status=0

    set +e
    if command -v timeout >/dev/null 2>&1; then
        output="$(timeout "$SIGNATURE_VERIFY_TIMEOUT_SECONDS" "$@" 2>&1)"
        status=$?
    else
        log_warning "未找到 timeout 命令，$label 将不启用超时保护"
        output="$("$@" 2>&1)"
        status=$?
    fi
    set -e

    if [ -n "$output" ]; then
        printf '%s\n' "$output"
    fi

    if [ "$status" -eq 124 ] || [ "$status" -eq 137 ]; then
        log_error "$label 超过 ${SIGNATURE_VERIFY_TIMEOUT_SECONDS}s，已停止以避免阻塞构建队列"
        return 1
    fi
    if [ "$status" -ne 0 ]; then
        log_error "$label 执行失败"
        return "$status"
    fi
    return 0
}

prepareLauncherForegroundIcon() {
    local source_file="$1"
    local target_file="$2"
    if [ ! -f "$source_file" ]; then
        return 0
    fi

    mkdir -p "$(dirname "$target_file")"

    local tmp_dir
    tmp_dir="$(mktemp -d)"
    cat > "$tmp_dir/LauncherIconForegroundPadder.java" <<'JAVA'
import java.awt.Graphics2D;
import java.awt.Rectangle;
import java.awt.RenderingHints;
import java.awt.image.BufferedImage;
import java.io.File;
import javax.imageio.ImageIO;

public class LauncherIconForegroundPadder {
    private static final int CANVAS_SIZE = 432;
    private static final int ALPHA_THRESHOLD = 8;

    public static void main(String[] args) throws Exception {
        BufferedImage source = ImageIO.read(new File(args[0]));
        if (source == null) {
            throw new IllegalArgumentException("unsupported image");
        }

        Rectangle bounds = findVisibleBounds(source);
        int maxContentSize = Math.round(CANVAS_SIZE * 2f / 3f);
        double scale = Math.min((double) maxContentSize / bounds.width, (double) maxContentSize / bounds.height);
        int drawWidth = Math.max(1, (int) Math.round(bounds.width * scale));
        int drawHeight = Math.max(1, (int) Math.round(bounds.height * scale));
        int drawX = (CANVAS_SIZE - drawWidth) / 2;
        int drawY = (CANVAS_SIZE - drawHeight) / 2;

        BufferedImage output = new BufferedImage(CANVAS_SIZE, CANVAS_SIZE, BufferedImage.TYPE_INT_ARGB);
        Graphics2D graphics = output.createGraphics();
        graphics.setRenderingHint(RenderingHints.KEY_INTERPOLATION, RenderingHints.VALUE_INTERPOLATION_BICUBIC);
        graphics.setRenderingHint(RenderingHints.KEY_RENDERING, RenderingHints.VALUE_RENDER_QUALITY);
        graphics.setRenderingHint(RenderingHints.KEY_ANTIALIASING, RenderingHints.VALUE_ANTIALIAS_ON);
        graphics.drawImage(
            source,
            drawX,
            drawY,
            drawX + drawWidth,
            drawY + drawHeight,
            bounds.x,
            bounds.y,
            bounds.x + bounds.width,
            bounds.y + bounds.height,
            null
        );
        graphics.dispose();
        ImageIO.write(output, "png", new File(args[1]));
    }

    private static Rectangle findVisibleBounds(BufferedImage image) {
        int minX = image.getWidth();
        int minY = image.getHeight();
        int maxX = -1;
        int maxY = -1;
        for (int y = 0; y < image.getHeight(); y++) {
            for (int x = 0; x < image.getWidth(); x++) {
                int alpha = (image.getRGB(x, y) >>> 24) & 0xff;
                if (alpha <= ALPHA_THRESHOLD) {
                    continue;
                }
                if (x < minX) {
                    minX = x;
                }
                if (x > maxX) {
                    maxX = x;
                }
                if (y < minY) {
                    minY = y;
                }
                if (y > maxY) {
                    maxY = y;
                }
            }
        }
        if (maxX < minX || maxY < minY) {
            return new Rectangle(0, 0, image.getWidth(), image.getHeight());
        }
        return new Rectangle(minX, minY, maxX - minX + 1, maxY - minY + 1);
    }
}
JAVA

    if javac "$tmp_dir/LauncherIconForegroundPadder.java" >/dev/null 2>&1 \
        && java -cp "$tmp_dir" LauncherIconForegroundPadder "$source_file" "$target_file" >/dev/null 2>&1; then
        rm -rf "$tmp_dir"
        return 0
    fi

    log_warning "launcher icon safe padding failed; using original uploaded icon"
    cp "$source_file" "$target_file"
    rm -rf "$tmp_dir"
}

normalizeSha256() {
    printf '%s' "$1" | tr -d '\r' | sed -E 's/[^0-9A-Fa-f]//g' | tr '[:lower:]' '[:upper:]'
}

extractSha256FromText() {
    printf '%s\n' "$1" | tr -d '\r' | sed -n -E 's/.*SHA-?256( digest)?[[:space:]]*:[[:space:]]*([0-9A-Fa-f:]+).*/\2/p' | head -n 1
}

getKeystoreSha256() {
    local output=""
    output="$(keytool -list -v -keystore "$KEYSTORE_FILE" -alias "$KEY_ALIAS" -storepass "$KEYSTORE_PASSWORD" -keypass "$KEY_PASSWORD" 2>&1 || true)"
    local raw
    raw="$(extractSha256FromText "$output")"
    if [ -z "$raw" ]; then
        log_error "无法从 keystore 中解析 SHA-256 指纹"
        return 1
    fi
    normalizeSha256 "$raw"
}

getSignedApkSha256() {
    local output=""
    output="$(apksigner verify --verbose --print-certs "$SIGNED_APK" 2>&1 || true)"
    local raw
    raw="$(extractSha256FromText "$output")"
    if [ -z "$raw" ]; then
        log_error "无法从 APK 中解析 SHA-256 指纹"
        return 1
    fi
    normalizeSha256 "$raw"
}

getSignedAabSha256() {
    local output=""
    output="$(keytool -printcert -jarfile "$SIGNED_AAB" 2>&1 || true)"
    local raw
    raw="$(extractSha256FromText "$output")"
    if [ -z "$raw" ]; then
        log_error "无法从 AAB 中解析 SHA-256 指纹"
        return 1
    fi
    normalizeSha256 "$raw"
}

verifyOutputSignatureMatchesKeystore() {
    local keystoreSha256=""
    local artifactSha256=""
    keystoreSha256="$(getKeystoreSha256)" || exit 1
    if [ "$OUTPUT_FORMAT" = "aab" ]; then
        artifactSha256="$(getSignedAabSha256)" || exit 1
    else
        artifactSha256="$(getSignedApkSha256)" || exit 1
    fi
    log_info "keystore SHA-256: $keystoreSha256"
    log_info "artifact SHA-256: $artifactSha256"
    if [ "$keystoreSha256" != "$artifactSha256" ]; then
        log_error "签名校验失败：产物证书与当前 keystore 不一致"
        exit 1
    fi
    log_success "签名指纹校验通过"
}

runOfflineizeAssets() {
    local entryHtml="$1"
    local stepLabel="${2:-Step 1.5}"
    local preprocessedRaw
    preprocessedRaw="$(printf '%s' "${CDN_LOCALIZE_PREPROCESSED:-false}" | tr '[:upper:]' '[:lower:]')"
    if [ "$preprocessedRaw" = "true" ]; then
        log_info "CDN localize preprocessed, skip build-time offlineize"
        return 0
    fi
    local enabledRaw
    enabledRaw="$(printf '%s' "${CDN_LOCALIZE_ENABLED:-true}" | tr '[:upper:]' '[:lower:]')"
    if [ "$enabledRaw" != "true" ]; then
        log_info "CDN localize disabled, skip offlineize"
        return 0
    fi
    local scriptPath="/workspace/scripts/offlineize_html_assets.mjs"
    if [ ! -f "$scriptPath" ]; then
        log_warning "Offlineize script not found: $scriptPath"
        return 0
    fi
    if [ ! -f "$entryHtml" ]; then
        log_warning "Offlineize entry html not found: $entryHtml"
        return 0
    fi

    local -a cmd=(node "$scriptPath" "$entryHtml")
    local urlsJson="${CDN_LOCALIZE_URLS_JSON:-}"
    local allowCount=0
    if [ -n "$urlsJson" ] && [ "$urlsJson" != "[]" ]; then
        local allowUrls
        allowUrls="$(node -e 'const raw=String(process.argv[1]||"").trim();let data=[];try{data=JSON.parse(raw)}catch{};if(!Array.isArray(data)){process.exit(0)};const seen=new Set();for(const item of data){const url=String(item||"").trim();if(!url||seen.has(url))continue;seen.add(url);process.stdout.write(url+"\\n");}' "$urlsJson" 2>/dev/null || true)"
        if [ -n "$allowUrls" ]; then
            while IFS= read -r url; do
                [ -z "$url" ] && continue
                cmd+=(--allow-url "$url")
                allowCount=$((allowCount + 1))
            done <<< "$allowUrls"
        fi
    fi

    if [ "$allowCount" -gt 0 ]; then
        log_info "$stepLabel: offlineize selected remote assets ($allowCount urls)..."
    else
        log_info "$stepLabel: offlineize remote assets..."
    fi
    if "${cmd[@]}"; then
        log_info "Offlineize complete"
    else
        log_warning "Offlineize failed; keep original remote URLs"
    fi
}

normalizeWebCssForLegacyWebView() {
    local webDir="$1"
    if [ -z "$webDir" ] || [ ! -d "$webDir" ]; then
        return 0
    fi

    local cssCount
    cssCount="$(find "$webDir" -type f -name '*.css' | wc -l | tr -d '[:space:]')"
    if [ -z "$cssCount" ] || [ "$cssCount" = "0" ]; then
        return 0
    fi

    log_info "Step 1.6: 兼容旧版 WebView 颜色语法..."
    WEB_DIR="$webDir" node <<'NODE'
const fs = require("fs");
const path = require("path");

function walkCssFiles(dir, result) {
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  for (const entry of entries) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      walkCssFiles(full, result);
      continue;
    }
    if (entry.isFile() && full.toLowerCase().endsWith(".css")) {
      result.push(full);
    }
  }
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function linearToSrgb(value) {
  if (value <= 0.0031308) {
    return 12.92 * value;
  }
  return 1.055 * Math.pow(value, 1 / 2.4) - 0.055;
}

function parseAlpha(alphaRaw) {
  if (!alphaRaw) {
    return null;
  }
  const text = String(alphaRaw).trim();
  if (!text) {
    return null;
  }
  if (text.endsWith("%")) {
    const value = Number.parseFloat(text.slice(0, -1));
    if (Number.isFinite(value)) {
      return clamp(value / 100, 0, 1);
    }
    return null;
  }
  const value = Number.parseFloat(text);
  if (!Number.isFinite(value)) {
    return null;
  }
  return clamp(value, 0, 1);
}

function oklchToRgbCss(lPctRaw, chromaRaw, hueRaw, alphaRaw) {
  const lPct = Number.parseFloat(lPctRaw);
  const chroma = Number.parseFloat(chromaRaw);
  const hueDeg = Number.parseFloat(hueRaw);
  if (!Number.isFinite(lPct) || !Number.isFinite(chroma) || !Number.isFinite(hueDeg)) {
    return null;
  }

  const l = clamp(lPct / 100, 0, 1);
  const hueRad = (hueDeg * Math.PI) / 180;
  const a = chroma * Math.cos(hueRad);
  const b = chroma * Math.sin(hueRad);

  const l_ = l + 0.3963377774 * a + 0.2158037573 * b;
  const m_ = l - 0.1055613458 * a - 0.0638541728 * b;
  const s_ = l - 0.0894841775 * a - 1.2914855480 * b;

  const l3 = l_ * l_ * l_;
  const m3 = m_ * m_ * m_;
  const s3 = s_ * s_ * s_;

  const rLin = 4.0767416621 * l3 - 3.3077115913 * m3 + 0.2309699292 * s3;
  const gLin = -1.2684380046 * l3 + 2.6097574011 * m3 - 0.3413193965 * s3;
  const bLin = -0.0041960863 * l3 - 0.7034186147 * m3 + 1.7076147010 * s3;

  const r = Math.round(clamp(linearToSrgb(rLin), 0, 1) * 255);
  const g = Math.round(clamp(linearToSrgb(gLin), 0, 1) * 255);
  const bl = Math.round(clamp(linearToSrgb(bLin), 0, 1) * 255);

  const alpha = parseAlpha(alphaRaw);
  if (alpha === null) {
    return `rgb(${r}, ${g}, ${bl})`;
  }
  return `rgba(${r}, ${g}, ${bl}, ${alpha.toFixed(3).replace(/0+$/, "").replace(/\.$/, "")})`;
}

const webDir = process.env.WEB_DIR ? path.resolve(process.cwd(), process.env.WEB_DIR) : "";
if (!webDir || !fs.existsSync(webDir)) {
  process.exit(0);
}

const cssFiles = [];
walkCssFiles(webDir, cssFiles);

let patchedFiles = 0;
let patchedColors = 0;
const colorPattern = /oklch\(\s*([0-9]*\.?[0-9]+)%\s+([0-9]*\.?[0-9]+)\s+(-?[0-9]*\.?[0-9]+)(?:\s*\/\s*([0-9]*\.?[0-9]+%?))?\s*\)/gi;

for (const filePath of cssFiles) {
  const original = fs.readFileSync(filePath, "utf8");
  let localCount = 0;
  const patched = original.replace(colorPattern, (full, lPct, chroma, hue, alpha) => {
    const rgbCss = oklchToRgbCss(lPct, chroma, hue, alpha);
    if (!rgbCss) {
      return full;
    }
    localCount += 1;
    return rgbCss;
  });

  if (localCount > 0 && patched !== original) {
    fs.writeFileSync(filePath, patched, "utf8");
    patchedFiles += 1;
    patchedColors += localCount;
  }
}

if (patchedFiles > 0) {
  console.log(`[WebViewCompat] patched ${patchedColors} oklch colors in ${patchedFiles} css files`);
} else {
  console.log("[WebViewCompat] no oklch colors patched");
}
NODE
}

dedupeWebBuildAssets() {
    local webDir="$1"
    if [ -z "$webDir" ] || [ ! -d "$webDir" ]; then
        return 0
    fi

    log_info "Step 1.7: 去重重复静态资源..."
    WEB_DIR="$webDir" node <<'NODE'
const fs = require("fs");
const path = require("path");
const crypto = require("crypto");
const { TextDecoder } = require("util");

const webDir = process.env.WEB_DIR ? path.resolve(process.cwd(), process.env.WEB_DIR) : "";
if (!webDir || !fs.existsSync(webDir)) {
  process.exit(0);
}

const textExts = new Set([
  ".html",
  ".htm",
  ".js",
  ".mjs",
  ".cjs",
  ".css",
  ".json",
  ".txt",
  ".xml",
  ".svg",
  ".webmanifest",
]);
const maxTextBytes = 20 * 1024 * 1024;
const utf8Decoder = new TextDecoder("utf-8", { fatal: true });

function walkFiles(dir, out) {
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      walkFiles(fullPath, out);
      continue;
    }
    if (entry.isFile()) {
      out.push(fullPath);
    }
  }
}

function relPath(filePath) {
  return path.relative(webDir, filePath).split(path.sep).join("/");
}

function rankPath(relativePath) {
  const parts = relativePath.split("/").filter(Boolean);
  const firstPart = (parts[0] || "").toLowerCase();
  return {
    firstPartRank: firstPart === "assets" ? 1 : 0,
    depth: parts.length,
    length: relativePath.length,
    relativePath,
  };
}

function compareRank(leftPath, rightPath) {
  const left = rankPath(leftPath);
  const right = rankPath(rightPath);
  if (left.firstPartRank !== right.firstPartRank) return left.firstPartRank - right.firstPartRank;
  if (left.depth !== right.depth) return left.depth - right.depth;
  if (left.length !== right.length) return left.length - right.length;
  return left.relativePath.localeCompare(right.relativePath);
}

function hashFileSha256(filePath) {
  const fd = fs.openSync(filePath, "r");
  const hash = crypto.createHash("sha256");
  const buffer = Buffer.allocUnsafe(1024 * 1024);
  try {
    while (true) {
      const readBytes = fs.readSync(fd, buffer, 0, buffer.length, null);
      if (readBytes <= 0) break;
      hash.update(buffer.subarray(0, readBytes));
    }
  } finally {
    fs.closeSync(fd);
  }
  return hash.digest("hex");
}

function isTextCandidate(filePath) {
  const ext = path.extname(filePath).toLowerCase();
  if (!textExts.has(ext)) return false;
  try {
    const st = fs.statSync(filePath);
    if (!st.isFile()) return false;
    return st.size > 0 && st.size <= maxTextBytes;
  } catch {
    return false;
  }
}

function readUtf8Strict(filePath) {
  try {
    const raw = fs.readFileSync(filePath);
    if (!raw || raw.length <= 0) return null;
    if (raw.includes(0x00)) return null;
    return utf8Decoder.decode(raw);
  } catch {
    return null;
  }
}

function buildReferencePairs(sourceRelative, targetRelative) {
  const source = String(sourceRelative || "").replace(/\\/g, "/").replace(/^\/+/, "");
  const target = String(targetRelative || "").replace(/\\/g, "/").replace(/^\/+/, "");
  const pairs = new Map();
  if (!source || !target || source === target) {
    return pairs;
  }
  const addPair = (from, to) => {
    if (!from || !to || from === to) return;
    pairs.set(from, to);
  };
  addPair(`/${source}`, `/${target}`);
  addPair(`./${source}`, `./${target}`);
  addPair(source, target);
  addPair(`\\/${source}`, `\\/${target}`);
  return pairs;
}

const allFiles = [];
walkFiles(webDir, allFiles);

const groupedByDigest = new Map();
for (const filePath of allFiles) {
  let st;
  try {
    st = fs.statSync(filePath);
  } catch {
    continue;
  }
  if (!st.isFile() || st.size <= 0) continue;
  let digest = "";
  try {
    digest = hashFileSha256(filePath);
  } catch {
    continue;
  }
  if (!digest) continue;
  const key = `${st.size}:${digest}`;
  const list = groupedByDigest.get(key) || [];
  list.push(filePath);
  groupedByDigest.set(key, list);
}

const dedupeJobs = [];
const oldReferences = new Set();
for (const files of groupedByDigest.values()) {
  if (!Array.isArray(files) || files.length < 2) continue;
  const ordered = [...files].sort((left, right) => compareRank(relPath(left), relPath(right)));
  const canonical = ordered[0];
  const canonicalRelative = relPath(canonical);
  for (const duplicatePath of ordered.slice(1)) {
    const duplicateRelative = relPath(duplicatePath);
    if (!duplicateRelative || duplicateRelative === canonicalRelative) continue;
    const refPairs = buildReferencePairs(duplicateRelative, canonicalRelative);
    if (refPairs.size <= 0) continue;
    dedupeJobs.push({
      duplicatePath,
      refPairs,
    });
    for (const oldRef of refPairs.keys()) {
      oldReferences.add(oldRef);
    }
  }
}

if (dedupeJobs.length <= 0) {
  console.log("[WebDedupe] no duplicated assets found");
  process.exit(0);
}

const replacementMap = new Map();
for (const job of dedupeJobs) {
  for (const [oldRef, newRef] of job.refPairs.entries()) {
    replacementMap.set(oldRef, newRef);
  }
}
const replacements = [...replacementMap.entries()].sort((a, b) => b[0].length - a[0].length);

let replacedFiles = 0;
let replacedRefs = 0;
for (const filePath of allFiles) {
  if (!isTextCandidate(filePath)) continue;
  const content = readUtf8Strict(filePath);
  if (content === null) continue;
  let updated = content;
  let localCount = 0;
  for (const [oldRef, newRef] of replacements) {
    if (oldRef === newRef || !updated.includes(oldRef)) continue;
    const parts = updated.split(oldRef);
    const hitCount = parts.length - 1;
    if (hitCount <= 0) continue;
    updated = parts.join(newRef);
    localCount += hitCount;
  }
  if (localCount > 0 && updated !== content) {
    fs.writeFileSync(filePath, updated, "utf8");
    replacedFiles += 1;
    replacedRefs += localCount;
  }
}

const remainingRefs = new Set();
const needles = [...oldReferences].sort((a, b) => b.length - a.length);
for (const filePath of allFiles) {
  if (!isTextCandidate(filePath)) continue;
  const content = readUtf8Strict(filePath);
  if (content === null) continue;
  for (const needle of needles) {
    if (!remainingRefs.has(needle) && content.includes(needle)) {
      remainingRefs.add(needle);
    }
  }
  if (remainingRefs.size >= oldReferences.size) {
    break;
  }
}

let removedFiles = 0;
let removedBytes = 0;
let skippedFiles = 0;
for (const job of dedupeJobs) {
  const stillReferenced = [...job.refPairs.keys()].some((oldRef) => remainingRefs.has(oldRef));
  if (stillReferenced) {
    skippedFiles += 1;
    continue;
  }
  try {
    const st = fs.statSync(job.duplicatePath);
    if (st.isFile()) {
      removedBytes += st.size;
    }
    fs.unlinkSync(job.duplicatePath);
    removedFiles += 1;
  } catch {
    skippedFiles += 1;
  }
}

if (removedFiles > 0) {
  const savedMb = (removedBytes / (1024 * 1024)).toFixed(2);
  console.log(`[WebDedupe] removed ${removedFiles} duplicated files, saved ~${savedMb} MB, replaced ${replacedRefs} refs`);
} else {
  console.log("[WebDedupe] duplicated files detected but none removed");
}
if (skippedFiles > 0) {
  console.log(`[WebDedupe] skipped ${skippedFiles} files because old references still exist`);
}
if (replacedFiles > 0 && removedFiles <= 0) {
  console.log(`[WebDedupe] updated ${replacedFiles} text files but did not remove duplicates`);
}
NODE
}

normalizeProjectRootForBuild() {
    local projectRoot="$1"
    if [ -z "$projectRoot" ] || [ ! -d "$projectRoot" ]; then
        echo "$projectRoot"
        return 0
    fi
    case "$projectRoot" in
        *"#"*)
            local safeRoot="$PROJECT_DIR/__convertapk_safe_root"
            log_warning "检测到项目路径包含 #，将复制到安全目录后再构建" >&2
            rm -rf "$safeRoot"
            mkdir -p "$safeRoot"
            cp -R "$projectRoot"/. "$safeRoot"/
            log_info "安全构建路径: $safeRoot" >&2
            echo "$safeRoot"
            return 0
            ;;
    esac
    echo "$projectRoot"
}

findAlternativeViteRoot() {
    local currentRoot="$1"
    local packageJson=""
    while IFS= read -r packageJson; do
        local candidateRoot
        candidateRoot="$(dirname "$packageJson")"
        if [ "$candidateRoot" = "$currentRoot" ]; then
            continue
        fi
        if [ -f "$candidateRoot/index.html" ]; then
            echo "$candidateRoot"
            return 0
        fi
    done < <(find "$PROJECT_DIR" -name "package.json" -type f \
        -not -path "*/node_modules/*" \
        -not -path "*/android/*" \
        -not -path "*/.git/*")
    return 1
}

findNativeAndroidRoot() {
    local searchRoot="$1"
    local settingsFile=""
    while IFS= read -r settingsFile; do
        local candidateRoot
        candidateRoot="$(dirname "$settingsFile")"
        if [ -f "$candidateRoot/app/src/main/AndroidManifest.xml" ] && \
           { [ -f "$candidateRoot/app/build.gradle" ] || [ -f "$candidateRoot/app/build.gradle.kts" ]; }; then
            echo "$candidateRoot"
            return 0
        fi
    done < <(find "$searchRoot" \( -name "settings.gradle" -o -name "settings.gradle.kts" \) -type f \
        -not -path "*/node_modules/*" \
        -not -path "*/.git/*" \
        -not -path "*/__MACOSX/*" | sort)
    return 1
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

version_gte() {
    local current="$1"
    local required="$2"
    if [ -z "$current" ] || [ -z "$required" ]; then
        return 1
    fi
    [ "$(printf '%s\n%s\n' "$required" "$current" | sort -V | head -n 1)" = "$required" ]
}

detect_android_gradle_plugin_version() {
    local version=""
    if [ -f "gradle/libs.versions.toml" ]; then
        version="$(sed -n -E 's/^[[:space:]]*agp[[:space:]]*=[[:space:]]*"([^"]+)".*/\1/p' gradle/libs.versions.toml | head -n 1)"
    fi
    if [ -z "$version" ]; then
        version="$(grep -RhoE 'com\.android\.(application|library)[^0-9\r\n]*[0-9]+(\.[0-9]+){1,3}' \
            build.gradle build.gradle.kts settings.gradle settings.gradle.kts app/build.gradle app/build.gradle.kts 2>/dev/null \
            | sed -n -E 's/.*([0-9]+(\.[0-9]+){1,3}).*/\1/p' \
            | head -n 1)"
    fi
    printf '%s' "$version"
}

extract_gradle_distribution_version() {
    printf '%s' "$1" | sed -n -E 's#.*gradle-([0-9]+(\.[0-9]+){1,3})-.*#\1#p' | head -n 1
}

get_gradle_wrapper_distribution_url() {
    local wrapper_props="$1"
    if [ ! -f "$wrapper_props" ]; then
        return 0
    fi
    grep -E '^distributionUrl=' "$wrapper_props" | head -n 1 | cut -d'=' -f2-
}

select_default_gradle_distribution_url() {
    local agp_version
    agp_version="$(detect_android_gradle_plugin_version)"
    if version_gte "$agp_version" "9.0.0"; then
        # AGP 9.x 需要 Gradle 9，避免补齐 wrapper 后被旧版 Gradle 拦截。
        printf '%s' "https://services.gradle.org/distributions/gradle-9.3.1-bin.zip"
        return 0
    fi

    # 兜底使用兼容 JDK 21 的 Gradle 8 版本，只有项目 wrapper 过低或缺失时才使用。
    printf '%s' "https://services.gradle.org/distributions/gradle-8.14.3-all.zip"
}

resolve_gradle_distribution_url() {
    local wrapper_props="${1:-}"
    if [ -n "${CONVERTAPK_GRADLE_DISTRIBUTION_URL:-}" ]; then
        printf '%s' "$CONVERTAPK_GRADLE_DISTRIBUTION_URL"
        return 0
    fi

    local agp_version
    agp_version="$(detect_android_gradle_plugin_version)"
    local current_url=""
    local current_version=""
    if [ -n "$wrapper_props" ]; then
        current_url="$(get_gradle_wrapper_distribution_url "$wrapper_props")"
        current_version="$(extract_gradle_distribution_version "$current_url")"
    fi

    if [ -n "$current_url" ] && [ -n "$current_version" ] && [ "${CONVERTAPK_GRADLE_FORCE_UPGRADE:-0}" != "1" ]; then
        if version_gte "$agp_version" "9.0.0"; then
            if version_gte "$current_version" "9.0.0"; then
                printf '%s' "$current_url"
                return 0
            fi
        else
            local min_gradle_version="${CONVERTAPK_GRADLE_MIN_VERSION:-8.5}"
            if version_gte "$current_version" "$min_gradle_version"; then
                printf '%s' "$current_url"
                return 0
            fi
        fi
    fi

    select_default_gradle_distribution_url
}

patch_gradle_wrapper_version() {
    local seen="false"
    for wrapper_props in "android/gradle/wrapper/gradle-wrapper.properties" "gradle/wrapper/gradle-wrapper.properties"; do
        if [ ! -f "$wrapper_props" ]; then
            continue
        fi
        seen="true"
        local current_url
        local target_url
        local safe_url
        current_url="$(get_gradle_wrapper_distribution_url "$wrapper_props")"
        target_url="$(resolve_gradle_distribution_url "$wrapper_props")"

        if [ -n "$current_url" ] && [ "$current_url" = "$target_url" ]; then
            log_info "保留项目自带 Gradle wrapper：$wrapper_props -> $target_url"
            continue
        fi

        safe_url="$target_url"
        safe_url="${safe_url//\\/\\\\}"
        safe_url="${safe_url//:/\\:}"
        safe_url="${safe_url//\//\\/}"

        if grep -q '^distributionUrl=' "$wrapper_props"; then
            sed -i -E "s#^distributionUrl=.*#distributionUrl=$safe_url#g" "$wrapper_props"
        else
            printf '\ndistributionUrl=%s\n' "$safe_url" >> "$wrapper_props"
        fi
        sed -i '/^distributionSha256Sum=/d' "$wrapper_props"
        log_info "已调整 Gradle wrapper：$wrapper_props -> $target_url"
    done

    if [ "$seen" != "true" ]; then
        log_warning "未找到 gradle-wrapper.properties，跳过 Gradle 版本锁定"
    fi
}

is_valid_gradle_wrapper_jar() {
    local jar_file="$1"
    if [ ! -s "$jar_file" ]; then
        return 1
    fi
    if ! unzip -tq "$jar_file" >/dev/null 2>&1; then
        return 1
    fi
    if ! unzip -l "$jar_file" 2>/dev/null | grep -q "org/gradle/wrapper/GradleWrapperMain.class"; then
        return 1
    fi
    return 0
}

ensure_gradle_wrapper_jar() {
    local wrapper_props=""
    local wrapper_jar=""
    for candidate in "gradle/wrapper/gradle-wrapper.properties" "android/gradle/wrapper/gradle-wrapper.properties"; do
        if [ -f "$candidate" ]; then
            wrapper_props="$candidate"
            break
        fi
    done
    for candidate in "gradle/wrapper/gradle-wrapper.jar" "android/gradle/wrapper/gradle-wrapper.jar"; do
        if [ -f "$candidate" ]; then
            wrapper_jar="$candidate"
            break
        fi
    done

    if [ -z "$wrapper_props" ] && [ -z "$wrapper_jar" ]; then
        log_warning "未找到 Gradle wrapper 文件，跳过 gradle-wrapper.jar 校验"
        return 0
    fi

    if [ -z "$wrapper_jar" ] && [ -n "$wrapper_props" ]; then
        wrapper_jar="$(dirname "$wrapper_props")/gradle-wrapper.jar"
    fi

    if [ -n "$wrapper_jar" ] && is_valid_gradle_wrapper_jar "$wrapper_jar"; then
        return 0
    fi

    log_warning "检测到 gradle-wrapper.jar 缺失或损坏，开始自动修复..."

    local template_candidates=(
        "$TEMPLATE_ROOT/Tubbim/gradle/wrapper/gradle-wrapper.jar"
        "$TEMPLATE_ROOT/HTML2APK/gradle/wrapper/gradle-wrapper.jar"
    )
    local template_jar=""
    for src in "${template_candidates[@]}"; do
        if [ -f "$src" ] && is_valid_gradle_wrapper_jar "$src"; then
            template_jar="$src"
            break
        fi
    done

    if [ -n "$template_jar" ]; then
        mkdir -p "$(dirname "$wrapper_jar")"
        cp -f "$template_jar" "$wrapper_jar"
        if is_valid_gradle_wrapper_jar "$wrapper_jar"; then
            log_success "已使用模板修复 gradle-wrapper.jar"
            return 0
        fi
    fi

    local wrapper_version="8.14.3"
    if [ -n "$wrapper_props" ] && [ -f "$wrapper_props" ]; then
        local dist_url_raw
        dist_url_raw="$(grep -E '^distributionUrl=' "$wrapper_props" | head -n 1 | cut -d'=' -f2-)"
        if [ -n "$dist_url_raw" ]; then
            local dist_url="${dist_url_raw//\\:/:}"
            local parsed_version
            parsed_version="$(printf '%s' "$dist_url" | sed -n -E 's#.*gradle-([0-9]+(\.[0-9]+)+)-.*#\1#p' | head -n 1)"
            if [ -n "$parsed_version" ]; then
                wrapper_version="$parsed_version"
            fi
        fi
    fi

    local urls=(
        "https://raw.githubusercontent.com/gradle/gradle/v${wrapper_version}/gradle/wrapper/gradle-wrapper.jar"
        "https://raw.githubusercontent.com/gradle/gradle/v8.14.3/gradle/wrapper/gradle-wrapper.jar"
    )
    local tmp_file="${wrapper_jar}.tmp.$$"
    rm -f "$tmp_file"
    for url in "${urls[@]}"; do
        log_info "尝试下载 gradle-wrapper.jar: $url"
        if curl -fL --connect-timeout 10 --retry 3 --retry-delay 2 -o "$tmp_file" "$url"; then
            if is_valid_gradle_wrapper_jar "$tmp_file"; then
                mkdir -p "$(dirname "$wrapper_jar")"
                mv "$tmp_file" "$wrapper_jar"
                chmod 644 "$wrapper_jar" 2>/dev/null || true
                log_success "已下载并修复 gradle-wrapper.jar"
                return 0
            fi
            rm -f "$tmp_file"
        fi
    done
    rm -f "$tmp_file"
    log_error "gradle-wrapper.jar 自动修复失败，请重新上传项目或移除 ZIP 内损坏的 android 目录"
    exit 1
}

# ============================================
# 调试：打印所有环境变量
# ============================================
log_info "========== 环境变量调试 =========="
log_info "OUTPUT_FORMAT 原始值: '${OUTPUT_FORMAT:-未设置}'"
log_info "APP_NAME: '${APP_NAME:-未设置}'"
log_info "PACKAGE_NAME: '${PACKAGE_NAME:-未设置}'"
log_info "DOWNLOAD_MODE: '${DOWNLOAD_MODE:-未设置}'"
log_info "WEB_FILL_MODE: '${WEB_FILL_MODE:-未设置}'"
log_info "=================================="

TASK_MODE=${TASK_MODE:-convert}
# Normalize TASK_MODE aggressively to avoid hidden chars/CRLF causing mismatches.
TASK_MODE="$(printf '%s' "$TASK_MODE" | tr '[:upper:]' '[:lower:]' | tr -cd 'a-z')"
ANDROID_DIR="android"
PROJECT_DIR="${PROJECT_DIR:-/workspace/project}"

# Fallback inference if TASK_MODE is missing or unrecognized.
case "$TASK_MODE" in
    web|html|convert|native) ;;
    *)
        if [ -n "$INPUT_DIR" ] && find "$INPUT_DIR" -maxdepth 1 -type f \( -name "*.html" -o -name "*.htm" \) | head -n 1 | grep -q .; then
            log_warning "TASK_MODE '$TASK_MODE' unrecognized; falling back to html (HTML file found in input)"
            TASK_MODE="html"
        elif [ -n "$WEB_URL" ]; then
            log_warning "TASK_MODE '$TASK_MODE' unrecognized; falling back to web (WEB_URL provided)"
            TASK_MODE="web"
        else
            log_warning "TASK_MODE '$TASK_MODE' unrecognized; falling back to convert"
            TASK_MODE="convert"
        fi
        ;;
esac

log_info "TASK_MODE: '${TASK_MODE}'"

# ============================================
# 步骤 0: 准备工作
# ============================================
# Step 0: prepare
# ============================================
log_info "Step 0: 准备构建环境..."

if [ "$TASK_MODE" = "web" ]; then
    log_info "Step 1: 准备 Web 模板..."
    TEMPLATE_DIR="$TEMPLATE_ROOT/Tubbim"
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
const webViewUaRaw = String(process.env.WEBVIEW_UA || 'android').trim().toLowerCase();
const webViewUa = (webViewUaRaw === 'pc' || webViewUaRaw === 'desktop' || webViewUaRaw === 'windows') ? 'pc' : 'android';
const statusBarHidden = String(process.env.STATUS_BAR_HIDDEN || '').trim().toLowerCase() === 'true';
const taskMode = String(process.env.TASK_MODE || 'convert').trim().toLowerCase();
let statusBarColorRaw = String(process.env.STATUS_BAR_COLOR || 'white').trim().toLowerCase();
if (!statusBarHidden && taskMode === 'convert' && (statusBarColorRaw === 'transparent' || statusBarColorRaw === '@android:color/transparent')) {
  statusBarColorRaw = 'white';
}
const statusBarStyle = String(process.env.STATUS_BAR_STYLE || 'light').trim().toLowerCase();
const lightStatusBarIcons = statusBarStyle === 'dark';
const statusBarBackground =
  statusBarHidden
    ? 'transparent'
    : (statusBarColorRaw === '@android:color/transparent'
      ? 'transparent'
      : (statusBarColorRaw === 'white' ? '#FFFFFF' : statusBarColorRaw));
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
  gtext = gtext.replace(/buildConfigField\(\s*"String"\s*,\s*"WEBVIEW_UA"[\s\S]*?\)/, `buildConfigField("String", "WEBVIEW_UA", "\\"${webViewUa}\\"")`);
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
            prepareLauncherForegroundIcon "$INPUT_DIR/logo.png" "$drawable_dir/ic_launcher_foreground.png"
            log_info "Template launcher icon updated with adaptive safe padding"
        fi
    fi

    cd "$PROJECT_ROOT"
    log_success "Step 0 done"
elif [ "$TASK_MODE" = "html" ]; then
    log_info "Step 1: 准备 HTML 模板..."
    TEMPLATE_DIR="$TEMPLATE_ROOT/HTML2APK"
    if [ ! -d "$TEMPLATE_DIR" ]; then
        log_error "HTML template not found: $TEMPLATE_DIR"
        exit 1
    fi
    rm -rf "$PROJECT_DIR"
    mkdir -p "$PROJECT_DIR"
    cp -R "$TEMPLATE_DIR"/. "$PROJECT_DIR"/
    PROJECT_ROOT="$PROJECT_DIR"
    ANDROID_DIR="."

    HTML_FILE="$INPUT_DIR/index.html"
    if [ ! -f "$HTML_FILE" ]; then
        HTML_FILE=$(find "$INPUT_DIR" -maxdepth 1 -type f \( -name "*.html" -o -name "*.htm" \) | head -n 1)
    fi
    if [ -z "$HTML_FILE" ]; then
        log_error "HTML file not found in $INPUT_DIR"
        exit 1
    fi

    HTML_ROOT="$PROJECT_ROOT/html2apkdemo"
    rm -rf "$HTML_ROOT"
    mkdir -p "$HTML_ROOT"
    HTML_ASSETS_DIR="$INPUT_DIR/html_assets"
    if [ -d "$HTML_ASSETS_DIR" ] && [ -f "$HTML_ASSETS_DIR/index.html" ]; then
        cp -R "$HTML_ASSETS_DIR"/. "$HTML_ROOT"/
        log_info "Copied full HTML assets from: $HTML_ASSETS_DIR"
    else
        cp "$HTML_FILE" "$HTML_ROOT/index.html"
    fi

    LIBS_ZIP="$INPUT_DIR/libs.zip"
    if [ -f "$LIBS_ZIP" ]; then
        mkdir -p "$HTML_ROOT/libs"
        TMP_LIBS_DIR="/tmp/html_libs_$$"
        rm -rf "$TMP_LIBS_DIR"
        mkdir -p "$TMP_LIBS_DIR"
        unzip -q "$LIBS_ZIP" -d "$TMP_LIBS_DIR"
        if [ $(find "$TMP_LIBS_DIR" -mindepth 1 -maxdepth 1 -type d | wc -l) -eq 1 ] && [ $(find "$TMP_LIBS_DIR" -mindepth 1 -maxdepth 1 -type f | wc -l) -eq 0 ]; then
            SRC_DIR=$(find "$TMP_LIBS_DIR" -mindepth 1 -maxdepth 1 -type d | head -n 1)
            cp -R "$SRC_DIR"/. "$HTML_ROOT/libs/"
        else
            cp -R "$TMP_LIBS_DIR"/. "$HTML_ROOT/libs/"
        fi
        rm -rf "$TMP_LIBS_DIR"
    fi

    runOfflineizeAssets "$HTML_ROOT/index.html" "Step 1.5"

    PROJECT_ROOT="$PROJECT_ROOT" node << 'NODE'
const fs = require('fs');
const path = require('path');

const projectRoot = process.env.PROJECT_ROOT || process.cwd();
const appName = process.env.APP_NAME || 'MyApp';
const packageName = process.env.PACKAGE_NAME || 'com.example.app';
const versionName = process.env.VERSION_NAME || '1.0.0';
const versionCode = process.env.VERSION_CODE || '1';
const statusBarHidden = String(process.env.STATUS_BAR_HIDDEN || '').trim().toLowerCase() === 'true';
const taskMode = String(process.env.TASK_MODE || 'convert').trim().toLowerCase();
let statusBarColorRaw = String(process.env.STATUS_BAR_COLOR || 'white').trim().toLowerCase();
if (!statusBarHidden && taskMode === 'convert' && (statusBarColorRaw === 'transparent' || statusBarColorRaw === '@android:color/transparent')) {
  statusBarColorRaw = 'white';
}
const statusBarStyle = String(process.env.STATUS_BAR_STYLE || 'light').trim().toLowerCase();
const lightStatusBarIcons = statusBarStyle === 'dark';
const statusBarBackground =
  statusBarHidden
    ? 'transparent'
    : (statusBarColorRaw === '@android:color/transparent'
      ? 'transparent'
      : (statusBarColorRaw === 'white' ? '#FFFFFF' : statusBarColorRaw));
const doubleClickExit = String(process.env.DOUBLE_CLICK_EXIT || '').trim().toLowerCase() !== 'false';
const orientationRaw = String(process.env.SCREEN_ORIENTATION || '').trim().toLowerCase();
const screenOrientation = orientationRaw === 'portrait' || orientationRaw === 'landscape' ? orientationRaw : 'auto';
const downloadModeRaw = String(process.env.DOWNLOAD_MODE || '').trim().toLowerCase();
const downloadMode = downloadModeRaw === 'silent' ? 'silent' : 'picker';
const webFillModeRaw = String(process.env.WEB_FILL_MODE || '').trim().toLowerCase();
const webFillMode = webFillModeRaw === 'cover' ? 'cover' : 'contain';

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
  const ensureBuildConfigField = (source, typeName, keyName, line, anchors = []) => {
    const selfPattern = new RegExp(`buildConfigField\\(\\s*"${typeName}"\\s*,\\s*"${keyName}"[\\s\\S]*?\\)`);
    if (selfPattern.test(source)) {
      return source.replace(selfPattern, line);
    }
    for (const anchor of anchors) {
      const anchorPattern = new RegExp(`buildConfigField\\(\\s*"[^"]+"\\s*,\\s*"${anchor}"[\\s\\S]*?\\)`);
      if (anchorPattern.test(source)) {
        return source.replace(anchorPattern, (m) => `${m}\n        ${line}`);
      }
    }
    return source.replace(/defaultConfig\s*\{/, (m) => `${m}\n        ${line}`);
  };
  gtext = gtext.replace(/applicationId\s*=\s*"[^"]+"/, `applicationId = "${packageName}"`);
  gtext = gtext.replace(/versionCode\s*=\s*\d+/, `versionCode = ${versionCode}`);
  gtext = gtext.replace(/versionName\s*=\s*"[^"]+"/, `versionName = "${versionName}"`);
  gtext = gtext.replace(/buildConfigField\(\s*"boolean"\s*,\s*"HIDE_STATUS_BAR"[\s\S]*?\)/, `buildConfigField("boolean", "HIDE_STATUS_BAR", "${statusBarHidden}")`);
  gtext = gtext.replace(/buildConfigField\(\s*"String"\s*,\s*"STATUS_BAR_BACKGROUND"[\s\S]*?\)/, `buildConfigField("String", "STATUS_BAR_BACKGROUND", "\\"${statusBarBackground}\\"")`);
  gtext = gtext.replace(/buildConfigField\(\s*"boolean"\s*,\s*"LIGHT_STATUS_BAR_ICONS"[\s\S]*?\)/, `buildConfigField("boolean", "LIGHT_STATUS_BAR_ICONS", "${lightStatusBarIcons}")`);
  gtext = gtext.replace(/buildConfigField\(\s*"boolean"\s*,\s*"DOUBLE_CLICK_EXIT"[\s\S]*?\)/, `buildConfigField("boolean", "DOUBLE_CLICK_EXIT", "${doubleClickExit}")`);
  gtext = ensureBuildConfigField(
    gtext,
    "String",
    "SCREEN_ORIENTATION",
    `buildConfigField("String", "SCREEN_ORIENTATION", "\\"${screenOrientation}\\"")`,
    ["DOUBLE_CLICK_EXIT", "LIGHT_STATUS_BAR_ICONS", "STATUS_BAR_BACKGROUND"]
  );
  gtext = ensureBuildConfigField(
    gtext,
    "String",
    "DOWNLOAD_MODE",
    `buildConfigField("String", "DOWNLOAD_MODE", "\\"${downloadMode}\\"")`,
    ["SCREEN_ORIENTATION", "DOUBLE_CLICK_EXIT", "LIGHT_STATUS_BAR_ICONS"]
  );
  gtext = ensureBuildConfigField(
    gtext,
    "String",
    "WEB_FILL_MODE",
    `buildConfigField("String", "WEB_FILL_MODE", "\\"${webFillMode}\\"")`,
    ["DOWNLOAD_MODE", "SCREEN_ORIENTATION", "DOUBLE_CLICK_EXIT"]
  );
  fs.writeFileSync(gradleFile, gtext, 'utf8');
}
NODE

    if [ -f "$INPUT_DIR/logo.png" ]; then
        drawable_dir="$PROJECT_ROOT/app/src/main/res/drawable"
        if [ -d "$drawable_dir" ]; then
            rm -f "$drawable_dir/ic_launcher_foreground.xml"
            prepareLauncherForegroundIcon "$INPUT_DIR/logo.png" "$drawable_dir/ic_launcher_foreground.png"
            log_info "Template launcher icon updated with adaptive safe padding"
        fi
    fi

    cd "$PROJECT_ROOT"
    log_success "Step 0 done"
elif [ "$TASK_MODE" = "native" ]; then
    log_info "Step 1: 解压原生 Android 工程..."
    ZIP_FILE=$(find "$INPUT_DIR" -name "*.zip" -type f | head -n 1)

    if [ -z "$ZIP_FILE" ]; then
        log_error "No ZIP found in $INPUT_DIR"
        exit 1
    fi

    log_info "Found native Android ZIP: $ZIP_FILE"
    rm -rf "$PROJECT_DIR"
    mkdir -p "$PROJECT_DIR"
    unzip -q "$ZIP_FILE" -d "$PROJECT_DIR"
    check_error "Unzip native Android project failed"

    PROJECT_ROOT="$(findNativeAndroidRoot "$PROJECT_DIR" || true)"
    if [ -z "$PROJECT_ROOT" ]; then
        log_error "原生 Android 源码 ZIP 中未找到完整 Gradle 工程，请确认包含 settings.gradle、gradlew 与 app 模块"
        exit 1
    fi
    ANDROID_DIR="."
    log_info "Native Android project root: $PROJECT_ROOT"
    cd "$PROJECT_ROOT"
    log_success "Step 0 done"
else
    # check zip for convert mode
    ZIP_FILE=$(find "$INPUT_DIR" -name "*.zip" -type f | head -n 1)

    if [ -z "$ZIP_FILE" ]; then
        log_error "No ZIP found in $INPUT_DIR"
        exit 1
    fi

    log_info "Found ZIP: $ZIP_FILE"

    # create project dir
    rm -rf "$PROJECT_DIR"
    mkdir -p "$PROJECT_DIR"

    # unzip
    log_info "Unzip project..."
    unzip -q "$ZIP_FILE" -d "$PROJECT_DIR"
    check_error "Unzip failed"

    SKIP_WEB_BUILD=false

    # find package.json (exclude node_modules etc)
    PACKAGE_JSON=$(find "$PROJECT_DIR" -name "package.json" -type f \
        -not -path "*/node_modules/*" \
        -not -path "*/android/*" \
        -not -path "*/.git/*" \
        | head -n 1)

    if [ -z "$PACKAGE_JSON" ]; then
        # Fallback: allow zips containing only built static site (no Node project).
        # Common case: users zip the dist/build output folder.
        INDEX_HTML=$(find "$PROJECT_DIR" -name "index.html" -type f \
            -not -path "*/node_modules/*" \
            -not -path "*/android/*" \
            -not -path "*/.git/*" \
            | head -n 1)
        if [ -z "$INDEX_HTML" ]; then
            log_error "package.json not found (and index.html not found)."
            log_error "请上传包含 package.json 的项目源码（通常是项目根目录打包），或上传已构建的静态站点 ZIP（包含 index.html）。"
            exit 1
        fi

        log_warning "package.json not found, treating ZIP as prebuilt web assets"
        log_info "index.html found at: $INDEX_HTML"

        # Heuristic: if index.html looks like source (e.g. Vite dev entry), warn instead of generating a broken APK.
        if grep -qE '(^|[\"\\x27\\s])(/?src/|@vite|vite/client|react-refresh)' "$INDEX_HTML" 2>/dev/null; then
            log_error "检测到 index.html 可能是源码入口（引用了 /src 或 vite client），但 ZIP 中缺少 package.json。"
            log_error "请重新打包项目根目录（包含 package.json），或先构建后再上传 dist/build 的 ZIP。"
            exit 1
        fi

        STATIC_ROOT="$(dirname "$INDEX_HTML")"
        WRAPPER_ROOT="$PROJECT_DIR/__convertapk_prebuilt"
        rm -rf "$WRAPPER_ROOT"
        mkdir -p "$WRAPPER_ROOT/dist"
        cp -R "$STATIC_ROOT"/. "$WRAPPER_ROOT/dist"/

        # Minimal node project for Capacitor steps.
        cat > "$WRAPPER_ROOT/package.json" << 'EOF'
{
  "name": "convertapk-prebuilt",
  "private": true,
  "version": "1.0.0",
  "description": "Generated by ConvertAPK for prebuilt web assets",
  "scripts": {
    "build": "echo prebuilt"
  }
}
EOF

        PROJECT_ROOT="$WRAPPER_ROOT"
        WEB_DIR="dist"
        SKIP_WEB_BUILD=true
    else
        PROJECT_ROOT=$(dirname "$PACKAGE_JSON")
    fi

    PROJECT_ROOT="$(normalizeProjectRootForBuild "$PROJECT_ROOT")"

    log_info "Project root: $PROJECT_ROOT"

    cd "$PROJECT_ROOT"

    log_success "Step 0 done"
fi
if [ "$TASK_MODE" = "convert" ]; then
# ============================================
log_info "Step 1: 构建 Web 项目..."

# 兼容性兜底：如果上传 ZIP 自带 android 工程，先清理再由 Capacitor 重新生成，
# 避免旧工程中的 gradle-wrapper / gradlew 损坏导致构建失败。
if [ -d "$PROJECT_ROOT/android" ]; then
    log_warning "检测到上传包包含 android 目录，构建前将先清理以避免干扰"
    rm -rf "$PROJECT_ROOT/android"
    check_error "清理上传包内 android 目录失败"
fi

if [ "$SKIP_WEB_BUILD" = "true" ]; then
    log_warning "检测到预构建静态站点 ZIP：跳过 npm install / npm run build，直接使用 $WEB_DIR"
else

# 检测项目使用的包管理器
detectPackageManager() {
    if [ -f "pnpm-lock.yaml" ]; then
        echo "pnpm"
    elif [ -f "yarn.lock" ]; then
        echo "yarn"
    elif [ -f "package-lock.json" ] || [ -f "npm-shrinkwrap.json" ]; then
        echo "npm-ci"
    else
        echo "npm"
    fi
}

# 安装依赖（优先使用 lock 文件，避免版本漂移）
forceNextConfigExport() {
    if [ ! -f "package.json" ]; then
        return 0
    fi
    node <<'NODE'
const fs = require("fs");
const path = require("path");

const pkgPath = path.join(process.cwd(), "package.json");
let pkg = {};
try {
  pkg = JSON.parse(fs.readFileSync(pkgPath, "utf8"));
} catch {
  process.exit(0);
}

const deps = Object.assign({}, pkg.dependencies || {}, pkg.devDependencies || {});
if (!Object.prototype.hasOwnProperty.call(deps, "next")) {
  process.exit(0);
}

const candidates = ["next.config.ts", "next.config.js", "next.config.mjs", "next.config.cjs"];
let configPath = null;
for (const filename of candidates) {
  const fullPath = path.join(process.cwd(), filename);
  if (fs.existsSync(fullPath) && fs.statSync(fullPath).isFile()) {
    configPath = fullPath;
    break;
  }
}

if (!configPath) {
  console.log("[Next.js] 未找到 next.config.*，跳过 output 自动改写");
  process.exit(0);
}

let content = fs.readFileSync(configPath, "utf8");
const outputPattern = /(\boutput\s*:\s*)(['"])([^'"\r\n]+)\2/;
const matched = content.match(outputPattern);
let status = "no_change";

if (matched) {
  const currentValue = String(matched[3] || "").trim().toLowerCase();
  if (currentValue === "export") {
    status = "already_export";
  } else {
    content = content.replace(outputPattern, `${matched[1]}${matched[2]}export${matched[2]}`);
    status = "updated";
  }
} else {
  const injectPatterns = [
    /(const\s+nextConfig(?:\s*:\s*NextConfig)?\s*=\s*\{)/,
    /(module\.exports\s*=\s*\{)/,
    /(export\s+default\s*\{)/,
  ];
  for (const pattern of injectPatterns) {
    if (pattern.test(content)) {
      content = content.replace(pattern, "$1\n  output: 'export',");
      status = "injected";
      break;
    }
  }
}

const configName = path.basename(configPath);
if (status === "updated" || status === "injected") {
  fs.writeFileSync(configPath, content, "utf8");
  console.log(`[Next.js] 已自动改写 ${configName} 为 output: 'export'`);
} else if (status === "already_export") {
  console.log(`[Next.js] ${configName} 已是 output: 'export'`);
} else {
  console.log(`[Next.js] 未能自动改写 ${configName}，将继续尝试导出兜底流程`);
}
NODE
}

forceNextIgnoreTypeErrors() {
    node <<'NODE'
const fs = require("fs");
const path = require("path");

const pkgPath = path.join(process.cwd(), "package.json");
let pkg = {};
try {
  pkg = JSON.parse(fs.readFileSync(pkgPath, "utf8"));
} catch {
  process.exit(0);
}

const deps = Object.assign({}, pkg.dependencies || {}, pkg.devDependencies || {});
if (!Object.prototype.hasOwnProperty.call(deps, "next")) {
  process.exit(0);
}

const candidates = ["next.config.ts", "next.config.js", "next.config.mjs", "next.config.cjs"];
let configPath = null;
for (const filename of candidates) {
  const fullPath = path.join(process.cwd(), filename);
  if (fs.existsSync(fullPath) && fs.statSync(fullPath).isFile()) {
    configPath = fullPath;
    break;
  }
}

if (!configPath) {
  const createdConfigPath = path.join(process.cwd(), "next.config.mjs");
  const scaffold = `/** @type {import('next').NextConfig} */
const nextConfig = {
  typescript: { ignoreBuildErrors: true },
  eslint: { ignoreDuringBuilds: true },
};

export default nextConfig;
`;
  fs.writeFileSync(createdConfigPath, scaffold, "utf8");
  console.log("[Next.js] 未找到 next.config.*，已创建 next.config.mjs 并注入类型检查兜底配置");
  process.exit(0);
}

let content = fs.readFileSync(configPath, "utf8");
let changed = false;

if (/typescript\s*:\s*\{[^}]*ignoreBuildErrors\s*:\s*true/i.test(content)) {
  // no-op
} else if (/typescript\s*:\s*\{/i.test(content)) {
  content = content.replace(/typescript\s*:\s*\{([\s\S]*?)\}/m, (m, inner) => {
    if (/ignoreBuildErrors\s*:/i.test(inner)) {
      return m.replace(/ignoreBuildErrors\s*:\s*[^,\n}]+/i, "ignoreBuildErrors: true");
    }
    return m.replace(/\}\s*$/, ", ignoreBuildErrors: true }");
  });
  changed = true;
} else {
  const injectPatterns = [
    /(const\s+nextConfig(?:\s*:\s*NextConfig)?\s*=\s*\{)/,
    /(module\.exports\s*=\s*\{)/,
    /(export\s+default\s*\{)/,
  ];
  for (const pattern of injectPatterns) {
    if (pattern.test(content)) {
      content = content.replace(pattern, "$1\n  typescript: { ignoreBuildErrors: true },\n  eslint: { ignoreDuringBuilds: true },");
      changed = true;
      break;
    }
  }
}

if (!/eslint\s*:\s*\{[^}]*ignoreDuringBuilds\s*:\s*true/i.test(content)) {
  if (/eslint\s*:\s*\{/i.test(content)) {
    content = content.replace(/eslint\s*:\s*\{([\s\S]*?)\}/m, (m, inner) => {
      if (/ignoreDuringBuilds\s*:/i.test(inner)) {
        return m.replace(/ignoreDuringBuilds\s*:\s*[^,\n}]+/i, "ignoreDuringBuilds: true");
      }
      return m.replace(/\}\s*$/, ", ignoreDuringBuilds: true }");
    });
    changed = true;
  } else {
    const injectPatterns = [
      /(const\s+nextConfig(?:\s*:\s*NextConfig)?\s*=\s*\{)/,
      /(module\.exports\s*=\s*\{)/,
      /(export\s+default\s*\{)/,
    ];
    for (const pattern of injectPatterns) {
      if (pattern.test(content)) {
        content = content.replace(pattern, "$1\n  eslint: { ignoreDuringBuilds: true },");
        changed = true;
        break;
      }
    }
  }
}

if (changed) {
  fs.writeFileSync(configPath, content, "utf8");
  console.log(`[Next.js] 已注入类型检查兜底配置: ${path.basename(configPath)}`);
} else {
  console.log(`[Next.js] ${path.basename(configPath)} 已包含类型检查兜底配置`);
}
NODE
}

installDependencies() {
    local installMode="${1:-normal}"
    local packageManager
    packageManager="$(detectPackageManager)"

    if [ "$installMode" = "reinstall" ]; then
        log_info "清理 node_modules 后重新安装依赖..."
        rm -rf node_modules
    fi

    if [ "$packageManager" = "pnpm" ]; then
        if command -v pnpm >/dev/null 2>&1; then
            log_info "使用 pnpm-lock.yaml 锁定安装依赖..."
            if pnpm install --frozen-lockfile; then
                return 0
            fi
            log_warning "pnpm install 失败，回退 npm install（可能导致版本漂移）"
            npm install --legacy-peer-deps
            return $?
        fi
        log_warning "检测到 pnpm-lock.yaml 但未安装 pnpm，回退 npm install（可能导致版本漂移）"
        npm install --legacy-peer-deps
        return $?
    fi

    if [ "$packageManager" = "yarn" ]; then
        if command -v yarn >/dev/null 2>&1; then
            log_info "使用 yarn.lock 锁定安装依赖..."
            if yarn install --frozen-lockfile; then
                return 0
            fi
            log_warning "yarn install 失败，回退 npm install（可能导致版本漂移）"
            npm install --legacy-peer-deps
            return $?
        fi
        log_warning "检测到 yarn.lock 但未安装 yarn，回退 npm install（可能导致版本漂移）"
        npm install --legacy-peer-deps
        return $?
    fi

    if [ "$packageManager" = "npm-ci" ]; then
        log_info "使用 package-lock 锁定安装依赖（npm ci）..."
        if npm ci --legacy-peer-deps; then
            return 0
        fi
        log_warning "npm ci 失败，回退 npm install（可能导致版本漂移）"
        npm install --legacy-peer-deps
        return $?
    fi

    log_info "未检测到 lock 文件，使用 npm install..."
    npm install --legacy-peer-deps
    return $?
}

# 安装构建缺失依赖（按项目包管理器执行）
installMissingDependency() {
    local packageName="$1"
    local packageManager
    packageManager="$(detectPackageManager)"

    if [ "$packageManager" = "pnpm" ] && command -v pnpm >/dev/null 2>&1; then
        pnpm add "$packageName" >/dev/null 2>&1 || true
        return 0
    fi

    if [ "$packageManager" = "yarn" ] && command -v yarn >/dev/null 2>&1; then
        yarn add "$packageName" >/dev/null 2>&1 || true
        return 0
    fi

    npm install "$packageName" --legacy-peer-deps --save >/dev/null 2>&1 || true
}

# 完整重装依赖的函数
reinstallDependencies() {
    log_info "执行完整依赖重装..."
    installDependencies "reinstall"
    return $?
}

detectWebOutputDir() {
    if [ -d "dist" ]; then
        echo "dist"
        return 0
    fi
    if [ -d "build" ]; then
        echo "build"
        return 0
    fi
    if [ -d "out" ]; then
        echo "out"
        return 0
    fi
    return 1
}

detectPrebuiltWebFallbackReason() {
    local webOutputDir="$1"
    if [ -z "$webOutputDir" ] || [ ! -f "$webOutputDir/index.html" ] || [ ! -f "package.json" ]; then
        return 1
    fi
    if ! command -v node >/dev/null 2>&1; then
        return 1
    fi

    local yarnAvailable="false"
    if command -v yarn >/dev/null 2>&1; then
        yarnAvailable="true"
    fi

    YARN_AVAILABLE="$yarnAvailable" node <<'NODE'
const fs = require("fs");
const path = require("path");

function readJson(filePath) {
  try {
    return JSON.parse(fs.readFileSync(filePath, "utf8"));
  } catch {
    return {};
  }
}

function majorOf(version) {
  const match = String(version || "").match(/\d+/);
  return match ? Number(match[0]) : 0;
}

const pkg = readJson(path.join(process.cwd(), "package.json"));
const deps = Object.assign({}, pkg.dependencies || {}, pkg.devDependencies || {});
const reasons = [];

if (Object.prototype.hasOwnProperty.call(deps, "node-sass")) {
  reasons.push("依赖包含 node-sass，旧版 node-sass 在当前 Node 环境下经常安装失败");
}

const vueCliVersion = deps["@vue/cli-service"];
if (vueCliVersion && majorOf(vueCliVersion) > 0 && majorOf(vueCliVersion) <= 4) {
  reasons.push("依赖包含 Vue CLI 4，适合优先复用已生成的 dist 静态产物");
}

if (fs.existsSync(path.join(process.cwd(), "yarn.lock")) && process.env.YARN_AVAILABLE !== "true") {
  reasons.push("项目带 yarn.lock 但构建镜像未安装 yarn，回退 npm 可能导致依赖树漂移");
}

if (!reasons.length) {
  process.exit(1);
}

console.log(reasons.join("；"));
NODE
}

printNodeFailureHelp() {
    local failureOutput="$1"

    if echo "$failureOutput" | grep -qi "Exit handler never called"; then
        log_warning "修复建议：npm 自身异常退出，常见于旧版前端依赖与当前 Node/npm 不兼容。若压缩包内已有 dist/index.html，建议直接上传 dist 静态产物。"
    fi

    if echo "$failureOutput" | grep -qi "node-sass"; then
        log_warning "修复建议：node-sass 已不适合新 Node 环境，建议将依赖替换为 sass，或使用项目历史 Node 版本在本地构建后上传 dist。"
    fi

    if [ -f "yarn.lock" ] && ! command -v yarn >/dev/null 2>&1; then
        log_warning "修复建议：项目包含 yarn.lock，但构建镜像没有 yarn；请改用静态 dist 上传，或提交与 npm 对应的 package-lock.json 后重试。"
    fi
}

detectWebBuildFallback() {
    if [ ! -f "package.json" ] || ! command -v node >/dev/null 2>&1; then
        return 1
    fi

    node <<'NODE'
const fs = require("fs");
const path = require("path");

const pkgPath = path.join(process.cwd(), "package.json");
let pkg = {};
try {
  pkg = JSON.parse(fs.readFileSync(pkgPath, "utf8"));
} catch {
  process.exit(1);
}

const deps = Object.assign({}, pkg.dependencies || {}, pkg.devDependencies || {});
const hasPackage = (name) => Object.prototype.hasOwnProperty.call(deps, name);
const hasFile = (names) => names.some((name) => fs.existsSync(path.join(process.cwd(), name)));

if (hasPackage("vite") || hasFile(["vite.config.js", "vite.config.mjs", "vite.config.ts", "vite.config.cjs"])) {
  console.log("vite");
  process.exit(0);
}

process.exit(1);
NODE
}

runWebOutputFallback() {
    local fallbackKind
    fallbackKind="$(detectWebBuildFallback || true)"

    if [ "$fallbackKind" != "vite" ]; then
        return 1
    fi

    log_warning "npm run build 未生成 Web 输出目录，检测到 Vite 项目，尝试执行 Vite 构建兜底..."

    local viteCommand=""
    if [ -x "node_modules/.bin/vite" ]; then
        viteCommand="node_modules/.bin/vite"
    else
        viteCommand="npx --no-install vite"
    fi

    local fallbackOutput=""
    local fallbackSuccess=false
    fallbackOutput=$($viteCommand build --logLevel error 2>&1) && fallbackSuccess=true || fallbackSuccess=false

    if [ -n "$fallbackOutput" ]; then
        echo "$fallbackOutput"
    fi

    if [ "$fallbackSuccess" != "true" ]; then
        log_warning "Vite 构建兜底失败，继续使用原始错误结果"
        return 1
    fi

    if detectWebOutputDir >/dev/null 2>&1; then
        log_success "Vite 构建兜底成功"
        return 0
    fi

    log_warning "Vite 构建兜底已执行，但仍未生成 dist/build/out 输出目录"
    return 1
}

# 首次安装依赖
PREBUILT_WEB_DIR="$(detectWebOutputDir || true)"
PREBUILT_WEB_REASON=""
if [ -n "$PREBUILT_WEB_DIR" ]; then
    PREBUILT_WEB_REASON="$(detectPrebuiltWebFallbackReason "$PREBUILT_WEB_DIR" || true)"
fi

if [ -n "$PREBUILT_WEB_REASON" ]; then
    WEB_DIR="$PREBUILT_WEB_DIR"
    log_warning "检测到可用预构建静态目录 $WEB_DIR，且源码依赖存在兼容风险：$PREBUILT_WEB_REASON"
    log_warning "已跳过 npm install / npm run build，直接使用现有静态产物，避免旧依赖在服务器环境安装失败"
else
log_info "安装项目依赖..."
if command -v node >/dev/null 2>&1; then
    forceNextConfigExport || log_warning "Next.js config auto rewrite failed, continue build"
fi
INSTALL_OUTPUT=$(installDependencies 2>&1) && INSTALL_SUCCESS=true || INSTALL_SUCCESS=false
if [ -n "$INSTALL_OUTPUT" ]; then
    echo "$INSTALL_OUTPUT"
fi
if [ "$INSTALL_SUCCESS" != "true" ]; then
    printNodeFailureHelp "$INSTALL_OUTPUT"
    log_error "依赖安装失败"
    exit 1
fi

# 尝试构建
log_info "构建项目..."
BUILD_OUTPUT=$(npm run build 2>&1) && BUILD_SUCCESS=true || BUILD_SUCCESS=false

if [ "$BUILD_SUCCESS" = "true" ]; then
    log_success "项目构建成功"
else
    log_warning "首次构建失败，分析错误..."
    echo "$BUILD_OUTPUT"

    if echo "$BUILD_OUTPUT" | grep -q "Type error:"; then
        log_warning "检测到 Next.js 类型检查失败，尝试注入 ignoreBuildErrors 后重试..."
        if command -v node >/dev/null 2>&1; then
            forceNextIgnoreTypeErrors || log_warning "Next.js 类型检查兜底注入失败，继续后续兜底流程"
            BUILD_OUTPUT=$(npm run build 2>&1) && BUILD_SUCCESS=true || BUILD_SUCCESS=false
            if [ "$BUILD_SUCCESS" = "true" ]; then
                log_success "已通过类型检查兜底完成构建"
            else
                log_warning "类型检查兜底后仍构建失败，继续后续兜底流程"
                echo "$BUILD_OUTPUT"
            fi
        fi
    fi

    if echo "$BUILD_OUTPUT" | grep -qE '\[vite:build-html\].*EISDIR' && \
       echo "$BUILD_OUTPUT" | grep -qE 'index\.html'; then
        log_warning "检测到 vite 读取 index.html 异常，尝试自动切换项目根目录"
        ALT_ROOT="$(findAlternativeViteRoot "$PROJECT_ROOT" || true)"
        if [ -n "$ALT_ROOT" ]; then
            PROJECT_ROOT="$(normalizeProjectRootForBuild "$ALT_ROOT")"
            log_info "切换到候选项目根目录: $PROJECT_ROOT"
            cd "$PROJECT_ROOT"
            installDependencies
            check_error "切换目录后依赖安装失败"
            BUILD_OUTPUT=$(npm run build 2>&1) && BUILD_SUCCESS=true || BUILD_SUCCESS=false
            if [ "$BUILD_SUCCESS" = "true" ]; then
                log_success "切换项目根目录后构建成功"
            else
                log_warning "切换项目根目录后仍构建失败，继续执行依赖修复流程"
                echo "$BUILD_OUTPUT"
            fi
        else
            log_warning "未找到可用的候选项目根目录，继续使用原目录"
        fi
    fi
    
    # 提取缺失的模块名
    if [ "$BUILD_SUCCESS" != "true" ]; then
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
                installMissingDependency "$PKG_NAME"
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
            reinstallDependencies
            check_error "依赖重装失败"
            
            # 第三次尝试构建
            log_info "最终构建尝试..."
            npm run build
            check_error "npm run build 失败"
        fi
    else
        # 没有检测到缺失模块，直接尝试完整重装
        log_warning "未检测到具体缺失模块，尝试完整重装依赖..."
        
        reinstallDependencies
        check_error "依赖重装失败"
        
        # 再次构建
        log_info "重新构建项目..."
        npm run build
        check_error "npm run build 失败"
    fi
    fi
fi
fi

# 确定输出目录
WEB_DIR="$(detectWebOutputDir || true)"
if [ -z "$WEB_DIR" ]; then
    runWebOutputFallback || true
    WEB_DIR="$(detectWebOutputDir || true)"
fi

if [ -z "$WEB_DIR" ]; then
    log_error "未找到构建输出目录 (dist/build/out)"
    exit 1
fi

log_success "Web 项目构建完成，输出目录: $WEB_DIR"

fi

if [ -z "$WEB_DIR" ]; then
    # 兼容：兜底检测输出目录
    if [ -d "dist" ]; then
        WEB_DIR="dist"
    elif [ -d "build" ]; then
        WEB_DIR="build"
    elif [ -d "out" ]; then
        WEB_DIR="out"
    else
        log_error "未找到 Web 输出目录 (dist/build/out)"
        exit 1
    fi
fi

if [ ! -d "$WEB_DIR" ]; then
    log_error "Web 输出目录不存在: $WEB_DIR"
    exit 1
fi

normalizeWebCssForLegacyWebView "$WEB_DIR"

if [ "$TASK_MODE" = "convert" ]; then
    runOfflineizeAssets "$WEB_DIR/index.html" "Step 1.5"
fi

dedupeWebBuildAssets "$WEB_DIR"

# 注入前端下载处理脚本（换行修复默认关闭，避免影响页面布局）
log_info "注入前端下载处理脚本..."
ENABLE_NEWLINE_FIX_RAW="$(printf '%s' "${ENABLE_NEWLINE_FIX:-false}" | tr '[:upper:]' '[:lower:]')"
INJECT_NEWLINE_FIX="false"
case "$ENABLE_NEWLINE_FIX_RAW" in
    1|true|yes|on)
        INJECT_NEWLINE_FIX="true"
        ;;
esac
if [ "$INJECT_NEWLINE_FIX" = "true" ]; then
    log_warning "已启用换行修复脚本注入（可能影响页面布局）"
else
    log_info "默认禁用换行修复脚本注入"
fi

WEB_DIR="$WEB_DIR" INJECT_NEWLINE_FIX="$INJECT_NEWLINE_FIX" node << 'NODE'
const fs = require("fs");
const path = require("path");

function readText(filePath) {
  try {
    return fs.readFileSync(filePath, "utf8");
  } catch (err) {
    return fs.readFileSync(filePath, "latin1");
  }
}

function writeText(filePath, text) {
  fs.writeFileSync(filePath, text, "utf8");
}

const webDir = process.env.WEB_DIR || "dist";
const injectNewlineFix = String(process.env.INJECT_NEWLINE_FIX || "").toLowerCase() === "true";
const downloadMode = String(process.env.DOWNLOAD_MODE || "").trim().toLowerCase() === "silent" ? "silent" : "picker";
const indexHtml = path.join(process.cwd(), webDir, "index.html");
if (!fs.existsSync(indexHtml)) {
  process.exit(0);
}

let html = readText(indexHtml);

const downloadScript = `<script id="convertapk-download-helper">(function(){
  if (window.__convertapkDownloadHelper) return;
  window.__convertapkDownloadHelper = true;
  var downloadMode = '${downloadMode}';
  function getAnchor(el){
    while (el && el.tagName !== 'A') el = el.parentElement;
    return el;
  }
  function withDefaultExtension(name, mimeType){
    var safe = String(name || '').trim();
    if (!safe) safe = 'download';
    safe = safe.replace(/[\\\\/:*?"<>|]+/g, '_');
    if (safe.includes('.')) return safe;
    var mime = String(mimeType || '').toLowerCase();
    if (mime.includes('json')) return safe + '.json';
    if (mime.includes('pdf')) return safe + '.pdf';
    if (mime.includes('csv')) return safe + '.csv';
    if (mime.includes('zip')) return safe + '.zip';
    if (mime.startsWith('text/')) return safe + '.txt';
    return safe;
  }
  function getFilename(a, href, mimeType){
    var name = (a.getAttribute('download') || a.download || '').trim();
    if (name) return name;
    try {
      var url = new URL(href, window.location.href);
      name = url.pathname.split('/').pop() || 'download';
    } catch (e) {
      name = 'download';
    }
    return withDefaultExtension(name, mimeType);
  }
  function getDownloadRequestKey(a, href){
    var downloadName = '';
    try {
      downloadName = (a && (a.getAttribute('download') || a.download || '')) || '';
    } catch (e) {
    }
    var normalizedHref = String(href || '');
    if (normalizedHref.startsWith('blob:')) {
      // blob URL 每次都可能变化，这里做归一化避免同一导出动作重复触发
      normalizedHref = 'blob:';
    } else if (normalizedHref.startsWith('data:')) {
      normalizedHref = 'data:';
    }
    return normalizedHref + '|' + String(downloadName || '');
  }
  function shouldSkipDuplicateRequest(a, href){
    var now = Date.now();
    var state = window.__convertapkDownloadDedupeState;
    if (!state) {
      state = { lastKey: '', lastAt: 0, inFlight: {} };
      window.__convertapkDownloadDedupeState = state;
    }
    var key = getDownloadRequestKey(a, href);
    var recentWindow = 1200;
    var inFlightWindow = 4000;
    try {
      for (var k in state.inFlight) {
        if (!Object.prototype.hasOwnProperty.call(state.inFlight, k)) continue;
        if (now - Number(state.inFlight[k] || 0) > inFlightWindow) {
          delete state.inFlight[k];
        }
      }
    } catch (e) {
    }
    if (state.inFlight[key]) {
      return true;
    }
    if (state.lastKey === key && now - Number(state.lastAt || 0) < recentWindow) {
      return true;
    }
    state.lastKey = key;
    state.lastAt = now;
    state.inFlight[key] = now;
    return false;
  }
  function releaseDownloadRequest(a, href){
    try {
      var state = window.__convertapkDownloadDedupeState;
      if (!state || !state.inFlight) return;
      var key = getDownloadRequestKey(a, href);
      delete state.inFlight[key];
    } catch (e) {
    }
  }
  function getShareState(){
    var state = window.__convertapkShareState;
    if (!state) {
      state = { inFlight: false, currentFile: '', lastFile: '', lastAt: 0 };
      window.__convertapkShareState = state;
    }
    return state;
  }
  function beginShare(fileKey){
    var state = getShareState();
    var now = Date.now();
    var cooldownMs = 10000;
    if (state.inFlight) {
      return false;
    }
    // 任意文件在冷却窗口内都跳过，防止多条导出路径导致重复弹窗
    if (now - Number(state.lastAt || 0) < cooldownMs) {
      return false;
    }
    state.inFlight = true;
    state.currentFile = fileKey;
    return true;
  }
  function endShare(fileKey, shared){
    var state = getShareState();
    if (shared) {
      state.lastFile = fileKey;
      state.lastAt = Date.now();
    }
    setTimeout(function(){
      var latest = getShareState();
      if (latest.currentFile === fileKey) {
        latest.inFlight = false;
        latest.currentFile = '';
      }
    }, 300);
  }
  function readAsDataUrl(blob){
    return new Promise(function(resolve, reject){
      var reader = new FileReader();
      reader.onload = function(){ resolve(reader.result || ''); };
      reader.onerror = function(){ reject(reader.error); };
      reader.readAsDataURL(blob);
    });
  }
  async function shareFile(filename){
    try {
      var cap = window.Capacitor;
      if (!cap || !cap.Plugins || !cap.Plugins.Share || !cap.Plugins.Filesystem) return false;
      var fsPlugin = cap.Plugins.Filesystem;
      var uriResult = await fsPlugin.getUri({ path: filename, directory: 'DOCUMENTS' });
      var fileUrl = uriResult && uriResult.uri ? uriResult.uri : '';
      if (!fileUrl) {
        uriResult = await fsPlugin.getUri({ path: filename, directory: 'DATA' });
        fileUrl = uriResult && uriResult.uri ? uriResult.uri : '';
      }
      if (!fileUrl) return false;
      var fileKey = String(filename || 'download');
      if (!beginShare(fileKey)) {
        return true;
      }
      var shared = false;
      try {
        await cap.Plugins.Share.share({
          title: filename,
          text: filename,
          files: [fileUrl],
          dialogTitle: filename
        });
        shared = true;
        return true;
      } catch (e) {
        return false;
      } finally {
        endShare(fileKey, shared);
      }
    } catch (e) {
      return false;
    }
  }
  async function maybeShareSavedFile(filename, triggerPicker){
    if (triggerPicker === false) return;
    if (downloadMode === 'silent') return;
    var shared = await shareFile(filename);
    if (!shared) {
      console.warn('[ConvertAPK] 文件已保存，但当前设备无法直接拉起分享面板:', filename);
    }
  }
  async function saveBlob(blob, filename, triggerPicker){
    var cap = window.Capacitor;
    if (!cap || !cap.Plugins || !cap.Plugins.Filesystem) return false;
    var dataUrl = await readAsDataUrl(blob);
    var base64 = String(dataUrl).split(',')[1] || '';
    var fsPlugin = cap.Plugins.Filesystem;
      try {
        await fsPlugin.writeFile({ path: filename, data: base64, directory: 'DOCUMENTS', recursive: true });
        await maybeShareSavedFile(filename, triggerPicker);
        return true;
    } catch (e) {
      try {
        await fsPlugin.writeFile({ path: filename, data: base64, directory: 'DATA', recursive: true });
        await maybeShareSavedFile(filename, triggerPicker);
        return true;
      } catch (e2) {
        return false;
      }
    }
  }
  async function handleDownload(a, href){
    if (!href) return false;
    if (shouldSkipDuplicateRequest(a, href)) {
      return true;
    }
    try {
      var isBlob = href.startsWith('blob:');
      var isData = href.startsWith('data:');
      if (!isBlob && !isData) {
        if (downloadMode === 'silent') return false;
        try {
          var url = new URL(href, window.location.href).toString();
          var cap = window.Capacitor;
          if (cap && cap.Plugins && cap.Plugins.Browser) {
            cap.Plugins.Browser.open({ url: url });
            return true;
          }
          window.open(url, '_blank');
          return true;
        } catch (e) {
          return false;
        }
      }
      try {
        var res = await fetch(href);
        var blob = await res.blob();
        return await saveBlob(blob, getFilename(a, href, blob && blob.type), true);
      } catch (e) {
        return false;
      }
    } finally {
      setTimeout(function(){
        releaseDownloadRequest(a, href);
      }, 1600);
    }
  }
  async function shareFiles(files, title){
    if (!files || !files.length) return false;
    var file = files[0];
    var name = withDefaultExtension((file && file.name) || title || 'share', file && file.type);
    try {
      var ok = await saveBlob(file, name, false);
      if (!ok) return false;
      return await shareFile(name);
    } catch (e) {
      return false;
    }
  }
  (function(){
    if (!navigator) return;
    var cap = window.Capacitor;
    if (!cap || !cap.Plugins || !cap.Plugins.Share || !cap.Plugins.Filesystem) return;
    var origCanShare = navigator.canShare ? navigator.canShare.bind(navigator) : null;
    navigator.canShare = function(data){
      if (data && data.files && data.files.length) return true;
      return origCanShare ? origCanShare(data) : false;
    };
    if (navigator.share) {
      var origShare = navigator.share.bind(navigator);
      navigator.share = async function(data){
        if (data && data.files && data.files.length) {
          var ok = await shareFiles(data.files, data.title || data.text || '');
          if (ok) return;
          // 文件分享失败时不回退到文本分享，避免出现额外弹窗
          throw new Error('file share failed');
        }
        return origShare(data);
      };
    } else {
      navigator.share = async function(data){
        if (data && data.files && data.files.length) {
          var ok = await shareFiles(data.files, data.title || data.text || '');
          if (ok) return;
          // 文件分享失败时不回退到文本分享，避免出现额外弹窗
          throw new Error('file share failed');
        }
        throw new Error('share not supported');
      };
    }
  })();
  function hookJsPdfSave(){
    try {
      var JSPDF = (window.jspdf && window.jspdf.jsPDF) || window.jsPDF;
      if (!JSPDF || !JSPDF.API || JSPDF.API.__convertapkSavePatched) return false;
      var origSave = JSPDF.API.save;
      JSPDF.API.save = function(filename){
        try {
          var blob = this.output('blob');
          saveBlob(blob, filename || 'download.pdf');
          return;
        } catch (e) {
        }
        return origSave ? origSave.apply(this, arguments) : undefined;
      };
      JSPDF.API.__convertapkSavePatched = true;
      return true;
    } catch (e) {
      return false;
    }
  }
  var _pdfTries = 0;
  var _pdfTimer = setInterval(function(){
    _pdfTries += 1;
    if (hookJsPdfSave() || _pdfTries > 20) clearInterval(_pdfTimer);
  }, 500);
  if (navigator) {
    try {
      navigator.msSaveOrOpenBlob = function(blob, name){ saveBlob(blob, name || 'download'); return true; };
      navigator.msSaveBlob = function(blob, name){ saveBlob(blob, name || 'download'); return true; };
    } catch (e) {
    }
  }
  try {
    window.saveAs = function(blob, name){ return saveBlob(blob, name || 'download'); };
  } catch (e) {
  }
  var _origClick = HTMLAnchorElement.prototype.click;
  HTMLAnchorElement.prototype.click = function(){
    try {
      var href = this.getAttribute('href') || this.href || '';
      var download = this.getAttribute('download') || this.download;
      var isBlob = href.startsWith('blob:');
      var isData = href.startsWith('data:');
      var shouldHandle = isBlob || isData || (download && downloadMode !== 'silent');
      if (shouldHandle) {
        handleDownload(this, href);
        return;
      }
    } catch (e) {
    }
    return _origClick.call(this);
  };
  var _origDispatch = HTMLAnchorElement.prototype.dispatchEvent;
  HTMLAnchorElement.prototype.dispatchEvent = function(evt){
    // 仅保留原生 dispatch，避免 click/dispatch 双拦截导致重复导出
    return _origDispatch.call(this, evt);
  };
  document.addEventListener('click', function(e){
    var a = getAnchor(e.target);
    if (!a) return;
    var href = a.getAttribute('href') || '';
    var download = a.getAttribute('download') || a.download;
    if (!href) return;
    var isBlob = href.startsWith('blob:');
    var isData = href.startsWith('data:');
    var shouldHandle = isBlob || isData || (download && downloadMode !== 'silent');
    if (shouldHandle) {
      e.preventDefault();
      e.stopPropagation();
      handleDownload(a, href);
    }
  }, true);
})();</script>`;

const newlineScript = `<script id="convertapk-newline-fix">(function(){
  if (window.__convertapkNewlineFix) return;
  window.__convertapkNewlineFix = true;
  function shouldSkip(node){
    if (!node || !node.parentElement) return true;
    var tag = node.parentElement.tagName || '';
    if (['SCRIPT','STYLE','TEXTAREA','CODE','PRE','INPUT'].includes(tag)) return true;
    // 仅在显式标记的容器内处理，避免全局布局抖动
    return !node.parentElement.closest('[data-convertapk-newline-fix="true"]');
  }
  function replaceNode(node){
    var text = node.nodeValue || '';
    if (text.indexOf('\\n') === -1) return;
    var parts = text.split('\\n');
    var frag = document.createDocumentFragment();
    for (var i = 0; i < parts.length; i++) {
      frag.appendChild(document.createTextNode(parts[i]));
      if (i < parts.length - 1) frag.appendChild(document.createElement('br'));
    }
    if (node.parentNode) node.parentNode.replaceChild(frag, node);
  }
  function walk(){
    if (!document.body) return;
    var walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    var n; var list = [];
    while ((n = walker.nextNode())) {
      if (shouldSkip(n)) continue;
      if (n.nodeValue && n.nodeValue.indexOf('\\n') !== -1) list.push(n);
    }
    for (var i = 0; i < list.length; i++) replaceNode(list[i]);
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', walk);
  } else {
    walk();
  }
})();</script>`;

let insert = "";
if (!html.includes("convertapk-download-helper")) {
  insert += downloadScript + "\n";
}
if (injectNewlineFix && !html.includes("convertapk-newline-fix")) {
  insert += newlineScript + "\n";
}
if (!insert) {
  process.exit(0);
}

if (/<\/body>/i.test(html)) {
  html = html.replace(/<\/body>/i, insert + "</body>");
} else {
  html += "\n" + insert;
}

writeText(indexHtml, html);
NODE
# ============================================
log_info "Step 2: 初始化 Capacitor..."

# 检查是否已安装Capacitor
CAPACITOR_MAJOR="${CAPACITOR_MAJOR:-8}"
CAPACITOR_VERSION_SPEC="^${CAPACITOR_MAJOR}"
CAPACITOR_ASSETS_PACKAGE_SPEC="${CAPACITOR_ASSETS_PACKAGE_SPEC:-@capacitor/assets@3.0.5}"

installCapacitorPackage() {
    local packageName="$1"
    local saveFlag="$2"
    local packageSpec="${packageName}@${CAPACITOR_VERSION_SPEC}"
    if [ -n "$saveFlag" ]; then
        npm install "$saveFlag" "$packageSpec" --legacy-peer-deps
    else
        npm install "$packageSpec" --legacy-peer-deps
    fi
    check_error "install ${packageSpec} failed"
}

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

# 创建 capacitor.config.json（规避 ESM/CJS 与 TypeScript 依赖）
log_info "创建 Capacitor 配置..."
log_info "Force install Capacitor major ${CAPACITOR_MAJOR} ..."
installCapacitorPackage "@capacitor/core" ""
installCapacitorPackage "@capacitor/cli" "-D"
installCapacitorPackage "@capacitor/filesystem" ""
installCapacitorPackage "@capacitor/browser" ""
installCapacitorPackage "@capacitor/share" ""
installCapacitorPackage "@capacitor/android" ""

rm -f capacitor.config.ts capacitor.config.js
WEB_DIR="$WEB_DIR" node -e "const fs=require('fs'); const config={ appId: process.env.PACKAGE_NAME || 'com.example.app', appName: process.env.APP_NAME || 'MyApp', webDir: process.env.WEB_DIR || 'dist', server: { androidScheme: 'https' } }; fs.writeFileSync('capacitor.config.json', JSON.stringify(config, null, 2), 'utf8');"
check_error "生成 capacitor.config.json 失败"

log_success "Capacitor 初始化完成"

# ============================================
# 步骤 3: 添加 Android 平台
# ============================================
log_info "Step 3: 添加 Android 平台..."

# 检查是否已安装android平台
if ! grep -q "@capacitor/android" package.json; then
    log_info "安装 @capacitor/android..."
    npm install "@capacitor/android@${CAPACITOR_VERSION_SPEC}" --legacy-peer-deps
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
log_info "使用 @capacitor/assets 包规格: ${CAPACITOR_ASSETS_PACKAGE_SPEC}"
npm install -D "${CAPACITOR_ASSETS_PACKAGE_SPEC}" --legacy-peer-deps
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
if [ "$TASK_MODE" != "native" ]; then
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

const safeAreaTopMarkers = [
  "var(--convertapk-safe-top",
  "--convertapk-safe-top",
];
const safeAreaBottomMarkers = [
  "safe-area-inset-bottom",
  "--convertapk-safe-bottom",
];
const safeAreaScanExtensions = new Set([
  ".html",
  ".htm",
  ".css",
  ".js",
  ".mjs",
  ".cjs",
  ".ts",
  ".tsx",
  ".vue",
]);
const safeAreaScanMaxBytes = 2 * 1024 * 1024;

function detectFileSafeArea(filePath) {
  const ext = path.extname(filePath).toLowerCase();
  if (!safeAreaScanExtensions.has(ext)) {
    return { top: false, bottom: false };
  }
  let raw;
  try {
    raw = fs.readFileSync(filePath);
  } catch (err) {
    return { top: false, bottom: false };
  }
  const text = raw.subarray(0, safeAreaScanMaxBytes).toString("utf8");
  if (!text) {
    return { top: false, bottom: false };
  }
  return {
    top: safeAreaTopMarkers.some((marker) => text.includes(marker)),
    bottom: safeAreaBottomMarkers.some((marker) => text.includes(marker)),
  };
}

function detectSafeAreaUsage(projectRootDir, androidRootDir) {
  const candidates = [
    path.join(projectRootDir, "index.html"),
    path.join(projectRootDir, "src"),
    path.join(projectRootDir, "dist"),
    path.join(projectRootDir, "build"),
    path.join(androidRootDir, "app", "src", "main", "assets", "public"),
  ];
  const skipDirs = new Set(["node_modules", ".git", ".gradle"]);
  const seen = new Set();
  let topDetected = false;
  let bottomDetected = false;
  for (const candidate of candidates) {
    if (!fs.existsSync(candidate)) {
      continue;
    }
    const stack = [candidate];
    while (stack.length) {
      const current = stack.pop();
      let stat;
      try {
        stat = fs.statSync(current);
      } catch (err) {
        continue;
      }
      if (stat.isDirectory()) {
        let entries = [];
        try {
          entries = fs.readdirSync(current, { withFileTypes: true });
        } catch (err) {
          continue;
        }
        for (const entry of entries) {
          if (skipDirs.has(entry.name)) {
            continue;
          }
          stack.push(path.join(current, entry.name));
        }
        continue;
      }
      if (!stat.isFile()) {
        continue;
      }
      const resolved = path.resolve(current);
      if (seen.has(resolved)) {
        continue;
      }
      seen.add(resolved);
      const safeAreaUsage = detectFileSafeArea(resolved);
      if (!safeAreaUsage.top && !safeAreaUsage.bottom) {
        continue;
      }
      let displayPath = resolved;
      try {
        const relativePath = path.relative(projectRootDir, resolved);
        if (relativePath && !relativePath.startsWith("..") && !path.isAbsolute(relativePath)) {
          displayPath = relativePath;
        }
      } catch (err) {
      }
      if (safeAreaUsage.top && !topDetected) {
        topDetected = true;
        console.log(`[Insets] detected safe-area top usage: ${displayPath}`);
      }
      if (safeAreaUsage.bottom && !bottomDetected) {
        bottomDetected = true;
        console.log(`[Insets] detected safe-area bottom usage: ${displayPath}`);
      }
      if (topDetected && bottomDetected) {
        return { top: true, bottom: true };
      }
    }
  }
  if (!topDetected) {
    console.log("[Insets] safe-area top usage not detected");
  }
  if (!bottomDetected) {
    console.log("[Insets] safe-area bottom usage not detected");
  }
  return { top: topDetected, bottom: bottomDetected };
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
const allowKotlinPatch = taskMode === "convert";
const skipMainActivityInjection =
  String(process.env.CAPACITOR_MINIMAL_MAINACTIVITY || "true").trim().toLowerCase() !== "false";
let useWebViewTopPadding = true;
let useWebViewBottomPadding = true;
if (!skipMainActivityInjection) {
  const safeAreaUsage = detectSafeAreaUsage(projectRoot, androidDir);
  useWebViewTopPadding = true;
  useWebViewBottomPadding = !safeAreaUsage.bottom;
  console.log(
    `[Insets] safe-area top auto-detect ignored; forcing useWebViewTopPadding=true, detectedTop=${safeAreaUsage.top ? "true" : "false"}; ` +
    `[Insets] useWebViewTopPadding=${useWebViewTopPadding ? "true" : "false"}, ` +
    `useWebViewBottomPadding=${useWebViewBottomPadding ? "true" : "false"}`
  );
} else {
  console.log("[MainActivity] skip ConvertAPK MainActivity injection; keep original Capacitor MainActivity");
}
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
        webView.clipToPadding = true
        val useWebViewTopPadding = ${useWebViewTopPadding ? "true" : "false"}
        val useWebViewBottomPadding = ${useWebViewBottomPadding ? "true" : "false"}
        val root = window.decorView
        ViewCompat.setOnApplyWindowInsetsListener(root) { _, insets ->
            val nav = insets.getInsets(WindowInsetsCompat.Type.navigationBars())
            val status = insets.getInsets(WindowInsetsCompat.Type.statusBars())
            val statusStable = insets.getInsetsIgnoringVisibility(WindowInsetsCompat.Type.statusBars())
            val cutout = insets.getInsets(WindowInsetsCompat.Type.displayCutout())
            val topSystemInset = maxOf(status.top, statusStable.top, cutout.top)
            val shouldApplyTopInset = useWebViewTopPadding && !BuildConfig.HIDE_STATUS_BAR
            val topInset = if (shouldApplyTopInset) topSystemInset else 0
            val bottomInset = if (useWebViewBottomPadding) nav.bottom else 0
            webView.setPadding(nav.left, topInset, nav.right, bottomInset)
            webView.post {
                val script = "(function(){var t=" + topInset + ";var b=" + bottomInset +
                    ";var root=document.documentElement;" +
                    "if(root){root.style.setProperty('--convertapk-safe-top', t+'px');root.style.setProperty('--convertapk-safe-bottom', b+'px');}" +
                    "if(document.body){document.body.style.setProperty('--convertapk-safe-top', t+'px');document.body.style.setProperty('--convertapk-safe-bottom', b+'px');}" +
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
        WindowCompat.setDecorFitsSystemWindows(window, false)
        val statusBarColor = resolveStatusBarColor(BuildConfig.STATUS_BAR_BACKGROUND)
        @Suppress("DEPRECATION")
        window.statusBarColor = statusBarColor
        window.decorView.setBackgroundColor(statusBarColor)
        val controller = WindowInsetsControllerCompat(window, window.decorView)
        controller.isAppearanceLightStatusBars = BuildConfig.LIGHT_STATUS_BAR_ICONS
        if (BuildConfig.HIDE_STATUS_BAR) {
            if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.P) {
                val lp = window.attributes
                lp.layoutInDisplayCutoutMode = WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_SHORT_EDGES
                window.attributes = lp
            }
            window.addFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN)
            window.clearFlags(WindowManager.LayoutParams.FLAG_FORCE_NOT_FULLSCREEN)
            @Suppress("DEPRECATION")
            window.decorView.systemUiVisibility =
                View.SYSTEM_UI_FLAG_FULLSCREEN or
                View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN or
                View.SYSTEM_UI_FLAG_LAYOUT_STABLE
            controller.hide(WindowInsetsCompat.Type.statusBars())
            controller.show(WindowInsetsCompat.Type.navigationBars())
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

    private fun resolveStatusBarColor(raw: String): Int {
        val value = raw.trim()
        if (value.equals("transparent", ignoreCase = true) || value.equals("@android:color/transparent", ignoreCase = true)) {
            return android.graphics.Color.TRANSPARENT
        }
        return runCatching { android.graphics.Color.parseColor(value) }.getOrDefault(android.graphics.Color.WHITE)
    }
}
`;
  replacedKotlin = true;
}

const statusBarHidden =
  String(process.env.STATUS_BAR_HIDDEN || "").trim().toLowerCase() === "true";
let statusBarColorRaw = String(process.env.STATUS_BAR_COLOR || "white").trim();
if (
  taskMode === "convert" &&
  !statusBarHidden &&
  ["transparent", "@android:color/transparent"].includes(statusBarColorRaw.toLowerCase())
) {
  statusBarColorRaw = "#FFFFFF";
}
const statusBarColorLower = statusBarColorRaw.toLowerCase();
const statusBarIsWhite =
  statusBarColorLower === "white" ||
  statusBarColorLower === "#ffffff" ||
  statusBarColorLower === "#ffffffff";
const statusBarIsTransparent =
  statusBarColorLower === "transparent" ||
  statusBarColorLower === "@android:color/transparent";
const drawBehindStatusBar = statusBarIsTransparent;
const minimalStatusBarBackground =
  statusBarIsTransparent ? "transparent" : (statusBarIsWhite ? "#FFFFFF" : statusBarColorRaw);
const minimalStatusBarBackgroundLiteral = JSON.stringify(minimalStatusBarBackground);
const minimalLightStatusBarIcons =
  String(process.env.STATUS_BAR_STYLE || "light").trim().toLowerCase() === "dark";

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

if (isKotlin) {
  const topPaddingLiteral = useWebViewTopPadding ? "true" : "false";
  const bottomPaddingLiteral = useWebViewBottomPadding ? "true" : "false";
  text = text.replace(
    /^(\s*)val\s+useWebViewPadding\s*=\s*(?:true|false)\s*$/gm,
    `$1val useWebViewTopPadding = ${topPaddingLiteral}\n$1val useWebViewBottomPadding = ${bottomPaddingLiteral}`
  );
  text = text.replace(
    /^(\s*)val\s+useWebViewTopPadding\s*=\s*(?:true|false)\s*$/gm,
    `$1val useWebViewTopPadding = ${topPaddingLiteral}`
  );
  text = text.replace(
    /^(\s*)val\s+useWebViewBottomPadding\s*=\s*(?:true|false)\s*$/gm,
    `$1val useWebViewBottomPadding = ${bottomPaddingLiteral}`
  );
  text = text.replace(
    /val\s+shouldApplyTopInset\s*=\s*useWebViewPadding\s*&&/g,
    "val shouldApplyTopInset = useWebViewTopPadding &&"
  );
  text = text.replace(
    /val\s+shouldApplyTopInset\s*=\s*useWebViewTopPadding\s*&&\s*(?:\(\s*drawBehindStatusBar\s*\|\|\s*BuildConfig\.HIDE_STATUS_BAR\s*\)|drawBehindStatusBar\s*&&\s*!BuildConfig\.HIDE_STATUS_BAR)/g,
    "val shouldApplyTopInset = useWebViewTopPadding && !BuildConfig.HIDE_STATUS_BAR"
  );
  text = text.replace(
    /val\s+bottomInset\s*=\s*if\s*\(useWebViewPadding\)\s*nav\.bottom\s*else\s*0/g,
    "val bottomInset = if (useWebViewBottomPadding) nav.bottom else 0"
  );
  text = text.replace(
    /^\s*controller\.systemBarsBehavior\s*=\s*WindowInsetsControllerCompat\.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE\s*$/gm,
    ""
  );
  text = text.replace(/\|\s*View\.SYSTEM_UI_FLAG_IMMERSIVE_STICKY/g, "");
  text = text.replace(/\|\s*View\.SYSTEM_UI_FLAG_HIDE_NAVIGATION/g, "");
  text = text.replace(
    /^(\s*)controller\.hide\(WindowInsetsCompat\.Type\.statusBars\(\)\)\s*(?:\r?\n\1controller\.show\(WindowInsetsCompat\.Type\.navigationBars\(\)\))?\s*$/gm,
    "$1controller.hide(WindowInsetsCompat.Type.statusBars())\n$1controller.show(WindowInsetsCompat.Type.navigationBars())"
  );
}

if (!isKotlin) {
  const hasDownloadListener = text.includes("setDownloadListener");
  const hasInsetsListener = text.includes("ViewCompat.setOnApplyWindowInsetsListener(decor");
  const downloadSnippet = hasDownloadListener
    ? ""
    :
    "            webView.setDownloadListener((url, userAgent, contentDisposition, mimeType, contentLength) -> {\n" +
    "                try {\n" +
    "                    Intent intent = new Intent(Intent.ACTION_VIEW);\n" +
    "                    intent.setData(Uri.parse(url));\n" +
    "                    intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);\n" +
    "                    startActivity(intent);\n" +
    "                } catch (Exception ignored) {\n" +
    "                }\n" +
    "            });\n";
  const insetsSnippet = hasInsetsListener
    ? ""
    :
    "            // ConvertAPK: WebView 安全区补偿\n" +
    "            webView.setClipToPadding(true);\n" +
    "            final boolean useWebViewTopPadding = " + (useWebViewTopPadding ? "true" : "false") + ";\n" +
    "            final boolean useWebViewBottomPadding = " + (useWebViewBottomPadding ? "true" : "false") + ";\n" +
    "            final boolean drawBehindStatusBar = " + (drawBehindStatusBar ? "true" : "false") + ";\n" +
    "            final boolean hideStatusBar = " + (statusBarHidden ? "true" : "false") + ";\n" +
    "            View decor = getWindow().getDecorView();\n" +
    "            ViewCompat.setOnApplyWindowInsetsListener(decor, (v, insets) -> {\n" +
    "                Insets nav = insets.getInsets(WindowInsetsCompat.Type.navigationBars());\n" +
    "                Insets status = insets.getInsets(WindowInsetsCompat.Type.statusBars());\n" +
    "                Insets statusStable = insets.getInsetsIgnoringVisibility(WindowInsetsCompat.Type.statusBars());\n" +
    "                Insets cutout = insets.getInsets(WindowInsetsCompat.Type.displayCutout());\n" +
    "                int topSystemInset = Math.max(Math.max(status.top, statusStable.top), cutout.top);\n" +
    "                boolean shouldApplyTopInset = useWebViewTopPadding && !hideStatusBar;\n" +
    "                int topInset = shouldApplyTopInset ? topSystemInset : 0;\n" +
    "                int bottomInset = useWebViewBottomPadding ? nav.bottom : 0;\n" +
    "                webView.setPadding(nav.left, topInset, nav.right, bottomInset);\n" +
    "                webView.post(() -> webView.evaluateJavascript(\n" +
    "                    \"(function(){var t=\" + topInset + \";var b=\" + bottomInset + \";\" +\n" +
    "                    \"var root=document.documentElement;\" +\n" +
    "                    \"if(root){root.style.setProperty('--convertapk-safe-top', t+'px');root.style.setProperty('--convertapk-safe-bottom', b+'px');}\" +\n" +
    "                    \"if(document.body){document.body.style.setProperty('--convertapk-safe-top', t+'px');document.body.style.setProperty('--convertapk-safe-bottom', b+'px');}\" +\n" +
    "                    \"})();\", null));\n" +
    "                return insets;\n" +
    "            });\n" +
    "            ViewCompat.requestApplyInsets(decor);\n";
  const snippet = !downloadSnippet && !insetsSnippet
    ? ""
    :
    "        WebView webView = getBridge() != null ? getBridge().getWebView() : null;\n" +
    "        if (webView != null) {\n" +
    downloadSnippet +
    insetsSnippet +
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
      "        getWindow().addFlags(android.view.WindowManager.LayoutParams.FLAG_FULLSCREEN);\n" +
      "        getWindow().clearFlags(android.view.WindowManager.LayoutParams.FLAG_FORCE_NOT_FULLSCREEN);\n" +
      "        getWindow().setStatusBarColor(android.graphics.Color.TRANSPARENT);\n" +
      "        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.P) {\n" +
      "            android.view.WindowManager.LayoutParams lp = getWindow().getAttributes();\n" +
      "            lp.layoutInDisplayCutoutMode = android.view.WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_SHORT_EDGES;\n" +
      "            getWindow().setAttributes(lp);\n" +
      "        }\n" +
      "        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.R) {\n" +
      "            getWindow().setDecorFitsSystemWindows(false);\n" +
      "            android.view.WindowInsetsController controller = getWindow().getInsetsController();\n" +
      "            if (controller != null) {\n" +
      "                controller.hide(android.view.WindowInsets.Type.statusBars());\n" +
      "                controller.show(android.view.WindowInsets.Type.navigationBars());\n" +
      "            }\n" +
      "        } else {\n" +
      "            android.view.View decorView = getWindow().getDecorView();\n" +
      "            int flags = android.view.View.SYSTEM_UI_FLAG_FULLSCREEN\n" +
      "                | android.view.View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN\n" +
      "                | android.view.View.SYSTEM_UI_FLAG_LAYOUT_STABLE;\n" +
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

if (!isKotlin) {
  const topPaddingLiteral = useWebViewTopPadding ? "true" : "false";
  const bottomPaddingLiteral = useWebViewBottomPadding ? "true" : "false";
  text = text.replace(
    /^(\s*)final\s+boolean\s+useWebViewPadding\s*=\s*(?:true|false)\s*;\s*$/gm,
    `$1final boolean useWebViewTopPadding = ${topPaddingLiteral};\n$1final boolean useWebViewBottomPadding = ${bottomPaddingLiteral};`
  );
  text = text.replace(
    /^(\s*)final\s+boolean\s+useWebViewTopPadding\s*=\s*(?:true|false)\s*;\s*$/gm,
    `$1final boolean useWebViewTopPadding = ${topPaddingLiteral};`
  );
  text = text.replace(
    /^(\s*)final\s+boolean\s+useWebViewBottomPadding\s*=\s*(?:true|false)\s*;\s*$/gm,
    `$1final boolean useWebViewBottomPadding = ${bottomPaddingLiteral};`
  );
  text = text.replace(
    /boolean\s+shouldApplyTopInset\s*=\s*useWebViewPadding\s*&&/g,
    "boolean shouldApplyTopInset = useWebViewTopPadding &&"
  );
  text = text.replace(
    /boolean\s+shouldApplyTopInset\s*=\s*useWebViewTopPadding\s*&&\s*(?:\(\s*drawBehindStatusBar\s*\|\|\s*BuildConfig\.HIDE_STATUS_BAR\s*\)|drawBehindStatusBar\s*&&\s*!hideStatusBar|drawBehindStatusBar\s*&&\s*!BuildConfig\.HIDE_STATUS_BAR)/g,
    "boolean shouldApplyTopInset = useWebViewTopPadding && !BuildConfig.HIDE_STATUS_BAR"
  );
  text = text.replace(
    /int\s+bottomInset\s*=\s*useWebViewPadding\s*\?\s*nav\.bottom\s*:\s*0\s*;/g,
    "int bottomInset = useWebViewBottomPadding ? nav.bottom : 0;"
  );
  text = text.replace(
    /^\s*controller\.setSystemBarsBehavior\(\s*WindowInsetsControllerCompat\.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE\s*\)\s*;\s*$/gm,
    ""
  );
  text = text.replace(
    /^\s*controller\.setSystemBarsBehavior\(\s*android\.view\.WindowInsetsController\.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE\s*\)\s*;\s*$/gm,
    ""
  );
  text = text.replace(/\|\s*android\.view\.View\.SYSTEM_UI_FLAG_IMMERSIVE_STICKY/g, "");
  text = text.replace(/\|\s*android\.view\.View\.SYSTEM_UI_FLAG_HIDE_NAVIGATION/g, "");
  text = text.replace(
    /^(\s*)controller\.hide\(WindowInsetsCompat\.Type\.statusBars\(\)\)\s*;\s*(?:\r?\n\1controller\.show\(WindowInsetsCompat\.Type\.navigationBars\(\)\)\s*;)?\s*$/gm,
    "$1controller.hide(WindowInsetsCompat.Type.statusBars());\n$1controller.show(WindowInsetsCompat.Type.navigationBars());"
  );
  text = text.replace(
    /^(\s*)controller\.hide\(android\.view\.WindowInsets\.Type\.statusBars\(\)\)\s*;\s*(?:\r?\n\1controller\.show\(android\.view\.WindowInsets\.Type\.navigationBars\(\)\)\s*;)?\s*$/gm,
    "$1controller.hide(android.view.WindowInsets.Type.statusBars());\n$1controller.show(android.view.WindowInsets.Type.navigationBars());"
  );
}

if (!useWebViewTopPadding || !useWebViewBottomPadding) {
  const topExpr = useWebViewTopPadding ? "topInset" : "0";
  const bottomExpr = useWebViewBottomPadding ? "nav.bottom" : "0";
  text = text.replace(
    /webView\.setPadding\(\s*nav\.left\s*,\s*topInset\s*,\s*nav\.right\s*,\s*nav\.bottom\s*\);/g,
    `webView.setPadding(nav.left, ${topExpr}, nav.right, ${bottomExpr});`
  );
  text = text.replace(
    /webView\.setPadding\(\s*nav\.left\s*,\s*topInset\s*,\s*nav\.right\s*,\s*nav\.bottom\s*\)/g,
    `webView.setPadding(nav.left, ${topExpr}, nav.right, ${bottomExpr})`
  );
  text = text.replace(
    /\+\s*topInset\s*\+\s*";var b="\s*\+\s*nav\.bottom\s*\+/g,
    `+ ${topExpr} + ";var b=" + ${bottomExpr} +`
  );
}

function ensureImportLine(source, importLine) {
  if (source.includes(importLine)) {
    return source;
  }
  const lines = source.split(/\r?\n/);
  let insertAt = -1;
  for (let i = 0; i < lines.length; i++) {
    if (lines[i].startsWith("import ")) {
      insertAt = i + 1;
    }
  }
  if (insertAt === -1) {
    for (let i = 0; i < lines.length; i++) {
      if (lines[i].startsWith("package ")) {
        insertAt = i + 1;
        break;
      }
    }
  }
  if (insertAt === -1) {
    insertAt = 0;
  }
  lines.splice(insertAt, 0, importLine);
  return lines.join("\n");
}

function insertAfterMainActivityClassOpen(source, insert, isKotlinFile = false) {
  const match = source.match(/class\s+MainActivity\b[^{]*\{/m);
  if (match) {
    const idx = source.indexOf(match[0]) + match[0].length;
    return source.slice(0, idx) + "\n" + insert + source.slice(idx);
  }
  if (isKotlinFile) {
    const kotlinDecl = source.match(/class\s+MainActivity\b[^\n]*/m);
    if (kotlinDecl) {
      const rawDecl = kotlinDecl[0];
      const decl = rawDecl.trimEnd();
      if (!decl.includes("{")) {
        const start = source.indexOf(rawDecl);
        const end = start + rawDecl.length;
        const replacement = `${decl} {\n${insert}}\n`;
        return source.slice(0, start) + replacement + source.slice(end);
      }
    }
  }
  return source;
}

function removeMinimalDoubleClickExit(source) {
  source = source.replace(
    /\n?\s*\/\/ ConvertAPK: double-click-exit state \(minimal\)\n\s*(?:private var|private long)\s+convertApkLastBackPressedAt[^\n]*\n?/gm,
    "\n"
  );
  source = source.replace(
    /\n?\s*\/\/ ConvertAPK: double-click-exit start \(minimal\)\n[\s\S]*?\n\s*\/\/ ConvertAPK: double-click-exit end \(minimal\)\n?/gm,
    "\n"
  );
  return source;
}

function injectMinimalSnippetIntoOnCreate(source, isKotlinFile, snippet) {
  if (!snippet || !snippet.trim()) {
    return source;
  }
  if (source.includes(snippet.trim())) {
    return source;
  }

  if (isKotlinFile) {
    const withSuper = /(override\s+fun\s+onCreate\s*\([^)]*\)\s*\{[\s\S]*?super\.onCreate\s*\(\s*savedInstanceState\s*\)\s*)/m;
    if (withSuper.test(source)) {
      return source.replace(withSuper, `$1\n${snippet}`);
    }
    const methodStart = /(override\s+fun\s+onCreate\s*\([^)]*\)\s*\{)/m;
    if (methodStart.test(source)) {
      return source.replace(methodStart, `$1\n${snippet}`);
    }
    const classClose = source.lastIndexOf("}");
    if (classClose !== -1) {
      const createMethod =
        "    override fun onCreate(savedInstanceState: Bundle?) {\n" +
        "        super.onCreate(savedInstanceState)\n" +
        snippet +
        "    }\n\n";
      return source.slice(0, classClose) + "\n" + createMethod + source.slice(classClose);
    }
    return source;
  }

  const withSuper = /((?:@Override\s+)?protected\s+void\s+onCreate\s*\([^)]*\)\s*\{[\s\S]*?super\.onCreate\s*\(\s*savedInstanceState\s*\)\s*;\s*)/m;
  if (withSuper.test(source)) {
    return source.replace(withSuper, `$1\n${snippet}`);
  }
  const methodStart = /((?:@Override\s+)?protected\s+void\s+onCreate\s*\([^)]*\)\s*\{)/m;
  if (methodStart.test(source)) {
    return source.replace(methodStart, `$1\n${snippet}`);
  }
  const classClose = source.lastIndexOf("}");
  if (classClose !== -1) {
    const createMethod =
      "    @Override\n" +
      "    protected void onCreate(Bundle savedInstanceState) {\n" +
      "        super.onCreate(savedInstanceState);\n" +
      snippet +
      "    }\n\n";
    return source.slice(0, classClose) + "\n" + createMethod + source.slice(classClose);
  }
  return source;
}

function syncMinimalDoubleClickExit(source, isKotlinFile, enabled) {
  let updated = removeMinimalDoubleClickExit(source);
  if (!enabled) {
    return updated;
  }
  if (isKotlinFile) {
    updated = ensureImportLine(updated, "import android.widget.Toast");
    updated = ensureImportLine(updated, "import android.os.Bundle");
    updated = ensureImportLine(updated, "import androidx.activity.OnBackPressedCallback");
    const fieldBlock =
      "    // ConvertAPK: double-click-exit state (minimal)\n" +
      "    private var convertApkLastBackPressedAt: Long = 0L\n";
    const onCreateSnippet =
      "        // ConvertAPK: double-click-exit start (minimal)\n" +
      "        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {\n" +
      "            override fun handleOnBackPressed() {\n" +
      "                val webView = bridge?.webView\n" +
      "                if (webView != null && webView.canGoBack()) {\n" +
      "                    webView.goBack()\n" +
      "                    return\n" +
      "                }\n" +
      "                val now = System.currentTimeMillis()\n" +
      "                if (now - convertApkLastBackPressedAt < 2000) {\n" +
      "                    finish()\n" +
      "                } else {\n" +
      "                    convertApkLastBackPressedAt = now\n" +
      "                    Toast.makeText(this@MainActivity, \"Press back again to exit\", Toast.LENGTH_SHORT).show()\n" +
      "                }\n" +
      "            }\n" +
      "        })\n" +
      "    // ConvertAPK: double-click-exit end (minimal)\n";
    updated = insertAfterMainActivityClassOpen(updated, fieldBlock, true);
    updated = injectMinimalSnippetIntoOnCreate(updated, true, onCreateSnippet);
    return updated;
  }
  updated = ensureImportLine(updated, "import android.widget.Toast;");
  updated = ensureImportLine(updated, "import android.os.Bundle;");
  updated = ensureImportLine(updated, "import androidx.activity.OnBackPressedCallback;");
  const fieldBlock =
    "    // ConvertAPK: double-click-exit state (minimal)\n" +
    "    private long convertApkLastBackPressedAt = 0L;\n";
  const onCreateSnippet =
    "        // ConvertAPK: double-click-exit start (minimal)\n" +
    "        getOnBackPressedDispatcher().addCallback(this, new OnBackPressedCallback(true) {\n" +
    "            @Override\n" +
    "            public void handleOnBackPressed() {\n" +
    "                android.webkit.WebView webView = getBridge() != null ? getBridge().getWebView() : null;\n" +
    "                if (webView != null && webView.canGoBack()) {\n" +
    "                    webView.goBack();\n" +
    "                    return;\n" +
    "                }\n" +
    "                long now = System.currentTimeMillis();\n" +
    "                if (now - convertApkLastBackPressedAt < 2000) {\n" +
    "                    finish();\n" +
    "                } else {\n" +
    "                    convertApkLastBackPressedAt = now;\n" +
    "                    Toast.makeText(MainActivity.this, \"Press back again to exit\", Toast.LENGTH_SHORT).show();\n" +
    "                }\n" +
    "            }\n" +
    "        });\n" +
    "    // ConvertAPK: double-click-exit end (minimal)\n";
  updated = insertAfterMainActivityClassOpen(updated, fieldBlock, false);
  updated = injectMinimalSnippetIntoOnCreate(updated, false, onCreateSnippet);
  return updated;
}

function removeMinimalDownloadListener(source) {
  source = source.replace(
    /\n?\s*\/\/ ConvertAPK: download start \(minimal\)\n[\s\S]*?\n\s*\/\/ ConvertAPK: download end \(minimal\)\n?/gm,
    "\n"
  );
  return source;
}

function syncMinimalDownloadListener(source, isKotlinFile, enabled, downloadModeValue) {
  let updated = removeMinimalDownloadListener(source);
  if (!enabled) {
    return updated;
  }
  const normalizedDownloadMode = downloadModeValue === "silent" ? "silent" : "picker";
  if (isKotlinFile) {
    updated = insertAfterMainActivityClassOpen(updated, "", true);
    updated = ensureImportLine(updated, "import android.app.DownloadManager");
    updated = ensureImportLine(updated, "import android.content.Intent");
    updated = ensureImportLine(updated, "import android.net.Uri");
    updated = ensureImportLine(updated, "import android.os.Bundle");
    updated = ensureImportLine(updated, "import android.os.Environment");
    updated = ensureImportLine(updated, "import android.webkit.CookieManager");
    updated = ensureImportLine(updated, "import android.webkit.URLUtil");
    updated = ensureImportLine(updated, "import android.widget.Toast");
    const onCreateSnippet =
      "        // ConvertAPK: download start (minimal)\n" +
      "        val webView = bridge?.webView\n" +
      "        if (webView != null) {\n" +
      "            webView.setDownloadListener { url, userAgent, contentDisposition, mimeType, _ ->\n" +
      "                try {\n" +
      "                    val safeUrl = (url ?: \"\").trim()\n" +
      "                    if (safeUrl.isBlank()) {\n" +
      "                        return@setDownloadListener\n" +
      "                    }\n" +
      "                    val lowerUrl = safeUrl.lowercase()\n" +
      "                    val isHttp = lowerUrl.startsWith(\"http://\") || lowerUrl.startsWith(\"https://\")\n" +
      "                    if (!isHttp) {\n" +
      "                        return@setDownloadListener\n" +
      "                    }\n" +
      "                    val downloadMode = \"" + normalizedDownloadMode + "\"\n" +
      "                    if (downloadMode != \"silent\") {\n" +
      "                        try {\n" +
      "                            val intent = Intent(Intent.ACTION_VIEW, Uri.parse(safeUrl))\n" +
      "                            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)\n" +
      "                            startActivity(intent)\n" +
      "                            return@setDownloadListener\n" +
      "                        } catch (_: Exception) {\n" +
      "                        }\n" +
      "                    }\n" +
      "                    val request = DownloadManager.Request(Uri.parse(safeUrl))\n" +
      "                    if (!mimeType.isNullOrBlank()) {\n" +
      "                        request.setMimeType(mimeType)\n" +
      "                    }\n" +
      "                    if (!userAgent.isNullOrBlank()) {\n" +
      "                        request.addRequestHeader(\"User-Agent\", userAgent)\n" +
      "                    }\n" +
      "                    val cookie = CookieManager.getInstance().getCookie(safeUrl)\n" +
      "                    if (!cookie.isNullOrBlank()) {\n" +
      "                        request.addRequestHeader(\"cookie\", cookie)\n" +
      "                    }\n" +
      "                    val fileName = URLUtil.guessFileName(safeUrl, contentDisposition, mimeType)\n" +
      "                    request.setTitle(fileName)\n" +
      "                    request.setDescription(safeUrl)\n" +
      "                    request.setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED)\n" +
      "                    request.setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS, fileName)\n" +
      "                    val dm = getSystemService(DOWNLOAD_SERVICE) as DownloadManager\n" +
      "                    dm.enqueue(request)\n" +
      "                } catch (_: Exception) {\n" +
      "                    Toast.makeText(this@MainActivity, \"Download failed\", Toast.LENGTH_SHORT).show()\n" +
      "                }\n" +
      "            }\n" +
      "        }\n" +
      "    // ConvertAPK: download end (minimal)\n";
    updated = injectMinimalSnippetIntoOnCreate(updated, true, onCreateSnippet);
    return updated;
  }
  updated = ensureImportLine(updated, "import android.app.DownloadManager;");
  updated = ensureImportLine(updated, "import android.content.Intent;");
  updated = ensureImportLine(updated, "import android.net.Uri;");
  updated = ensureImportLine(updated, "import android.os.Bundle;");
  updated = ensureImportLine(updated, "import android.os.Environment;");
  updated = ensureImportLine(updated, "import android.webkit.CookieManager;");
  updated = ensureImportLine(updated, "import android.webkit.URLUtil;");
  updated = ensureImportLine(updated, "import android.widget.Toast;");
  const onCreateSnippet =
    "        // ConvertAPK: download start (minimal)\n" +
    "        android.webkit.WebView webView = getBridge() != null ? getBridge().getWebView() : null;\n" +
    "        if (webView != null) {\n" +
    "            webView.setDownloadListener((url, userAgent, contentDisposition, mimeType, _contentLength) -> {\n" +
    "                try {\n" +
    "                    String safeUrl = url == null ? \"\" : url.trim();\n" +
    "                    if (safeUrl.isEmpty()) {\n" +
    "                        return;\n" +
    "                    }\n" +
    "                    String lowerUrl = safeUrl.toLowerCase();\n" +
    "                    boolean isHttp = lowerUrl.startsWith(\"http://\") || lowerUrl.startsWith(\"https://\");\n" +
    "                    if (!isHttp) {\n" +
    "                        return;\n" +
    "                    }\n" +
    "                    String downloadMode = \"" + normalizedDownloadMode + "\";\n" +
    "                    if (!\"silent\".equals(downloadMode)) {\n" +
    "                        try {\n" +
    "                            Intent intent = new Intent(Intent.ACTION_VIEW, Uri.parse(safeUrl));\n" +
    "                            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);\n" +
    "                            startActivity(intent);\n" +
    "                            return;\n" +
    "                        } catch (Exception ignored) {\n" +
    "                        }\n" +
    "                    }\n" +
    "                    DownloadManager.Request request = new DownloadManager.Request(Uri.parse(safeUrl));\n" +
    "                    if (mimeType != null && !mimeType.isEmpty()) {\n" +
    "                        request.setMimeType(mimeType);\n" +
    "                    }\n" +
    "                    if (userAgent != null && !userAgent.isEmpty()) {\n" +
    "                        request.addRequestHeader(\"User-Agent\", userAgent);\n" +
    "                    }\n" +
    "                    String cookie = CookieManager.getInstance().getCookie(safeUrl);\n" +
    "                    if (cookie != null && !cookie.isEmpty()) {\n" +
    "                        request.addRequestHeader(\"cookie\", cookie);\n" +
    "                    }\n" +
    "                    String fileName = URLUtil.guessFileName(safeUrl, contentDisposition, mimeType);\n" +
    "                    request.setTitle(fileName);\n" +
    "                    request.setDescription(safeUrl);\n" +
    "                    request.setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);\n" +
    "                    request.setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS, fileName);\n" +
    "                    DownloadManager dm = (DownloadManager) getSystemService(DOWNLOAD_SERVICE);\n" +
    "                    if (dm != null) {\n" +
    "                        dm.enqueue(request);\n" +
    "                    }\n" +
    "                } catch (Exception ignored) {\n" +
    "                    Toast.makeText(MainActivity.this, \"Download failed\", Toast.LENGTH_SHORT).show();\n" +
    "                }\n" +
    "            });\n" +
    "        }\n" +
    "    // ConvertAPK: download end (minimal)\n";
  updated = injectMinimalSnippetIntoOnCreate(updated, false, onCreateSnippet);
  return updated;
}

function removeDisablePinchZoom(source) {
  source = source.replace(
    /\n?\s*\/\/ ConvertAPK: disable-zoom start \(minimal\)\n[\s\S]*?\n\s*\/\/ ConvertAPK: disable-zoom end \(minimal\)\n?/gm,
    "\n"
  );
  return source;
}

function syncDisablePinchZoom(source, isKotlinFile, enabled) {
  let updated = removeDisablePinchZoom(source);
  if (!enabled) {
    return updated;
  }
  if (isKotlinFile) {
    updated = insertAfterMainActivityClassOpen(updated, "", true);
    const onCreateSnippet =
      "        // ConvertAPK: disable-zoom start (minimal)\n" +
      "        val convertApkWebView = bridge?.webView\n" +
      "        if (convertApkWebView != null) {\n" +
      "            val settings = convertApkWebView.settings\n" +
      "            settings.setSupportZoom(false)\n" +
      "            settings.builtInZoomControls = false\n" +
      "            settings.displayZoomControls = false\n" +
      "        }\n" +
      "        // ConvertAPK: disable-zoom end (minimal)\n";
    updated = injectMinimalSnippetIntoOnCreate(updated, true, onCreateSnippet);
    return updated;
  }
  const onCreateSnippet =
    "        // ConvertAPK: disable-zoom start (minimal)\n" +
    "        android.webkit.WebView convertApkWebView = getBridge() != null ? getBridge().getWebView() : null;\n" +
    "        if (convertApkWebView != null) {\n" +
    "            android.webkit.WebSettings settings = convertApkWebView.getSettings();\n" +
    "            settings.setSupportZoom(false);\n" +
    "            settings.setBuiltInZoomControls(false);\n" +
    "            settings.setDisplayZoomControls(false);\n" +
    "        }\n" +
    "        // ConvertAPK: disable-zoom end (minimal)\n";
  updated = injectMinimalSnippetIntoOnCreate(updated, false, onCreateSnippet);
  return updated;
}

function removeMinimalStatusBarHidden(source) {
  source = source.replace(
    /\n?\s*\/\/ ConvertAPK: status-bar-hidden start \(minimal\)\n[\s\S]*?\n\s*\/\/ ConvertAPK: status-bar-hidden end \(minimal\)\n?/gm,
    "\n"
  );
  return source;
}

function removeMinimalStatusBarColor(source) {
  source = source.replace(
    /\n?\s*\/\/ ConvertAPK：状态栏颜色开始（极简）\n[\s\S]*?\n\s*\/\/ ConvertAPK：状态栏颜色结束（极简）\n?/gm,
    "\n"
  );
  return source;
}

function syncMinimalStatusBarHidden(source, isKotlinFile, enabled) {
  let updated = removeMinimalStatusBarHidden(source);
  if (!enabled) {
    return updated;
  }
  if (isKotlinFile) {
    updated = ensureImportLine(updated, "import android.os.Build");
    updated = ensureImportLine(updated, "import android.os.Bundle");
    updated = ensureImportLine(updated, "import android.view.View");
    updated = ensureImportLine(updated, "import android.view.WindowInsets");
    updated = ensureImportLine(updated, "import android.view.WindowManager");
    const methodBlock =
      "    // ConvertAPK: status-bar-hidden start (minimal)\n" +
      "    override fun onCreate(savedInstanceState: Bundle?) {\n" +
      "        super.onCreate(savedInstanceState)\n" +
      "        normalizeConvertApkWebViewInsets()\n" +
      "        applyConvertApkStatusBarHidden()\n" +
      "    }\n\n" +
      "    override fun onWindowFocusChanged(hasFocus: Boolean) {\n" +
      "        super.onWindowFocusChanged(hasFocus)\n" +
      "        if (hasFocus) {\n" +
      "            normalizeConvertApkWebViewInsets()\n" +
      "            applyConvertApkStatusBarHidden()\n" +
      "        }\n" +
      "    }\n\n" +
      "    private fun normalizeConvertApkWebViewInsets() {\n" +
      "        val convertApkWebView = bridge?.webView ?: return\n" +
      "        convertApkWebView.setPadding(0, 0, 0, 0)\n" +
      "        convertApkWebView.clipToPadding = false\n" +
      "        val parentView = convertApkWebView.parent as? View\n" +
      "        if (parentView != null) {\n" +
      "            parentView.setPadding(0, 0, 0, 0)\n" +
      "            parentView.fitsSystemWindows = false\n" +
      "        }\n" +
      "    }\n\n" +
      "    private fun applyConvertApkStatusBarHidden() {\n" +
      "        @Suppress(\"DEPRECATION\")\n" +
      "        window.addFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN)\n" +
      "        @Suppress(\"DEPRECATION\")\n" +
      "        window.clearFlags(WindowManager.LayoutParams.FLAG_FORCE_NOT_FULLSCREEN)\n" +
      "        @Suppress(\"DEPRECATION\")\n" +
      "        window.statusBarColor = android.graphics.Color.TRANSPARENT\n" +
      "        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {\n" +
      "            val lp = window.attributes\n" +
      "            lp.layoutInDisplayCutoutMode = WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_SHORT_EDGES\n" +
      "            window.attributes = lp\n" +
      "        }\n" +
      "        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {\n" +
      "            window.setDecorFitsSystemWindows(false)\n" +
      "            val controller = window.insetsController\n" +
      "            if (controller != null) {\n" +
      "                controller.hide(WindowInsets.Type.statusBars())\n" +
      "                controller.show(WindowInsets.Type.navigationBars())\n" +
      "            }\n" +
      "        } else {\n" +
      "            @Suppress(\"DEPRECATION\")\n" +
      "            window.addFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN)\n" +
      "            @Suppress(\"DEPRECATION\")\n" +
      "            window.decorView.systemUiVisibility =\n" +
      "                View.SYSTEM_UI_FLAG_FULLSCREEN or\n" +
      "                View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN or\n" +
      "                View.SYSTEM_UI_FLAG_LAYOUT_STABLE\n" +
      "        }\n" +
      "    }\n" +
      "    // ConvertAPK: status-bar-hidden end (minimal)\n";
    const normalized = insertAfterMainActivityClassOpen(updated, "", true);
    updated = normalized;
    const classClose = updated.lastIndexOf("}");
    if (classClose !== -1) {
      updated = updated.slice(0, classClose) + "\n" + methodBlock + "\n" + updated.slice(classClose);
    }
    return updated;
  }
  updated = ensureImportLine(updated, "import android.os.Build;");
  updated = ensureImportLine(updated, "import android.os.Bundle;");
  updated = ensureImportLine(updated, "import android.view.View;");
  updated = ensureImportLine(updated, "import android.view.WindowInsets;");
  updated = ensureImportLine(updated, "import android.view.WindowManager;");
  const methodBlock =
    "    // ConvertAPK: status-bar-hidden start (minimal)\n" +
    "    @Override\n" +
    "    protected void onCreate(Bundle savedInstanceState) {\n" +
    "        super.onCreate(savedInstanceState);\n" +
    "        normalizeConvertApkWebViewInsets();\n" +
    "        applyConvertApkStatusBarHidden();\n" +
    "    }\n\n" +
    "    @Override\n" +
    "    public void onWindowFocusChanged(boolean hasFocus) {\n" +
    "        super.onWindowFocusChanged(hasFocus);\n" +
    "        if (hasFocus) {\n" +
    "            normalizeConvertApkWebViewInsets();\n" +
    "            applyConvertApkStatusBarHidden();\n" +
    "        }\n" +
    "    }\n\n" +
    "    private void normalizeConvertApkWebViewInsets() {\n" +
    "        android.webkit.WebView convertApkWebView = getBridge() != null ? getBridge().getWebView() : null;\n" +
    "        if (convertApkWebView == null) {\n" +
    "            return;\n" +
    "        }\n" +
    "        convertApkWebView.setPadding(0, 0, 0, 0);\n" +
    "        convertApkWebView.setClipToPadding(false);\n" +
    "        android.view.ViewParent parent = convertApkWebView.getParent();\n" +
    "        if (parent instanceof View) {\n" +
    "            View parentView = (View) parent;\n" +
    "            parentView.setPadding(0, 0, 0, 0);\n" +
    "            parentView.setFitsSystemWindows(false);\n" +
    "        }\n" +
    "    }\n\n" +
    "    private void applyConvertApkStatusBarHidden() {\n" +
    "        getWindow().addFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN);\n" +
    "        getWindow().clearFlags(WindowManager.LayoutParams.FLAG_FORCE_NOT_FULLSCREEN);\n" +
    "        getWindow().setStatusBarColor(android.graphics.Color.TRANSPARENT);\n" +
    "        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {\n" +
    "            WindowManager.LayoutParams lp = getWindow().getAttributes();\n" +
    "            lp.layoutInDisplayCutoutMode = WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_SHORT_EDGES;\n" +
    "            getWindow().setAttributes(lp);\n" +
    "        }\n" +
    "        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {\n" +
    "            getWindow().setDecorFitsSystemWindows(false);\n" +
    "            android.view.WindowInsetsController controller = getWindow().getInsetsController();\n" +
    "            if (controller != null) {\n" +
    "                controller.hide(WindowInsets.Type.statusBars());\n" +
    "                controller.show(WindowInsets.Type.navigationBars());\n" +
    "            }\n" +
    "        } else {\n" +
    "            getWindow().addFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN);\n" +
    "            getWindow().getDecorView().setSystemUiVisibility(\n" +
    "                View.SYSTEM_UI_FLAG_FULLSCREEN |\n" +
    "                View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN |\n" +
    "                View.SYSTEM_UI_FLAG_LAYOUT_STABLE\n" +
    "            );\n" +
    "        }\n" +
    "    }\n" +
    "    // ConvertAPK: status-bar-hidden end (minimal)\n";
  const normalized = insertAfterMainActivityClassOpen(updated, "", false);
  updated = normalized;
  const classClose = updated.lastIndexOf("}");
  if (classClose !== -1) {
    updated = updated.slice(0, classClose) + "\n" + methodBlock + "\n" + updated.slice(classClose);
  }
  return updated;
}

function syncMinimalStatusBarColor(source, isKotlinFile, enabled) {
  let updated = removeMinimalStatusBarColor(source);
  if (!enabled) {
    return updated;
  }
  if (isKotlinFile) {
    updated = ensureImportLine(updated, "import android.graphics.Color");
    updated = ensureImportLine(updated, "import android.os.Build");
    updated = ensureImportLine(updated, "import android.os.Bundle");
    updated = ensureImportLine(updated, "import android.view.Gravity");
    updated = ensureImportLine(updated, "import android.view.View");
    updated = ensureImportLine(updated, "import android.view.ViewGroup");
    updated = ensureImportLine(updated, "import android.view.WindowInsets");
    updated = ensureImportLine(updated, "import android.view.WindowInsetsController");
    updated = ensureImportLine(updated, "import android.view.WindowManager");
    updated = ensureImportLine(updated, "import android.widget.FrameLayout");
    const methodBlock =
      "    // ConvertAPK：状态栏颜色开始（极简）\n" +
      "    override fun onCreate(savedInstanceState: Bundle?) {\n" +
      "        super.onCreate(savedInstanceState)\n" +
      "        applyConvertApkStatusBarColor()\n" +
      "    }\n\n" +
      "    override fun onWindowFocusChanged(hasFocus: Boolean) {\n" +
      "        super.onWindowFocusChanged(hasFocus)\n" +
      "        if (hasFocus) {\n" +
      "            applyConvertApkStatusBarColor()\n" +
      "        }\n" +
      "    }\n\n" +
      "    private fun applyConvertApkStatusBarColor() {\n" +
      "        val statusBarColor = resolveConvertApkStatusBarColor(" + minimalStatusBarBackgroundLiteral + ")\n" +
      "        @Suppress(\"DEPRECATION\")\n" +
      "        window.statusBarColor = statusBarColor\n" +
      "        window.decorView.setBackgroundColor(statusBarColor)\n" +
      "        @Suppress(\"DEPRECATION\")\n" +
      "        window.clearFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN)\n" +
      "        @Suppress(\"DEPRECATION\")\n" +
      "        window.addFlags(WindowManager.LayoutParams.FLAG_FORCE_NOT_FULLSCREEN)\n" +
      "        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {\n" +
      "            window.setDecorFitsSystemWindows(false)\n" +
      "            val controller = window.insetsController\n" +
      "            if (controller != null) {\n" +
      "                controller.show(WindowInsets.Type.statusBars())\n" +
      "                val lightMask = WindowInsetsController.APPEARANCE_LIGHT_STATUS_BARS\n" +
      "                controller.setSystemBarsAppearance(if (" + (minimalLightStatusBarIcons ? "true" : "false") + ") lightMask else 0, lightMask)\n" +
      "            }\n" +
      "        } else {\n" +
      "            @Suppress(\"DEPRECATION\")\n" +
      "            var visibility = View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN or View.SYSTEM_UI_FLAG_LAYOUT_STABLE\n" +
      "            if (" + (minimalLightStatusBarIcons ? "true" : "false") + " && Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {\n" +
      "                visibility = visibility or View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR\n" +
      "            }\n" +
      "            @Suppress(\"DEPRECATION\")\n" +
      "            window.decorView.systemUiVisibility = visibility\n" +
      "        }\n" +
      "        syncConvertApkStatusBarOverlay(statusBarColor)\n" +
      "    }\n\n" +
      "    private fun syncConvertApkStatusBarOverlay(statusBarColor: Int) {\n" +
      "        val contentRoot = findViewById<ViewGroup>(android.R.id.content) ?: return\n" +
      "        val topInset = readConvertApkStatusBarHeightPx()\n" +
      "        val convertApkWebView = bridge?.webView\n" +
      "        if (convertApkWebView != null) {\n" +
      "            convertApkWebView.clipToPadding = true\n" +
      "            convertApkWebView.setPadding(convertApkWebView.paddingLeft, topInset, convertApkWebView.paddingRight, convertApkWebView.paddingBottom)\n" +
      "            convertApkWebView.post {\n" +
      "                val script = \"(function(){var t=\" + topInset + \";var root=document.documentElement;\" +\n" +
      "                    \"if(root){root.style.setProperty('--convertapk-safe-top', t+'px');}\" +\n" +
      "                    \"if(document.body){document.body.style.setProperty('--convertapk-safe-top', t+'px');}\" +\n" +
      "                    \"})();\"\n" +
      "                convertApkWebView.evaluateJavascript(script, null)\n" +
      "            }\n" +
      "        }\n" +
      "        val tag = \"convertapk-status-bar-overlay\"\n" +
      "        val overlay = contentRoot.findViewWithTag<View>(tag) ?: View(this).also {\n" +
      "            it.tag = tag\n" +
      "            contentRoot.addView(\n" +
      "                it,\n" +
      "                FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, topInset).apply {\n" +
      "                    gravity = Gravity.TOP\n" +
      "                },\n" +
      "            )\n" +
      "        }\n" +
      "        overlay.setBackgroundColor(statusBarColor)\n" +
      "        val params = overlay.layoutParams\n" +
      "        if (params != null && params.height != topInset) {\n" +
      "            params.height = topInset\n" +
      "            overlay.layoutParams = params\n" +
      "        }\n" +
      "        overlay.bringToFront()\n" +
      "    }\n\n" +
      "    private fun readConvertApkStatusBarHeightPx(): Int {\n" +
      "        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {\n" +
      "            val insetTop = window.decorView.rootWindowInsets?.getInsets(WindowInsets.Type.statusBars())?.top ?: 0\n" +
      "            if (insetTop > 0) return insetTop\n" +
      "        }\n" +
      "        val resId = resources.getIdentifier(\"status_bar_height\", \"dimen\", \"android\")\n" +
      "        if (resId > 0) return resources.getDimensionPixelSize(resId)\n" +
      "        return (24 * resources.displayMetrics.density).toInt()\n" +
      "    }\n\n" +
      "    private fun resolveConvertApkStatusBarColor(raw: String?): Int {\n" +
      "        val value = raw?.trim().orEmpty()\n" +
      "        if (value.equals(\"transparent\", ignoreCase = true) || value.equals(\"@android:color/transparent\", ignoreCase = true)) {\n" +
      "            return Color.TRANSPARENT\n" +
      "        }\n" +
      "        return runCatching { Color.parseColor(value) }.getOrDefault(Color.WHITE)\n" +
      "    }\n" +
      "    // ConvertAPK：状态栏颜色结束（极简）\n";
    const normalized = insertAfterMainActivityClassOpen(updated, "", true);
    updated = normalized;
    const classClose = updated.lastIndexOf("}");
    if (classClose !== -1) {
      updated = updated.slice(0, classClose) + "\n" + methodBlock + "\n" + updated.slice(classClose);
    }
    return updated;
  }
  updated = ensureImportLine(updated, "import android.graphics.Color;");
  updated = ensureImportLine(updated, "import android.os.Build;");
  updated = ensureImportLine(updated, "import android.os.Bundle;");
  updated = ensureImportLine(updated, "import android.view.Gravity;");
  updated = ensureImportLine(updated, "import android.view.View;");
  updated = ensureImportLine(updated, "import android.view.ViewGroup;");
  updated = ensureImportLine(updated, "import android.view.WindowInsets;");
  updated = ensureImportLine(updated, "import android.view.WindowInsetsController;");
  updated = ensureImportLine(updated, "import android.view.WindowManager;");
  updated = ensureImportLine(updated, "import android.widget.FrameLayout;");
  const methodBlock =
    "    // ConvertAPK：状态栏颜色开始（极简）\n" +
    "    @Override\n" +
    "    protected void onCreate(Bundle savedInstanceState) {\n" +
    "        super.onCreate(savedInstanceState);\n" +
    "        applyConvertApkStatusBarColor();\n" +
    "    }\n\n" +
    "    @Override\n" +
    "    public void onWindowFocusChanged(boolean hasFocus) {\n" +
    "        super.onWindowFocusChanged(hasFocus);\n" +
    "        if (hasFocus) {\n" +
    "            applyConvertApkStatusBarColor();\n" +
    "        }\n" +
    "    }\n\n" +
    "    private void applyConvertApkStatusBarColor() {\n" +
    "        int statusBarColor = resolveConvertApkStatusBarColor(" + minimalStatusBarBackgroundLiteral + ");\n" +
    "        getWindow().setStatusBarColor(statusBarColor);\n" +
    "        getWindow().getDecorView().setBackgroundColor(statusBarColor);\n" +
    "        getWindow().clearFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN);\n" +
    "        getWindow().addFlags(WindowManager.LayoutParams.FLAG_FORCE_NOT_FULLSCREEN);\n" +
    "        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {\n" +
    "            getWindow().setDecorFitsSystemWindows(false);\n" +
    "            WindowInsetsController controller = getWindow().getInsetsController();\n" +
    "            if (controller != null) {\n" +
    "                controller.show(WindowInsets.Type.statusBars());\n" +
    "                int lightMask = WindowInsetsController.APPEARANCE_LIGHT_STATUS_BARS;\n" +
    "                controller.setSystemBarsAppearance(" + (minimalLightStatusBarIcons ? "true" : "false") + " ? lightMask : 0, lightMask);\n" +
    "            }\n" +
    "        } else {\n" +
    "            int visibility = View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN | View.SYSTEM_UI_FLAG_LAYOUT_STABLE;\n" +
    "            if (" + (minimalLightStatusBarIcons ? "true" : "false") + " && Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {\n" +
    "                visibility |= View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR;\n" +
    "            }\n" +
    "            getWindow().getDecorView().setSystemUiVisibility(visibility);\n" +
    "        }\n" +
    "        syncConvertApkStatusBarOverlay(statusBarColor);\n" +
    "    }\n\n" +
    "    private void syncConvertApkStatusBarOverlay(int statusBarColor) {\n" +
    "        ViewGroup contentRoot = findViewById(android.R.id.content);\n" +
    "        if (contentRoot == null) {\n" +
    "            return;\n" +
    "        }\n" +
    "        int topInset = readConvertApkStatusBarHeightPx();\n" +
    "        android.webkit.WebView convertApkWebView = getBridge() != null ? getBridge().getWebView() : null;\n" +
    "        if (convertApkWebView != null) {\n" +
    "            convertApkWebView.setClipToPadding(true);\n" +
    "            convertApkWebView.setPadding(convertApkWebView.getPaddingLeft(), topInset, convertApkWebView.getPaddingRight(), convertApkWebView.getPaddingBottom());\n" +
    "            convertApkWebView.post(() -> convertApkWebView.evaluateJavascript(\n" +
    "                \"(function(){var t=\" + topInset + \";var root=document.documentElement;\" +\n" +
    "                \"if(root){root.style.setProperty('--convertapk-safe-top', t+'px');}\" +\n" +
    "                \"if(document.body){document.body.style.setProperty('--convertapk-safe-top', t+'px');}\" +\n" +
    "                \"})();\",\n" +
    "                null\n" +
    "            ));\n" +
    "        }\n" +
    "        String tag = \"convertapk-status-bar-overlay\";\n" +
    "        View overlay = contentRoot.findViewWithTag(tag);\n" +
    "        if (overlay == null) {\n" +
    "            overlay = new View(this);\n" +
    "            overlay.setTag(tag);\n" +
    "            FrameLayout.LayoutParams params = new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, topInset);\n" +
    "            params.gravity = Gravity.TOP;\n" +
    "            contentRoot.addView(overlay, params);\n" +
    "        }\n" +
    "        overlay.setBackgroundColor(statusBarColor);\n" +
    "        ViewGroup.LayoutParams params = overlay.getLayoutParams();\n" +
    "        if (params != null && params.height != topInset) {\n" +
    "            params.height = topInset;\n" +
    "            overlay.setLayoutParams(params);\n" +
    "        }\n" +
    "        overlay.bringToFront();\n" +
    "    }\n\n" +
    "    private int readConvertApkStatusBarHeightPx() {\n" +
    "        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R && getWindow().getDecorView().getRootWindowInsets() != null) {\n" +
    "            int insetTop = getWindow().getDecorView().getRootWindowInsets().getInsets(WindowInsets.Type.statusBars()).top;\n" +
    "            if (insetTop > 0) return insetTop;\n" +
    "        }\n" +
    "        int resId = getResources().getIdentifier(\"status_bar_height\", \"dimen\", \"android\");\n" +
    "        if (resId > 0) return getResources().getDimensionPixelSize(resId);\n" +
    "        return (int) (24 * getResources().getDisplayMetrics().density);\n" +
    "    }\n\n" +
    "    private int resolveConvertApkStatusBarColor(String raw) {\n" +
    "        String value = raw == null ? \"\" : raw.trim();\n" +
    "        if (\"transparent\".equalsIgnoreCase(value) || \"@android:color/transparent\".equalsIgnoreCase(value)) {\n" +
    "            return Color.TRANSPARENT;\n" +
    "        }\n" +
    "        try {\n" +
    "            return Color.parseColor(value);\n" +
    "        } catch (Exception ignored) {\n" +
    "            return Color.WHITE;\n" +
    "        }\n" +
    "    }\n" +
    "    // ConvertAPK：状态栏颜色结束（极简）\n";
  const normalized = insertAfterMainActivityClassOpen(updated, "", false);
  updated = normalized;
  const classClose = updated.lastIndexOf("}");
  if (classClose !== -1) {
    updated = updated.slice(0, classClose) + "\n" + methodBlock + "\n" + updated.slice(classClose);
  }
  return updated;
}

if (skipMainActivityInjection) {
  if (originalText.includes("ConvertAPK:")) {
    const javaPackageLine = packageLine.endsWith(";") ? packageLine : `${packageLine};`;
    text = isKotlin
      ? `${packageLine}\n\nimport com.getcapacitor.BridgeActivity\n\nclass MainActivity : BridgeActivity()\n`
      : `${javaPackageLine}\n\nimport com.getcapacitor.BridgeActivity;\n\npublic class MainActivity extends BridgeActivity {}\n`;
    console.log("[MainActivity] detected ConvertAPK markers; reset to minimal BridgeActivity");
  } else {
    text = originalText;
  }
  const enableMinimalBridgeTweaks = taskMode === "convert";
  const beforeMinimalStatusSync = text;
  text = syncMinimalStatusBarHidden(text, isKotlin, enableMinimalBridgeTweaks && statusBarHidden);
  if (beforeMinimalStatusSync !== text) {
    console.log(`[MainActivity] ${(enableMinimalBridgeTweaks && statusBarHidden) ? "enabled" : "disabled"} minimal status-bar-hidden`);
  }
  const beforeMinimalStatusColorSync = text;
  text = syncMinimalStatusBarColor(text, isKotlin, enableMinimalBridgeTweaks && !statusBarHidden);
  if (beforeMinimalStatusColorSync !== text) {
    console.log(`[MainActivity] ${(enableMinimalBridgeTweaks && !statusBarHidden) ? "enabled" : "disabled"} minimal status-bar-color`);
  }
  const beforeMinimalSync = text;
  text = syncMinimalDoubleClickExit(text, isKotlin, enableMinimalBridgeTweaks && doubleClickExit);
  if (beforeMinimalSync !== text) {
    console.log(`[MainActivity] ${(enableMinimalBridgeTweaks && doubleClickExit) ? "enabled" : "disabled"} minimal double-click-exit`);
  }
  const minimalDownloadMode = String(process.env.DOWNLOAD_MODE || "").trim().toLowerCase() === "silent" ? "silent" : "picker";
  const enableMinimalDownloadListener = enableMinimalBridgeTweaks;
  const beforeMinimalDownloadSync = text;
  text = syncMinimalDownloadListener(text, isKotlin, enableMinimalDownloadListener, minimalDownloadMode);
  if (beforeMinimalDownloadSync !== text) {
    console.log(`[MainActivity] ${enableMinimalDownloadListener ? "enabled" : "disabled"} minimal download-listener`);
  }
}

const beforeDisablePinchZoomSync = text;
text = syncDisablePinchZoom(text, isKotlin, taskMode === "convert");
if (beforeDisablePinchZoomSync !== text) {
  console.log(`[MainActivity] ${(taskMode === "convert") ? "enabled" : "disabled"} disable-pinch-zoom`);
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
    if (taskMode === "convert" && statusBarHidden) {
      const fullscreenLaunchThemeRef = "@style/ConvertApk.FullscreenLaunch";
      if (/\bandroid:theme=/.test(updated)) {
        updated = updated.replace(
          /\bandroid:theme="[^"]*"/,
          `android:theme="${fullscreenLaunchThemeRef}"`
        );
      } else {
        updated = updated.replace(/\s*\/?>$/, (end) => {
          const suffix = end.includes("/>") ? " />" : ">";
          return ` android:theme="${fullscreenLaunchThemeRef}"${suffix}`;
        });
      }
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

const convertApkFullscreenThemesFile = path.join(
  androidDir,
  "app",
  "src",
  "main",
  "res",
  "values",
  "convertapk_statusbar_themes.xml"
);
if (taskMode === "convert" && statusBarHidden) {
  const fullscreenThemesXml = `<?xml version="1.0" encoding="utf-8"?>
<resources>
    <style name="ConvertApk.FullscreenBase" parent="@style/Theme.AppCompat.DayNight.NoActionBar">
        <item name="android:windowFullscreen">true</item>
        <item name="android:windowTranslucentStatus">false</item>
        <item name="android:statusBarColor">@android:color/transparent</item>
        <item name="android:windowLightStatusBar">false</item>
        <item name="android:windowLayoutInDisplayCutoutMode">shortEdges</item>
    </style>
    <style name="ConvertApk.FullscreenLaunch" parent="@style/Theme.SplashScreen">
        <item name="android:windowFullscreen">true</item>
        <item name="android:windowTranslucentStatus">false</item>
        <item name="android:statusBarColor">@android:color/transparent</item>
        <item name="android:windowLightStatusBar">false</item>
        <item name="android:windowLayoutInDisplayCutoutMode">shortEdges</item>
        <item name="postSplashScreenTheme">@style/ConvertApk.FullscreenBase</item>
    </style>
</resources>
`;
  fs.mkdirSync(path.dirname(convertApkFullscreenThemesFile), { recursive: true });
  writeText(convertApkFullscreenThemesFile, fullscreenThemesXml);
}

// Status bar configuration (styles.xml/themes.xml)
// - STATUS_BAR_HIDDEN=true  -> fullscreen
// - STATUS_BAR_COLOR=transparent|#RRGGBB|#AARRGGBB
// - STATUS_BAR_STYLE=dark|light (dark = dark icons for light background)
const styleFileSet = new Set();

function collectStyleFilesFromResDir(resDirPath) {
  if (!fs.existsSync(resDirPath)) return;
  const entries = fs.readdirSync(resDirPath, { withFileTypes: true });
  for (const entry of entries) {
    if (!entry.isDirectory()) continue;
    if (!entry.name.startsWith("values")) continue;
    for (const name of ["styles.xml", "themes.xml"]) {
      const candidate = path.join(resDirPath, entry.name, name);
      if (fs.existsSync(candidate)) {
        styleFileSet.add(candidate);
      }
    }
  }
}

const moduleRoots = new Set();
moduleRoots.add(androidDir);
if (fs.existsSync(androidDir)) {
  const entries = fs.readdirSync(androidDir, { withFileTypes: true });
  for (const entry of entries) {
    if (!entry.isDirectory()) continue;
    if (entry.name.startsWith(".")) continue;
    moduleRoots.add(path.join(androidDir, entry.name));
  }
}

const settingsCandidates = [
  path.join(androidDir, "settings.gradle"),
  path.join(androidDir, "settings.gradle.kts"),
  path.join(androidDir, "capacitor.settings.gradle"),
  path.join(androidDir, "capacitor.settings.gradle.kts"),
];
for (const settingsFile of settingsCandidates) {
  if (!fs.existsSync(settingsFile)) continue;
  const settingsDir = path.dirname(settingsFile);
  const settingsText = readText(settingsFile);
  const projectDirRegex = /(?:new\s+File|file|File)\(\s*["']([^"']+)["']\s*\)/g;
  let match;
  while ((match = projectDirRegex.exec(settingsText)) !== null) {
    const relPath = String(match[1] || "").trim();
    if (!relPath) continue;
    const absolutePath = path.resolve(settingsDir, relPath);
    if (fs.existsSync(absolutePath)) {
      moduleRoots.add(absolutePath);
    }
  }
}

const capacitorAndroidModuleDir = path.join(
  projectRoot,
  "node_modules",
  "@capacitor",
  "android",
  "capacitor"
);
if (fs.existsSync(capacitorAndroidModuleDir)) {
  moduleRoots.add(capacitorAndroidModuleDir);
}

const capacitorPackagesRoot = path.join(projectRoot, "node_modules", "@capacitor");
if (fs.existsSync(capacitorPackagesRoot)) {
  const packages = fs.readdirSync(capacitorPackagesRoot, { withFileTypes: true });
  for (const pkg of packages) {
    if (!pkg.isDirectory()) continue;
    const pkgDir = path.join(capacitorPackagesRoot, pkg.name);
    const candidateDirs = [
      pkgDir,
      path.join(pkgDir, "android"),
      path.join(pkgDir, "capacitor"),
      path.join(pkgDir, "android", "capacitor"),
    ];
    for (const candidateDir of candidateDirs) {
      if (fs.existsSync(candidateDir)) {
        moduleRoots.add(candidateDir);
      }
    }
  }
}

for (const moduleRoot of moduleRoots) {
  const moduleResDir = path.join(moduleRoot, "src", "main", "res");
  collectStyleFilesFromResDir(moduleResDir);
}

const styleFiles = Array.from(styleFileSet);

const hidden = String(process.env.STATUS_BAR_HIDDEN || "")
  .trim()
  .toLowerCase() === "true";
const style = String(process.env.STATUS_BAR_STYLE || "light").trim().toLowerCase(); // dark | light
let colorRaw = String(process.env.STATUS_BAR_COLOR || "white").trim();
if (!colorRaw) colorRaw = "white";
if (
  taskMode === "convert" &&
  !hidden &&
  ["transparent", "@android:color/transparent"].includes(colorRaw.toLowerCase())
) {
  colorRaw = "#FFFFFF";
}
const colorLower = colorRaw.toLowerCase();
const statusBarColor =
  colorLower === "transparent" || colorLower === "@android:color/transparent"
    ? "@android:color/transparent"
    : colorLower === "white"
      ? "#FFFFFF"
      : colorRaw;
const lightStatusBar = style === "dark"; // windowLightStatusBar=true => dark icons
const styleNames = [
  "AppTheme",
  "AppTheme.NoActionBar",
  "AppTheme.NoActionBarLaunch",
  "Theme.App",
  "Theme.App.NoActionBar"
];
if (taskMode === "convert" && hidden) {
  styleNames.push("ConvertApk.FullscreenBase");
  styleNames.push("ConvertApk.FullscreenLaunch");
}
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
  if (!fs.existsSync(filePath)) return { changed: false, matchedStyles: new Set() };
  let stext = readText(filePath);
  const original = stext;
  const matchedStyles = new Set();

  function patchStyleBlock(styleName, items) {
    const re = new RegExp(
      `(<style\\\\b[^>]*\\\\bname="${escapeRegExp(styleName)}"[^>]*>)([\\\\s\\\\S]*?)(</style>)`
    );
    const match = stext.match(re);
    if (!match) return false;
    matchedStyles.add(styleName);
    let inner = match[2] || "";
    inner = inner.replace(/\s*<item\s+name="android:windowFullscreen">[\s\S]*?<\/item>\s*/g, "\n");
    inner = inner.replace(/\s*<item\s+name="android:windowTranslucentStatus">[\s\S]*?<\/item>\s*/g, "\n");
    inner = inner.replace(/\s*<item\s+name="android:statusBarColor">[\s\S]*?<\/item>\s*/g, "\n");
    inner = inner.replace(/\s*<item\s+name="android:windowLightStatusBar">[\s\S]*?<\/item>\s*/g, "\n");
    inner = inner.replace(/\s*<item\s+name="android:windowLayoutInDisplayCutoutMode">[\s\S]*?<\/item>\s*/g, "\n");
    const insert = items.length ? "\n        " + items.join("\n        ") + "\n" : "\n";
    const updated = match[1] + insert + inner.replace(/^\n+/, "\n") + match[3];
    stext = stext.replace(match[0], updated);
    return true;
  }

  const items = [];
  if (hidden) {
    items.push('<item name="android:windowFullscreen">true</item>');
    items.push('<item name="android:windowTranslucentStatus">false</item>');
    items.push('<item name="android:statusBarColor">@android:color/transparent</item>');
    items.push('<item name="android:windowLightStatusBar">false</item>');
    items.push('<item name="android:windowLayoutInDisplayCutoutMode">shortEdges</item>');
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
    return { changed: true, matchedStyles };
  }
  return { changed: false, matchedStyles };
}

const patchedStyleNames = new Set();
let patchedFileCount = 0;
for (const filePath of styleFiles) {
  const result = patchStylesFile(filePath);
  if (result.changed) {
    patchedFileCount += 1;
    console.log(`[StylesPatch] patched: ${filePath}`);
  }
  for (const styleName of result.matchedStyles) {
    patchedStyleNames.add(styleName);
  }
}
console.log(`[StylesPatch] scanned ${styleFiles.length} style files in android modules`);
const missingStyleNames = styleNames.filter((name) => !patchedStyleNames.has(name));
if (missingStyleNames.length) {
  console.log(`[StylesPatch] styles not found: ${missingStyleNames.join(", ")}`);
}

// Layout patch removed: rely on theme + window flags to avoid status bar overlap.
NODE

# ============================================
# 步骤 6: 配置 Android 项目
# ============================================
fi

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
        sed -i -E "s/applicationId[[:space:]]*=[[:space:]]*\"[^\"]*\"/applicationId = \"$PACKAGE_NAME\"/" "$GRADLE_FILE"
        sed -i "s/versionName[[:space:]]*=[[:space:]]*\".*\"/versionName = \"$VERSION_NAME\"/" "$GRADLE_FILE"
        sed -i "s/versionCode[[:space:]]*=[[:space:]]*[0-9]\+/versionCode = $VERSION_CODE/" "$GRADLE_FILE"
    else
        sed -i -E "s/applicationId[[:space:]]*=[[:space:]]*\"[^\"]*\"/applicationId = \"$PACKAGE_NAME\"/" "$GRADLE_FILE"
        sed -i -E "s/applicationId[[:space:]]+\"[^\"]*\"/applicationId = \"$PACKAGE_NAME\"/" "$GRADLE_FILE"
        sed -i -E "s/versionName[[:space:]]*=[[:space:]]*\".*\"/versionName = \"$VERSION_NAME\"/" "$GRADLE_FILE"
        sed -i -E "s/versionName[[:space:]]+\".*\"/versionName = \"$VERSION_NAME\"/" "$GRADLE_FILE"
        sed -i -E "s/versionCode[[:space:]]*=[[:space:]]*.*/versionCode = $VERSION_CODE/" "$GRADLE_FILE"
        sed -i -E "s/versionCode[[:space:]]+.*/versionCode = $VERSION_CODE/" "$GRADLE_FILE"
    fi
    log_info "已更新版本号信息"
fi

if [ "$TASK_MODE" = "native" ] && [ -f "$GRADLE_FILE" ]; then
    GRADLE_FILE_FOR_IDENTITY="$GRADLE_FILE" \
    APP_DIR_FOR_IDENTITY="$ANDROID_DIR/app" \
    APP_NAME_FOR_IDENTITY="$APP_NAME" \
    PACKAGE_NAME_FOR_IDENTITY="$PACKAGE_NAME" \
    VERSION_NAME_FOR_IDENTITY="$VERSION_NAME" \
    VERSION_CODE_FOR_IDENTITY="$VERSION_CODE" \
    node <<'NODE'
const fs = require('fs');
const path = require('path');

const gradleFile = process.env.GRADLE_FILE_FOR_IDENTITY;
const appDir = process.env.APP_DIR_FOR_IDENTITY;
const appName = String(process.env.APP_NAME_FOR_IDENTITY || '').trim();
const packageName = String(process.env.PACKAGE_NAME_FOR_IDENTITY || '').trim();
const versionName = String(process.env.VERSION_NAME_FOR_IDENTITY || '1.0.0').trim() || '1.0.0';
const versionCodeRaw = String(process.env.VERSION_CODE_FOR_IDENTITY || '1').trim();
const versionCode = /^\d+$/.test(versionCodeRaw) ? versionCodeRaw : '1';

function escapeRegex(value) {
  return String(value).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function escapeXml(value) {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function escapeXmlAttr(value) {
  return escapeXml(value).replace(/"/g, '&quot;');
}

function patchOrInsert(source, patterns, replacement) {
  for (const pattern of patterns) {
    if (pattern.test(source)) {
      return source.replace(pattern, replacement);
    }
  }
  if (/defaultConfig\s*\{/.test(source)) {
    return source.replace(/defaultConfig\s*\{/, (match) => `${match}\n        ${replacement}`);
  }
  return source;
}

function ensureStringValue(stringsFile, key, value) {
  fs.mkdirSync(path.dirname(stringsFile), { recursive: true });
  const escapedValue = escapeXml(value);
  if (!fs.existsSync(stringsFile)) {
    fs.writeFileSync(
      stringsFile,
      `<?xml version="1.0" encoding="utf-8"?>\n<resources>\n    <string name="${key}">${escapedValue}</string>\n</resources>\n`,
      'utf8'
    );
    return true;
  }
  let text = fs.readFileSync(stringsFile, 'utf8');
  const original = text;
  const pattern = new RegExp(`(<string\\s+name="${escapeRegex(key)}"[^>]*>)([\\s\\S]*?)(<\\/string>)`);
  if (pattern.test(text)) {
    text = text.replace(pattern, (match, openTag, oldValue, closeTag) => `${openTag}${escapedValue}${closeTag}`);
  } else if (/<\/resources>/.test(text)) {
    text = text.replace(/<\/resources>/, `    <string name="${key}">${escapedValue}</string>\n</resources>`);
  } else {
    text += `\n<string name="${key}">${escapedValue}</string>\n`;
  }
  if (text !== original) {
    fs.writeFileSync(stringsFile, text, 'utf8');
    return true;
  }
  return false;
}

if (gradleFile && fs.existsSync(gradleFile)) {
  const isKts = gradleFile.endsWith('.kts');
  let source = fs.readFileSync(gradleFile, 'utf8');
  const original = source;
  if (packageName) {
    source = patchOrInsert(
      source,
      isKts
        ? [/applicationId\s*=\s*"[^"]*"/, /applicationId\s*\(\s*"[^"]*"\s*\)/]
        : [/applicationId\s*=\s*"[^"]*"/, /applicationId\s+"[^"]*"/],
      `applicationId = "${packageName}"`
    );
  }
  source = patchOrInsert(
    source,
    isKts
      ? [/versionName\s*=\s*"[^"]*"/, /versionName\s*\(\s*"[^"]*"\s*\)/]
      : [/versionName\s*=\s*"[^"]*"/, /versionName\s+"[^"]*"/],
    `versionName = "${versionName}"`
  );
  source = patchOrInsert(
    source,
    isKts
      ? [/versionCode\s*=\s*\d+/, /versionCode\s*\(\s*\d+\s*\)/]
      : [/versionCode\s*=\s*\d+/, /versionCode\s+\d+/],
    `versionCode = ${versionCode}`
  );
  if (source !== original) {
    fs.writeFileSync(gradleFile, source, 'utf8');
    console.log('[NativeIdentityPatch] Gradle identity updated');
  }
}

if (appName && appDir) {
  const stringsFile = path.join(appDir, 'src', 'main', 'res', 'values', 'strings.xml');
  const manifestFile = path.join(appDir, 'src', 'main', 'AndroidManifest.xml');
  if (fs.existsSync(manifestFile)) {
    let manifest = fs.readFileSync(manifestFile, 'utf8');
    const originalManifest = manifest;
    const appTagMatch = manifest.match(/<application\b[^>]*>/);
    if (appTagMatch) {
      const appTag = appTagMatch[0];
      const labelMatch = appTag.match(/android:label\s*=\s*"([^"]*)"/);
      if (labelMatch && labelMatch[1].startsWith('@string/')) {
        ensureStringValue(stringsFile, labelMatch[1].slice('@string/'.length), appName);
      } else if (labelMatch) {
        manifest = manifest.replace(
          /(<application\b[^>]*android:label\s*=\s*")[^"]*(")/,
          (match, openTag, closeQuote) => `${openTag}${escapeXmlAttr(appName)}${closeQuote}`
        );
      } else {
        ensureStringValue(stringsFile, 'app_name', appName);
        manifest = manifest.replace(/<application\b/, '<application android:label="@string/app_name"');
      }
    } else {
      ensureStringValue(stringsFile, 'app_name', appName);
    }
    if (manifest !== originalManifest) {
      fs.writeFileSync(manifestFile, manifest, 'utf8');
    }
    console.log('[NativeIdentityPatch] app label updated');
  } else {
    ensureStringValue(stringsFile, 'app_name', appName);
    console.log('[NativeIdentityPatch] app label updated');
  }
}
NODE
fi

if [ "$TASK_MODE" = "native" ] && [ -f "$INPUT_DIR/logo.png" ]; then
    drawable_dir="$ANDROID_DIR/app/src/main/res/drawable"
    if [ -d "$drawable_dir" ]; then
        rm -f "$drawable_dir/ic_launcher_foreground.xml"
        prepareLauncherForegroundIcon "$INPUT_DIR/logo.png" "$drawable_dir/ic_launcher_foreground.png"
        log_info "Native launcher icon updated with adaptive safe padding"
    fi
fi

if [ "$TASK_MODE" = "native" ] && [ -f "$GRADLE_FILE" ]; then
    GRADLE_FILE_FOR_PATCH="$GRADLE_FILE" KEY_ALIAS_FOR_PATCH="$KEY_ALIAS" node <<'NODE'
const fs = require('fs');

const filePath = process.env.GRADLE_FILE_FOR_PATCH;
const keyAlias = process.env.KEY_ALIAS_FOR_PATCH || 'key0';
if (filePath && fs.existsSync(filePath)) {
  const quote = (value) => String(value).replace(/\\/g, '\\\\').replace(/"/g, '\\"');
  let source = fs.readFileSync(filePath, 'utf8');
  const original = source;

  if (filePath.endsWith('.kts')) {
    source = source.replace(/storeFile\s*=\s*file\([^\n]*\)/g, 'storeFile = file(System.getenv("KEYSTORE_PATH") ?: "${rootDir}/my-upload-key.jks")');
    source = source.replace(/storePassword\s*=\s*("[^"]*"|System\.getenv\("[^"]+"\))/g, 'storePassword = System.getenv("STORE_PASSWORD")');
    source = source.replace(/keyAlias\s*=\s*"[^"]*"/g, `keyAlias = System.getenv("KEY_ALIAS") ?: "${quote(keyAlias)}"`);
    source = source.replace(/keyPassword\s*=\s*("[^"]*"|System\.getenv\("[^"]+"\))/g, 'keyPassword = System.getenv("KEY_PASSWORD")');
  } else {
    source = source.replace(/storeFile\s+(file\([^\n]*\))/g, 'storeFile = file(System.getenv("KEYSTORE_PATH") ?: "${rootDir}/my-upload-key.jks")');
    source = source.replace(/storeFile\s*=\s*(file\([^\n]*\))/g, 'storeFile = file(System.getenv("KEYSTORE_PATH") ?: "${rootDir}/my-upload-key.jks")');
    source = source.replace(/storePassword\s+("[^"]*"|System\.getenv\("[^"]+"\))/g, 'storePassword = System.getenv("STORE_PASSWORD")');
    source = source.replace(/storePassword\s*=\s*("[^"]*"|System\.getenv\("[^"]+"\))/g, 'storePassword = System.getenv("STORE_PASSWORD")');
    source = source.replace(/keyAlias\s+"[^"]*"/g, `keyAlias = System.getenv("KEY_ALIAS") ?: "${quote(keyAlias)}"`);
    source = source.replace(/keyAlias\s*=\s*"[^"]*"/g, `keyAlias = System.getenv("KEY_ALIAS") ?: "${quote(keyAlias)}"`);
    source = source.replace(/keyPassword\s+("[^"]*"|System\.getenv\("[^"]+"\))/g, 'keyPassword = System.getenv("KEY_PASSWORD")');
    source = source.replace(/keyPassword\s*=\s*("[^"]*"|System\.getenv\("[^"]+"\))/g, 'keyPassword = System.getenv("KEY_PASSWORD")');
  }

  if (source !== original) {
    fs.writeFileSync(filePath, source);
    console.log(`[NativeSigningPatch] patched: ${filePath}`);
  }
}
NODE
fi

applyNativeGradleCompatibilityFallbacks() {
    if [ "$TASK_MODE" != "native" ]; then
        return 0
    fi
    if ! command -v node >/dev/null 2>&1; then
        return 0
    fi

    NATIVE_ANDROID_DIR="$ANDROID_DIR" node <<'NODE'
const fs = require('fs');
const path = require('path');

const rootDir = path.resolve(process.cwd(), process.env.NATIVE_ANDROID_DIR || '.');
const ignoredDirs = new Set(['.git', '.gradle', 'build', 'node_modules']);

function walk(dir, result) {
  let entries = [];
  try {
    entries = fs.readdirSync(dir, { withFileTypes: true });
  } catch {
    return;
  }
  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      if (!ignoredDirs.has(entry.name)) walk(fullPath, result);
      continue;
    }
    if (entry.isFile()) result.push(fullPath);
  }
}

function readText(filePath) {
  try {
    return fs.readFileSync(filePath, 'utf8');
  } catch {
    return '';
  }
}

function writeText(filePath, text) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, text, 'utf8');
}

function patchGroovySpaceAssignments(source) {
  const propertyNames = [
    'compileSdk',
    'compileSdkVersion',
    'namespace',
    'applicationId',
    'minSdk',
    'minSdkVersion',
    'targetSdk',
    'targetSdkVersion',
    'versionCode',
    'versionName',
    'testInstrumentationRunner',
    'abortOnError',
    'useLegacyPackaging',
    'minifyEnabled',
    'shrinkResources',
    'zipAlignEnabled',
    'debuggable',
    'jniDebuggable',
    'renderscriptTargetApi',
    'renderscriptSupportModeEnabled',
    'multiDexEnabled',
    'dimension',
    'applicationIdSuffix',
    'versionNameSuffix',
    'signingConfig',
    'storeFile',
    'storePassword',
    'keyAlias',
    'keyPassword',
    'v1SigningEnabled',
    'v2SigningEnabled',
    'v3SigningEnabled',
    'v4SigningEnabled',
  ];
  const propertyPattern = propertyNames.map((name) => name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|');
  const linePattern = new RegExp(`^([ \\t]*)(${propertyPattern})([ \\t]+)(?![=({])([^\\r\\n]+)$`, 'gm');
  return source.replace(linePattern, (match, indent, propertyName, spacing, value) => {
    const trimmedValue = value.trim();
    if (!trimmedValue || trimmedValue.startsWith('//') || trimmedValue.startsWith('{')) {
      return match;
    }
    return `${indent}${propertyName} = ${trimmedValue}`;
  });
}

function collectIncludedModules() {
  const modules = new Set();
  for (const settingsName of ['settings.gradle', 'settings.gradle.kts']) {
    const settingsPath = path.join(rootDir, settingsName);
    const source = readText(settingsPath);
    if (!source) continue;
    const includePattern = /include\s*(?:\(?\s*)?([^\r\n)]*)/g;
    let match;
    while ((match = includePattern.exec(source)) !== null) {
      const body = match[1] || '';
      for (const moduleMatch of body.matchAll(/['"](:[^'"]+)['"]/g)) {
        modules.add(moduleMatch[1]);
      }
    }
  }
  return Array.from(modules);
}

function warnMissingIncludedModules() {
  for (const moduleName of collectIncludedModules()) {
    if (moduleName === ':app') continue;
    const modulePath = path.join(rootDir, ...moduleName.replace(/^:/, '').split(':'));
    if (!fs.existsSync(modulePath)) {
      console.log(`[NativeCompatPatch] 警告：settings.gradle 引用了 ${moduleName}，但源码包中缺少目录 ${path.relative(rootDir, modulePath)}`);
      continue;
    }
    const hasBuildFile = fs.existsSync(path.join(modulePath, 'build.gradle')) || fs.existsSync(path.join(modulePath, 'build.gradle.kts'));
    if (!hasBuildFile) {
      console.log(`[NativeCompatPatch] 警告：settings.gradle 引用了 ${moduleName}，但该模块缺少 build.gradle/build.gradle.kts；如果这是 Git submodule，请重新打包含子模块的完整源码`);
    }
  }
}

const files = [];
walk(rootDir, files);
const textFiles = files.filter((filePath) => /\.(gradle|gradle\.kts|kt|java|xml|toml|properties)$/i.test(filePath));
const hasAndroidX = textFiles.some((filePath) => /\bandroidx[.:]/.test(readText(filePath)));

warnMissingIncludedModules();

let patchedGroovyDsl = 0;
for (const filePath of files.filter((item) => /\.gradle$/i.test(item))) {
  let source = readText(filePath);
  const original = source;
  source = patchGroovySpaceAssignments(source);
  if (source !== original) {
    writeText(filePath, source);
    patchedGroovyDsl += 1;
    console.log(`[NativeCompatPatch] 已迁移 Gradle Groovy 属性赋值语法: ${path.relative(rootDir, filePath)}`);
  }
}

if (patchedGroovyDsl > 0) {
  console.log('[NativeCompatPatch] 已将低风险旧 DSL 写法迁移为 propName = value，避免新 Gradle 版本拦截');
}

if (hasAndroidX) {
  const propsPath = path.join(rootDir, 'gradle.properties');
  let props = readText(propsPath);
  const original = props;
  if (/^android\.useAndroidX\s*=/m.test(props)) {
    props = props.replace(/^android\.useAndroidX\s*=.*$/m, 'android.useAndroidX=true');
  } else {
    const prefix = props.trim() ? `${props.replace(/\s*$/, '')}\n` : '';
    props = `${prefix}android.useAndroidX=true\n`;
  }
  if (props !== original) {
    writeText(propsPath, props);
    console.log('[NativeCompatPatch] 已启用 AndroidX: gradle.properties -> android.useAndroidX=true');
  }
}

let patchedJvmTarget = 0;
for (const filePath of files.filter((item) => /\.(gradle|gradle\.kts)$/i.test(item))) {
  let source = readText(filePath);
  const original = source;
  source = source.replace(/(jvmTarget\s*=\s*["'])21(["'])/g, (match, prefix, suffix) => `${prefix}17${suffix}`);
  source = source.replace(/(jvmTarget\s+["'])21(["'])/g, (match, prefix, suffix) => `${prefix}17${suffix}`);
  source = source.replace(/(jvmTarget\s*=\s*)JavaVersion\.VERSION_21(?:\.toString\(\))?/g, '$1"17"');
  if (source !== original) {
    writeText(filePath, source);
    patchedJvmTarget += 1;
    console.log(`[NativeCompatPatch] 已将 Kotlin jvmTarget 21 降级为 17: ${path.relative(rootDir, filePath)}`);
  }
}

if (patchedJvmTarget > 0) {
  console.log('[NativeCompatPatch] 当前构建器优先使用 JVM 17 兼容 Android/Kotlin 构建链');
}
NODE
}

applyNativeGradleCompatibilityFallbacks

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

KEYSTORE_FILE="$KEYSTORE_DIR/release.keystore"

ensure_native_gradle_signing_keystore() {
    if [ "$KEYSTORE_REUSED" = "true" ]; then
        if [ ! -f "$KEYSTORE_FILE" ]; then
            log_error "复用签名模式下密钥库文件不存在，无法执行原生 Gradle 签名"
            exit 1
        fi
        return 0
    fi

    if [ -f "$KEYSTORE_FILE" ]; then
        return 0
    fi

    log_info "为原生 Gradle 构建预生成签名密钥..."
    keytool -genkeypair -v \
        -keystore "$KEYSTORE_FILE" \
        -alias "$KEY_ALIAS" \
        -keyalg RSA \
        -keysize 2048 \
        -validity 10000 \
        -storepass "$KEYSTORE_PASSWORD" \
        -keypass "$KEY_PASSWORD" \
        -dname "CN=APK Builder, OU=Dev, O=Company, L=City, ST=State, C=CN"
    check_error "原生 Gradle 签名密钥生成失败"
}

if [ "$TASK_MODE" = "native" ]; then
    ensure_native_gradle_signing_keystore
    export KEYSTORE_PATH="$KEYSTORE_FILE"
    export STORE_PASSWORD="$KEYSTORE_PASSWORD"
    export KEY_PASSWORD="$KEY_PASSWORD"
    export KEY_ALIAS="$KEY_ALIAS"
    export RELEASE_STORE_FILE="$KEYSTORE_FILE"
    export RELEASE_STORE_PASSWORD="$KEYSTORE_PASSWORD"
    export RELEASE_KEY_ALIAS="$KEY_ALIAS"
    export RELEASE_KEY_PASSWORD="$KEY_PASSWORD"
fi

ANDROID_BUILD_DIR="$PROJECT_ROOT/$ANDROID_DIR"
cd "$ANDROID_BUILD_DIR"

# Ensure gradlew exists (web mode may miss wrapper if template copy failed)
if [ ! -f "gradlew" ]; then
    TEMPLATE_DIR="$TEMPLATE_ROOT/Tubbim"
    if [ -f "$TEMPLATE_DIR/gradlew" ]; then
        log_warning "gradlew missing; restoring from template"
        cp "$TEMPLATE_DIR/gradlew" .
        if [ -d "$TEMPLATE_DIR/gradle/wrapper" ] && [ ! -d "gradle/wrapper" ]; then
            mkdir -p "gradle"
            cp -R "$TEMPLATE_DIR/gradle/wrapper" "gradle/wrapper"
        elif [ -d "$TEMPLATE_DIR/gradle" ] && [ ! -d "gradle" ]; then
            cp -R "$TEMPLATE_DIR/gradle" .
        fi
    fi
fi
if [ ! -f "gradlew" ]; then
    log_error "gradlew not found in $ANDROID_BUILD_DIR"
    exit 1
fi



# 给 gradlew 执行权限
chmod +x gradlew

# 如果已缓存 Gradle wrapper 分发包就复用，否则尝试从镜像预取
patch_gradle_wrapper_version
ensure_gradle_wrapper_jar
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
        maven { url = uri('https://jitpack.io') }
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

printGradleFailureHelp() {
    local gradleLogFile="$1"
    if [ ! -f "$gradleLogFile" ]; then
        return 0
    fi

    if grep -qi "Unknown Kotlin JVM target: 21" "$gradleLogFile"; then
        log_warning "修复建议：项目 Kotlin jvmTarget=21，但当前 Kotlin Gradle 插件不支持。请把 build.gradle/build.gradle.kts 中的 jvmTarget 改为 17，或升级 Kotlin Gradle Plugin。"
    fi

    if grep -qi "Illegal escape" "$gradleLogFile"; then
        local illegalEscapeLine
        illegalEscapeLine="$(grep -i -m 1 "Illegal escape" "$gradleLogFile" || true)"
        if [ -n "$illegalEscapeLine" ]; then
            log_warning "源码定位：$illegalEscapeLine"
        fi
        log_warning "修复建议：Kotlin 正则里的反斜杠需要转义；例如空白分割请写成 Regex(\"\\\\s+\")，或使用原始字符串 Regex(\"\"\"\\s+\"\"\")。"
    fi

    if grep -Eqi "contains AndroidX dependencies|AndroidX dependencies|android\.useAndroidX" "$gradleLogFile"; then
        log_warning "修复建议：项目使用 AndroidX 依赖时，根目录 gradle.properties 需要包含 android.useAndroidX=true；如混用旧 support 包，可同时添加 android.enableJetifier=true。"
    fi

    if grep -Eqi "AndroidManifest\.xml.*doesn.?t exist|Source file .*AndroidManifest\.xml.*does not exist|main manifest.*doesn.?t exist" "$gradleLogFile"; then
        log_warning "修复建议：Gradle 找不到 app/src/main/AndroidManifest.xml。请确认源码 ZIP 包含完整 app 模块；如果任务在构建中被删除，请重新创建任务并等待构建结束后再删除。"
    fi

    if grep -Eqi "Properties should be assigned using the 'propName = value' syntax|Gradle-generated 'propName value'|groovy_space_assignment_syntax" "$gradleLogFile"; then
        local gradleDslLine
        gradleDslLine="$(grep -Ei -m 1 "Properties should be assigned using the 'propName = value' syntax|Use assignment" "$gradleLogFile" || true)"
        if [ -n "$gradleDslLine" ]; then
            log_warning "Gradle DSL 定位：$gradleDslLine"
        fi
        log_warning "修复建议：build.gradle 使用了旧 Groovy 空格赋值语法，请改为 propName = value；例如 compileSdk = 36、namespace = 'com.example.app'、useLegacyPackaging = true。"
    fi

    if grep -Eqi "Minimum supported Gradle version is|The current Gradle version is|This version of the Android Gradle plugin requires Gradle" "$gradleLogFile"; then
        log_warning "修复建议：Android Gradle Plugin 与 Gradle wrapper 版本不匹配。请按日志要求调整 gradle-wrapper.properties，或同步升级/降级 AGP 与 Gradle；这类大版本冲突平台不会自动强改。"
    fi

    if grep -Eqi "Kotlin Gradle plugin.*incompatible|Android Gradle plugin supports only Kotlin|No matching variant.*(kotlin-gradle-plugin|org\.jetbrains\.kotlin:kotlin)|The binary version of its metadata is" "$gradleLogFile"; then
        log_warning "修复建议：Kotlin Gradle Plugin 与 AGP/依赖版本存在大版本冲突。请统一 Kotlin、AGP、KSP/Compose 等插件版本；这类依赖矩阵问题平台只提供诊断，不自动改版本。"
    fi

    if grep -Eqi "path may not be null or empty string|path='null'|rootProject\.file\(.*null" "$gradleLogFile"; then
        log_warning "修复建议：项目签名脚本读取的 keystore 路径为空。若使用 RELEASE_STORE_FILE/RELEASE_STORE_PASSWORD 等环境变量，请确认构建环境已传入；平台已为原生构建注入这些兼容变量。"
    fi

    if grep -Eqi "Could not resolve project :|No matching variant of project :|No variants exist" "$gradleLogFile"; then
        log_warning "修复建议：Gradle 子模块缺失或未配置。请检查 settings.gradle 中 include 的模块是否都带有 build.gradle/build.gradle.kts；如果模块来自 Git submodule，请使用 git clone --recursive 后重新压缩完整源码，或把缺失模块目录补进 ZIP。"
    fi
}

runGradleReleaseBuild() {
    local gradleTask="$1"
    local outputLabel="$2"
    local gradleLogFile="/tmp/convertapk-gradle-${gradleTask}-$$.log"

    set +e
    ./gradlew "$gradleTask" "${GRADLE_INIT_ARGS[@]}" \
        --no-daemon \
        --stacktrace \
        --console=plain \
        --warning-mode all \
        -Dorg.gradle.jvmargs="-Xmx2048m -XX:MaxMetaspaceSize=512m" \
        -Dorg.gradle.parallel=false \
        -Dorg.gradle.caching=false 2>&1 | tee "$gradleLogFile"
    local gradleStatus=${PIPESTATUS[0]}
    set -e

    if [ "$gradleStatus" -ne 0 ]; then
        printGradleFailureHelp "$gradleLogFile"
        log_error "$outputLabel 构建失败"
        exit 1
    fi
}

if [ "$OUTPUT_FORMAT" = "aab" ]; then
    # 执行构建，添加 --info 查看详细日志，--stacktrace 查看错误栈
    runGradleReleaseBuild "bundleRelease" "AAB"

    # 找到生成的 AAB
    AAB_OUT_DIR="$(pwd)/app/build/outputs/bundle/release"
    AAB_PATH=$(find "$AAB_OUT_DIR" -maxdepth 1 -name "*.aab" -type f 2>/dev/null | head -n 1)
    if [ -z "$AAB_PATH" ]; then
        AAB_PATH=$(find . -name "*.aab" -path "*/release/*" -type f | head -n 1)
    fi

    if [ -z "$AAB_PATH" ] || [ ! -f "$AAB_PATH" ]; then
        log_error "未找到生成的AAB文件"
        ls -la "$AAB_OUT_DIR" 2>/dev/null || true
        exit 1
    fi

    log_success "AAB 构建完成: $AAB_PATH"
else
    # 执行构建，添加 --info 查看详细日志，--stacktrace 查看错误栈
    runGradleReleaseBuild "assembleRelease" "APK"

    # 找到生成的 APK
    APK_OUT_DIR="$(pwd)/app/build/outputs/apk/release"
    APK_PATH=$(find "$APK_OUT_DIR" -maxdepth 1 -name "*.apk" -type f 2>/dev/null | head -n 1)
    if [ -z "$APK_PATH" ]; then
        APK_PATH=$(find . -name "*.apk" -path "*/release/*" -type f | head -n 1)
    fi

    if [ -z "$APK_PATH" ] || [ ! -f "$APK_PATH" ]; then
        log_error "未找到生成的 APK 文件"
        ls -la "$APK_OUT_DIR" 2>/dev/null || true
        exit 1
    fi

    log_success "APK 构建完成: $APK_PATH"
fi

cd "$PROJECT_ROOT"

# ============================================
# 步骤 8: 生成/使用密钥库
# ============================================
log_info "Step 8: 准备签名密钥..."

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

cd "$ANDROID_BUILD_DIR"

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
    if [ $? -ne 0 ]; then
        # PKCS12 通常要求 keypass == storepass；如果用户填了不同的 keypass，keytool 可能会忽略，
        # 这里做一次兼容重试，避免“Wrong password”。
        if [ "$KEY_PASSWORD" != "$KEYSTORE_PASSWORD" ]; then
            log_warning "AAB 签名失败，尝试使用 key 密码=keystore 密码重试..."
            jarsigner \
                -digestalg SHA-256 \
                -sigalg SHA256withRSA \
                -keystore "$KEYSTORE_FILE" \
                -storepass "$KEYSTORE_PASSWORD" \
                -keypass "$KEYSTORE_PASSWORD" \
                -signedjar "$SIGNED_AAB" \
                "$UNSIGNED_AAB" \
                "$KEY_ALIAS"
        fi
        check_error "AAB 签名失败"
    fi

    # 验证签名
    log_info "验证 AAB 签名..."
    runSignatureVerification "AAB 签名验证" jarsigner -verify "$SIGNED_AAB" || { log_error "AAB 签名验证失败"; exit 1; }
    verifyOutputSignatureMatchesKeystore || { log_error "AAB 签名验证失败"; exit 1; }

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
    if [ $? -ne 0 ]; then
        # PKCS12 通常要求 keypass == storepass；如果用户填了不同的 keypass，keytool 可能会忽略，
        # 这里做一次兼容重试，避免“Wrong password”。
        if [ "$KEY_PASSWORD" != "$KEYSTORE_PASSWORD" ]; then
            log_warning "APK 签名失败，尝试使用 key 密码=keystore 密码重试..."
            apksigner sign \
                --ks "$KEYSTORE_FILE" \
                --ks-key-alias "$KEY_ALIAS" \
                --ks-pass pass:"$KEYSTORE_PASSWORD" \
                --key-pass pass:"$KEYSTORE_PASSWORD" \
                --v1-signing-enabled true \
                --v2-signing-enabled true \
                --v3-signing-enabled true \
                --out "$SIGNED_APK" \
                "$ALIGNED_APK"
        fi
        check_error "APK 签名失败"
    fi

    # 验证签名
    log_info "验证 APK 签名..."
    runSignatureVerification "APK 签名验证" apksigner verify "$SIGNED_APK" || { log_error "APK 签名验证失败"; exit 1; }
    verifyOutputSignatureMatchesKeystore || { log_error "APK 签名验证失败"; exit 1; }

    log_success "APK 签名完成"
    FINAL_OUTPUT="$SIGNED_APK"
fi

# ============================================
# 步骤 11: 跳过 Android 源码打包
# ============================================
log_info "Step 11: 跳过 Android 源码打包，构建完成后会自动清理中间产物"

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
