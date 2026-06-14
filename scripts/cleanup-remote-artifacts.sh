#!/usr/bin/env bash
set -euo pipefail

# ConvertAPK 远程服务器自动清理脚本。
# 默认只清理三类内容：超过下载期的 outputs 产物、task-assets 中误同步的 android_source_*、超过保留期的构建缓存。
DATA_ROOT="${DATA_ROOT:-/data/convertapk}"
ADMIN_STORAGE_ROOT="${ADMIN_STORAGE_ROOT:-/data/convertapk-admin/storage}"
OUTPUT_RETENTION_DAYS="${OUTPUT_RETENTION_DAYS:-3}"
CACHE_MAX_AGE_DAYS="${CACHE_MAX_AGE_DAYS:-7}"
DRY_RUN="${DRY_RUN:-0}"
LOG_FILE="${LOG_FILE:-}"

if [[ -n "$LOG_FILE" ]]; then
  mkdir -p "$(dirname "$LOG_FILE")"
  exec >> "$LOG_FILE" 2>&1
fi

log() {
  printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

isPositiveInt() {
  [[ "$1" =~ ^[0-9]+$ ]] && [[ "$1" -gt 0 ]]
}

if ! isPositiveInt "$OUTPUT_RETENTION_DAYS"; then
  log "OUTPUT_RETENTION_DAYS 非法，已回退为 3"
  OUTPUT_RETENTION_DAYS=3
fi

if ! isPositiveInt "$CACHE_MAX_AGE_DAYS"; then
  log "CACHE_MAX_AGE_DAYS 非法，已回退为 7"
  CACHE_MAX_AGE_DAYS=7
fi

removedCount=0
removedBytes=0

pathBytes() {
  du -sb "$1" 2>/dev/null | awk '{print $1}' || printf '0'
}

safeDeletePath() {
  local target="$1"
  local allowedRoot="$2"
  local realTarget
  local realRoot
  realTarget="$(realpath -m "$target")"
  realRoot="$(realpath -m "$allowedRoot")"

  case "$realTarget" in
    "$realRoot"/*) ;;
    *)
      log "跳过异常路径：$target"
      return 0
      ;;
  esac

  local bytes
  bytes="$(pathBytes "$target")"
  removedCount=$((removedCount + 1))
  removedBytes=$((removedBytes + bytes))

  if [[ "$DRY_RUN" == "1" ]]; then
    log "预演删除：$target"
    return 0
  fi

  rm -rf -- "$target"
  log "已删除：$target"
}

cleanAndroidSources() {
  local taskAssetsRoot="$ADMIN_STORAGE_ROOT/task-assets"
  if [[ ! -d "$taskAssetsRoot" ]]; then
    log "task-assets 目录不存在，跳过：$taskAssetsRoot"
    return 0
  fi

  while IFS= read -r -d '' item; do
    safeDeletePath "$item" "$taskAssetsRoot"
  done < <(find "$taskAssetsRoot" -mindepth 1 \( -type f -o -type d \) -name 'android_source_*' -print0)
}

cleanExpiredOutputs() {
  local outputsRoot="$DATA_ROOT/outputs"
  local expireMinutes=$((OUTPUT_RETENTION_DAYS * 24 * 60))
  if [[ ! -d "$outputsRoot" ]]; then
    log "outputs 目录不存在，跳过：$outputsRoot"
    return 0
  fi

  while IFS= read -r -d '' item; do
    safeDeletePath "$item" "$outputsRoot"
  done < <(find "$outputsRoot" -maxdepth 1 -type f \( -name '*.apk' -o -name '*.aab' -o -name '*.exe' -o -name '*.zip' \) -mmin +"$expireMinutes" -print0)
}

cleanBuildCaches() {
  local cacheRoot
  local cacheRoots=(
    "$DATA_ROOT/gradle-cache"
    "$DATA_ROOT/npm-cache"
    "$DATA_ROOT/electron-cache"
    "$DATA_ROOT/electron-builder-cache"
  )

  for cacheRoot in "${cacheRoots[@]}"; do
    if [[ ! -d "$cacheRoot" ]]; then
      continue
    fi
    while IFS= read -r -d '' item; do
      safeDeletePath "$item" "$cacheRoot"
    done < <(find "$cacheRoot" -mindepth 1 -maxdepth 1 -mmin +$((CACHE_MAX_AGE_DAYS * 24 * 60)) -print0)
  done
}

log "开始清理：outputs 保留 ${OUTPUT_RETENTION_DAYS} 天，缓存保留 ${CACHE_MAX_AGE_DAYS} 天，DRY_RUN=${DRY_RUN}"
cleanAndroidSources
cleanExpiredOutputs
cleanBuildCaches
log "清理结束：命中 ${removedCount} 项，约 ${removedBytes} 字节"