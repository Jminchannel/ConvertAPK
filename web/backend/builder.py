"""
APK Builder 模块
负责与 `apk-worker` 构建器交互。
支持任务队列调度与并发控制。
"""
import os
import json
import re
import shutil
import stat
import subprocess
import threading
import time
import queue
import zipfile
from datetime import datetime, timedelta
from pathlib import Path, PurePosixPath
from typing import Callable, Optional, List, Tuple
from redis import Redis
from redis.exceptions import RedisError

from local_builder import run_local_build
import env_setup
from admin_client import report_task_logs, upload_task_assets, report_task_status, flush_task_assets_queue, fetch_feature_flags
from build_failure_diagnosis import (
    create_failed_diagnosis,
    create_idle_diagnosis,
    create_running_diagnosis,
    diagnose_build_failure,
    resolve_openrouter_diag_runtime_config,
)

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent
APK_WORKER_DIR = PROJECT_ROOT / "apk-worker"
INPUT_DIR = APK_WORKER_DIR / "input"
OUTPUT_DIR = APK_WORKER_DIR / "output"
KEYSTORE_DIR = APK_WORKER_DIR / "keystore"

# 后端目录
BACKEND_DIR = Path(__file__).parent

# 数据目录（支持配置，便于容器化或云部署场景落盘持久化）
_data_dir_raw = os.getenv("APK_BUILDER_DATA_DIR", "").strip()
if not _data_dir_raw:
    try:
        _data_dir_raw = str(env_setup.get_config().get("data_root", "")).strip()
    except Exception:
        _data_dir_raw = ""
if _data_dir_raw:
    DATA_DIR = Path(_data_dir_raw).expanduser()
    if not DATA_DIR.is_absolute():
        DATA_DIR = (BACKEND_DIR / DATA_DIR).resolve()
else:
    # Default to per-user app data on Windows; fallback to backend dir.
    if os.name == "nt":
        appdata_root = os.getenv("APPDATA", "").strip()
        if appdata_root:
            DATA_DIR = Path(appdata_root) / "ConvertAPK"
        else:
            DATA_DIR = BACKEND_DIR
    else:
        DATA_DIR = BACKEND_DIR

# 云部署建议：backend 使用同一数据卷保存 uploads/tasks/outputs/logs，
# 并在调用 apk-builder 容器时挂载同一数据卷，避免宿主路径映射差异。
DATA_VOLUME = os.getenv("APK_BUILDER_DATA_VOLUME", "").strip()

try:
    DESKTOP_OUTPUT_RETENTION_MINUTES = max(int(os.getenv("DESKTOP_OUTPUT_RETENTION_MINUTES", "30") or "30"), 1)
except ValueError:
    DESKTOP_OUTPUT_RETENTION_MINUTES = 30
DESKTOP_OUTPUT_RETENTION_DELTA = timedelta(minutes=DESKTOP_OUTPUT_RETENTION_MINUTES)

_templates_dir_raw = os.getenv("APK_BUILDER_TEMPLATES_DIR", "").strip()
if _templates_dir_raw:
    TEMPLATES_DIR = os.path.expanduser(_templates_dir_raw)
elif not DATA_VOLUME:
    _templates_candidate = PROJECT_ROOT / "templates"
    TEMPLATES_DIR = str(_templates_candidate) if _templates_candidate.exists() else ""
else:
    TEMPLATES_DIR = ""
DATA_VOLUME_TEMPLATE_SUBDIR = Path("ConvertAPK-Desktop") / "templates"
DATA_VOLUME_TEMPLATE_CONTAINER_DIR = f"/data/{DATA_VOLUME_TEMPLATE_SUBDIR.as_posix()}"
ANDROID_TEMPLATE_NAMES = ("Tubbim", "HTML2APK")


def _is_android_templates_ready(root: Path) -> bool:
    return all((root / name / "gradlew").exists() for name in ANDROID_TEMPLATE_NAMES)


def _sync_android_templates_to_data_volume(on_log: Optional[Callable[[str], None]] = None) -> str:
    """同步 Android 模板到共享数据卷，供 apk-builder 子容器读取。"""
    if not DATA_VOLUME:
        return ""
    source_root = PROJECT_ROOT / "templates"
    target_root = DATA_DIR / DATA_VOLUME_TEMPLATE_SUBDIR
    if not source_root.exists():
        return DATA_VOLUME_TEMPLATE_CONTAINER_DIR if _is_android_templates_ready(target_root) else ""

    target_root.mkdir(parents=True, exist_ok=True)
    ignore = shutil.ignore_patterns(".git", ".gradle", ".gradle-home", ".kotlin", "build", "node_modules")
    copied = False
    for template_name in ANDROID_TEMPLATE_NAMES:
        source_dir = source_root / template_name
        if not source_dir.exists():
            continue
        shutil.copytree(source_dir, target_root / template_name, dirs_exist_ok=True, ignore=ignore)
        copied = True
    if copied and on_log:
        on_log(f"[Templates] Android 模板已同步到 {target_root}")
    return DATA_VOLUME_TEMPLATE_CONTAINER_DIR if _is_android_templates_ready(target_root) else ""


def _ensure_writable_data_dir(preferred_dir: Path) -> Path:
    """确保数据目录可写；若不可写则自动回退到本地可写目录。"""
    fallback_dirs = [BACKEND_DIR / ".runtime-data"]
    if os.name == "nt":
        appdata_root = os.getenv("APPDATA", "").strip()
        if appdata_root:
            fallback_dirs.insert(0, Path(appdata_root) / "ConvertAPK")

    candidates: list[Path] = []
    for candidate in [preferred_dir, *fallback_dirs]:
        resolved = candidate.expanduser()
        if not resolved.is_absolute():
            resolved = (BACKEND_DIR / resolved).resolve()
        if resolved not in candidates:
            candidates.append(resolved)

    last_error: Exception | None = None
    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            probe_path = candidate / ".write-probe"
            probe_path.write_text("ok", encoding="utf-8")
            probe_path.unlink(missing_ok=True)
            return candidate
        except Exception as exc:
            last_error = exc

    if last_error is not None:
        raise last_error
    return preferred_dir


DATA_DIR = _ensure_writable_data_dir(DATA_DIR)
UPLOAD_DIR = DATA_DIR / "uploads"
BACKEND_OUTPUT_DIR = DATA_DIR / "outputs"
LOGS_DIR = DATA_DIR / "logs"
TASKS_DIR = DATA_DIR / "tasks"  # 每个任务的独立目录
TASK_INPUT_ASSETS_DIR = DATA_DIR / "task-inputs"
GRADLE_WRAPPER_CACHE = DATA_DIR / "gradle-wrapper-cache"  # 全局 Gradle wrapper 缓存
NPM_CACHE_DIR = DATA_DIR / "npm-cache"
AUTO_CLEAN_BUILD_OUTPUTS = os.getenv("APK_BUILDER_AUTO_CLEAN_OUTPUTS", "").strip().lower() in {"1", "true", "yes", "on"}
AI_PROVIDER_DEFAULT = "openrouter"
AI_API_URL_DEFAULT = "https://openrouter.ai/api/v1/chat/completions"
AI_MODEL_DEFAULT = "qwen/qwen3.5-flash-02-23"
AI_TIMEOUT_SECONDS_DEFAULT = 18
AI_TIMEOUT_SECONDS_MIN = 8
AI_TIMEOUT_SECONDS_MAX = 120
TASK_AI_STATE_REDIS_URL = str(
    os.getenv("TASK_AI_STATE_REDIS_URL")
    or os.getenv("AUTH_SMS_REDIS_URL")
    or ""
).strip()
TASK_AI_STATE_REDIS_PREFIX = str(
    os.getenv("TASK_AI_STATE_REDIS_PREFIX")
    or "convertapk:task:ai:"
).strip() or "convertapk:task:ai:"
try:
    TASK_AI_DIAG_COOLDOWN_SECONDS = max(
        int(os.getenv("TASK_AI_DIAG_COOLDOWN_SECONDS", "600") or "600"),
        60,
    )
except ValueError:
    TASK_AI_DIAG_COOLDOWN_SECONDS = 600
TASK_AI_STATE_REDIS_LOCK = threading.Lock()
TASK_AI_STATE_REDIS_CLIENT: Optional[Redis] = None
TASK_AI_DIAG_COOLDOWN_FALLBACK_LOCK = threading.Lock()
TASK_AI_DIAG_COOLDOWN_FALLBACK: dict[str, float] = {}


def _to_runtime_bool(value, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def _normalize_ai_timeout_seconds(value) -> int:
    try:
        timeout_seconds = int(value)
    except Exception:
        return AI_TIMEOUT_SECONDS_DEFAULT
    if timeout_seconds < AI_TIMEOUT_SECONDS_MIN:
        return AI_TIMEOUT_SECONDS_MIN
    if timeout_seconds > AI_TIMEOUT_SECONDS_MAX:
        return AI_TIMEOUT_SECONDS_MAX
    return timeout_seconds


def _normalize_ai_api_url(value: str | None) -> str:
    api_url = str(value or "").strip()
    if not api_url:
        return AI_API_URL_DEFAULT
    normalized = api_url.rstrip("/")
    if normalized.lower() == "https://openrouter.ai/api/v1":
        return f"{normalized}/chat/completions"
    return api_url


def _task_ai_state_redis_key(suffix: str) -> str:
    return f"{TASK_AI_STATE_REDIS_PREFIX}{suffix}"


def _normalize_client_state_key(client_id: str | None) -> str:
    normalized = str(client_id or "").strip().lower()
    return normalized


def _get_task_ai_state_redis_client() -> Optional[Redis]:
    global TASK_AI_STATE_REDIS_CLIENT
    if not TASK_AI_STATE_REDIS_URL:
        return None
    if TASK_AI_STATE_REDIS_CLIENT is not None:
        return TASK_AI_STATE_REDIS_CLIENT
    with TASK_AI_STATE_REDIS_LOCK:
        if TASK_AI_STATE_REDIS_CLIENT is not None:
            return TASK_AI_STATE_REDIS_CLIENT
        try:
            client = Redis.from_url(
                TASK_AI_STATE_REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
                health_check_interval=30,
            )
            client.ping()
        except Exception:
            return None
        TASK_AI_STATE_REDIS_CLIENT = client
        return client


def _set_client_ai_diag_cooldown(
    client_id: str | None,
    ttl_seconds: int | None = None,
    task_id: str | None = None,
    source: str = "ai",
) -> None:
    normalized_key = _normalize_client_state_key(client_id)
    if not normalized_key:
        return
    ttl = max(int(ttl_seconds or TASK_AI_DIAG_COOLDOWN_SECONDS), 60)
    payload = {
        "client_id": normalized_key,
        "task_id": str(task_id or "").strip(),
        "source": str(source or "ai").strip() or "ai",
        "set_at": datetime.now().isoformat(),
    }
    redis_client = _get_task_ai_state_redis_client()
    if redis_client is not None:
        redis_key = _task_ai_state_redis_key(f"diag-cooldown:{normalized_key}")
        try:
            redis_client.set(redis_key, json.dumps(payload, ensure_ascii=False), ex=ttl)
            return
        except RedisError:
            pass
    with TASK_AI_DIAG_COOLDOWN_FALLBACK_LOCK:
        TASK_AI_DIAG_COOLDOWN_FALLBACK[normalized_key] = time.time() + float(ttl)


def _get_client_ai_diag_cooldown_remaining_seconds(client_id: str | None) -> int:
    normalized_key = _normalize_client_state_key(client_id)
    if not normalized_key:
        return 0
    redis_client = _get_task_ai_state_redis_client()
    if redis_client is not None:
        redis_key = _task_ai_state_redis_key(f"diag-cooldown:{normalized_key}")
        try:
            ttl = int(redis_client.ttl(redis_key))
            if ttl > 0:
                return ttl
        except RedisError:
            pass
    with TASK_AI_DIAG_COOLDOWN_FALLBACK_LOCK:
        expires_at = float(TASK_AI_DIAG_COOLDOWN_FALLBACK.get(normalized_key, 0.0) or 0.0)
        if expires_at <= 0:
            return 0
        remaining = int(max(0.0, expires_at - time.time()))
        if remaining <= 0:
            TASK_AI_DIAG_COOLDOWN_FALLBACK.pop(normalized_key, None)
            return 0
        return remaining


def _apply_ai_diag_cooldown_to_runtime_config(
    client_id: str | None,
    runtime_config: dict | None,
    scope: str = "",
) -> tuple[dict, int]:
    base_config = dict(runtime_config or {})
    remaining = _get_client_ai_diag_cooldown_remaining_seconds(client_id)
    if remaining <= 0:
        return base_config, 0
    base_config["enabled"] = False
    base_config["cooldown_rule_only"] = True
    base_config["cooldown_remaining_seconds"] = remaining
    base_config["cooldown_scope"] = str(scope or "").strip()
    return base_config, remaining


def _resolve_task_ai_runtime_config(client_id: str | None) -> dict:
    default_enabled = _to_runtime_bool(os.getenv("OPENROUTER_DIAG_ENABLED"), default=True)
    config = {
        "enabled": default_enabled,
        "provider": str(os.getenv("TASK_AI_PROVIDER") or AI_PROVIDER_DEFAULT).strip().lower() or AI_PROVIDER_DEFAULT,
        "api_url": str(
            os.getenv("TASK_AI_RISK_GUARD_API_URL")
            or os.getenv("OPENROUTER_API_URL")
            or AI_API_URL_DEFAULT
        ).strip(),
        "api_key": str(
            os.getenv("TASK_AI_RISK_GUARD_API_KEY")
            or os.getenv("OPENROUTER_API_KEY")
            or ""
        ).strip(),
        "model": str(
            os.getenv("TASK_AI_RISK_GUARD_MODEL")
            or os.getenv("OPENROUTER_MODEL")
            or AI_MODEL_DEFAULT
        ).strip(),
        "timeout_seconds": _normalize_ai_timeout_seconds(
            os.getenv("TASK_AI_RISK_GUARD_TIMEOUT_SECONDS")
            or os.getenv("OPENROUTER_DIAG_TIMEOUT_SECONDS")
            or AI_TIMEOUT_SECONDS_DEFAULT
        ),
        "site_url": str(os.getenv("OPENROUTER_SITE_URL") or "").strip(),
        "app_name": str(os.getenv("OPENROUTER_APP_NAME") or "ConvertAPK-EXE").strip(),
    }
    normalized_client_id = str(client_id or "").strip()
    if not normalized_client_id:
        config["api_url"] = _normalize_ai_api_url(config.get("api_url"))
        return config
    try:
        flags = fetch_feature_flags(client_id=normalized_client_id)
    except Exception:
        flags = None
    if not isinstance(flags, dict):
        return config
    if "ai_enabled" in flags:
        config["enabled"] = _to_runtime_bool(flags.get("ai_enabled"), default=config["enabled"])
    ai_provider = str(flags.get("ai_provider") or "").strip().lower()
    if ai_provider:
        config["provider"] = ai_provider
    ai_api_url = str(flags.get("ai_api_url") or "").strip()
    if ai_api_url:
        config["api_url"] = ai_api_url
    ai_api_key = str(flags.get("ai_api_key") or "").strip()
    if ai_api_key:
        config["api_key"] = ai_api_key
    ai_model = str(flags.get("ai_model") or "").strip()
    if ai_model:
        config["model"] = ai_model
    if "ai_timeout_seconds" in flags:
        config["timeout_seconds"] = _normalize_ai_timeout_seconds(flags.get("ai_timeout_seconds"))
    config["api_url"] = _normalize_ai_api_url(config.get("api_url"))
    return config

# Gradle 缓存策略（解决“开始构建响应慢/要等很久”的问题）：
# - volume: 使用 Docker volume 持久化 `/root/.gradle`（推荐，跨任务复用，且无需复制大缓存）
# - task:   使用任务目录下的 gradle 缓存（兼容模式，会在任务启动时复制全局 wrapper 缓存）
GRADLE_CACHE_MODE = os.getenv("APK_BUILDER_GRADLE_CACHE_MODE", "volume").strip().lower()
if GRADLE_CACHE_MODE not in {"volume", "task"}:
    GRADLE_CACHE_MODE = "volume"

# 后端容器化 + DATA_VOLUME 模式下，task 方式可能出现宿主路径映射问题，这里强制使用 volume。
if DATA_VOLUME and GRADLE_CACHE_MODE == "task":
    GRADLE_CACHE_MODE = "volume"

GRADLE_CACHE_VOLUME = os.getenv("APK_BUILDER_GRADLE_CACHE_VOLUME", "convertapk-gradle-cache").strip() or "convertapk-gradle-cache"
APK_BUILDER_IMAGE = os.getenv("APK_BUILDER_IMAGE", "apk-builder:latest").strip() or "apk-builder:latest"
DESKTOP_BUILDER_IMAGE = os.getenv("DESKTOP_BUILDER_IMAGE", "desktop-builder:latest").strip() or "desktop-builder:latest"

# 确保目录存在
DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
BACKEND_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)
TASKS_DIR.mkdir(parents=True, exist_ok=True)
TASK_INPUT_ASSETS_DIR.mkdir(parents=True, exist_ok=True)
NPM_CACHE_DIR.mkdir(parents=True, exist_ok=True)

_UNSIGNED_MARKERS = ("unsigned", "unaligned", "aligned")


def _is_unsigned_artifact(name: str) -> bool:
    lower = (name or "").lower()
    if "unsigned" in lower or "unaligned" in lower:
        return True
    if "aligned" in lower and "signed" not in lower:
        return True
    return False


def _select_artifact_file(
    artifact_files: list[Path],
    app_name: str,
    version_name: str,
    artifact_ext: str,
) -> Path | None:
    if not artifact_files:
        return None
    app_name = (app_name or "").strip()
    version_name = (version_name or "").strip()
    if app_name and version_name:
        exact = f"{app_name}-v{version_name}{artifact_ext}"
        for item in artifact_files:
            if item.name == exact:
                return item
    if version_name:
        candidates = [
            item
            for item in artifact_files
            if version_name in item.name and not _is_unsigned_artifact(item.name)
        ]
        if candidates:
            return max(candidates, key=lambda p: p.stat().st_mtime)
    candidates = [item for item in artifact_files if not _is_unsigned_artifact(item.name)]
    if candidates:
        return max(candidates, key=lambda p: p.stat().st_mtime)
    return max(artifact_files, key=lambda p: p.stat().st_mtime)


def _parse_hex_color(raw: str) -> Optional[Tuple[int, int, int]]:
    value = (raw or "").strip().lstrip("#")
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    elif len(value) == 4:
        value = "".join(ch * 2 for ch in value[1:])
    elif len(value) == 8:
        value = value[2:]
    if len(value) != 6:
        return None
    try:
        r = int(value[0:2], 16)
        g = int(value[2:4], 16)
        b = int(value[4:6], 16)
    except ValueError:
        return None
    return r, g, b


def _is_light_color(color: str) -> bool:
    value = (color or "").strip().lower()
    if not value or value == "transparent":
        return True
    if value in {"white", "#ffffff", "#ffffffff"}:
        return True
    if value in {"black", "#000000", "#ff000000"}:
        return False
    rgb = _parse_hex_color(value)
    if not rgb:
        return True
    r, g, b = rgb
    luminance = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255.0
    return luminance >= 0.6


def _normalize_status_bar_color(color: str) -> str:
    value = str(color or "").strip()
    if not value:
        return "#FFFFFF"
    lower = value.lower()
    if lower in {"transparent", "@android:color/transparent"}:
        return "transparent"
    if lower == "white":
        return "#FFFFFF"
    if re.fullmatch(r"#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{8})", value):
        return value.upper()
    return "#FFFFFF"


def _iter_zip_entries(zip_file: zipfile.ZipFile):
    for info in zip_file.infolist():
        if info.is_dir():
            continue
        raw_name = str(info.filename or "").replace("\\", "/").strip()
        if not raw_name:
            continue
        normalized = PurePosixPath(raw_name.lstrip("/"))
        parts = [part for part in normalized.parts if part and part != "."]
        if not parts or any(part == ".." for part in parts):
            continue
        yield info, parts


def _safe_task_asset_segment(value: str, fallback: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in str(value or "").strip())
    return safe or fallback


def _link_or_copy_file(src_path: Path, dst_path: Path) -> None:
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    if dst_path.exists():
        dst_path.unlink()
    try:
        os.link(str(src_path), str(dst_path))
    except Exception:
        shutil.copy2(str(src_path), str(dst_path))


def get_task_asset_dir(task_id: str) -> Path:
    return TASK_INPUT_ASSETS_DIR / _safe_task_asset_segment(task_id, "task")


def get_persisted_task_asset_path(task_id: str, filename: str) -> Path:
    return get_task_asset_dir(task_id) / _safe_task_asset_segment(filename, "file")


def persist_task_asset(task_id: str, filename: str, source_path: Path, move: bool = False) -> Path:
    target_path = get_persisted_task_asset_path(task_id, filename)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        if source_path.resolve() == target_path.resolve():
            return target_path
    except Exception:
        pass
    if target_path.exists():
        target_path.unlink()
    if move:
        shutil.move(str(source_path), str(target_path))
    else:
        shutil.copy2(str(source_path), str(target_path))
    return target_path


def restore_task_input_asset(task_id: str, filename: str, task_input_dir: Path) -> Path | None:
    source_path = get_persisted_task_asset_path(task_id, filename)
    if not source_path.exists():
        return None
    target_path = task_input_dir / filename
    _link_or_copy_file(source_path, target_path)
    return target_path


def ensure_task_input_assets(task_id: str, task_input_dir: Path) -> dict[str, Path]:
    restored: dict[str, Path] = {}
    task_input_dir.mkdir(parents=True, exist_ok=True)
    for filename in ("project.zip", "logo.png", "index.html"):
        target_path = task_input_dir / filename
        if target_path.exists():
            continue
        restored_path = restore_task_input_asset(task_id, filename, task_input_dir)
        if restored_path:
            restored[filename] = restored_path
    return restored


def delete_task_asset_dir(task_id: str) -> None:
    asset_dir = get_task_asset_dir(task_id)
    if asset_dir.exists():
        _remove_tree(asset_dir)


def _restore_html_task_input(task_input_dir: Path) -> None:
    zip_file = task_input_dir / "project.zip"
    if not zip_file.exists():
        return

    html_assets_dir = task_input_dir / "html_assets"
    if html_assets_dir.exists():
        shutil.rmtree(html_assets_dir, ignore_errors=True)
    html_assets_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_file, "r") as archive:
        index_candidates: list[tuple[int, int, str]] = []
        for _, parts in _iter_zip_entries(archive):
            lower_parts = [part.lower() for part in parts]
            if any(part in {"node_modules", ".git", "android", "__macosx"} for part in lower_parts):
                continue
            if lower_parts[-1] != "index.html":
                continue
            entry_name = str(PurePosixPath(*parts))
            index_candidates.append((len(parts), len(entry_name), entry_name))
        if not index_candidates:
            raise FileNotFoundError(f"HTML输入缺少 index.html: {zip_file}")

        index_candidates.sort(key=lambda item: (item[0], item[1], item[2]))
        normalized_index = PurePosixPath(index_candidates[0][2])
        root_parts = tuple(part for part in normalized_index.parts[:-1] if part)

        for info, parts in _iter_zip_entries(archive):
            lower_parts = [part.lower() for part in parts]
            if any(part in {"node_modules", ".git", "android", "__macosx"} for part in lower_parts):
                continue
            if root_parts and tuple(parts[: len(root_parts)]) != root_parts:
                continue
            relative_parts = parts[len(root_parts):] if root_parts else parts
            if not relative_parts:
                continue
            target = html_assets_dir.joinpath(*relative_parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info, "r") as source, open(target, "wb") as output:
                shutil.copyfileobj(source, output)

    html_index = html_assets_dir / "index.html"
    if not html_index.exists():
        raise FileNotFoundError(f"HTML输入缺少 index.html: {zip_file}")
    shutil.copy2(str(html_index), str(task_input_dir / "index.html"))


def _clear_dir_contents(target_dir: Path) -> None:
    if not target_dir.exists():
        return
    for item in target_dir.iterdir():
        if item.is_dir():
            _remove_tree(item)
        else:
            try:
                item.unlink()
            except Exception:
                pass


def _handle_remove_readonly(func, path, _exc_info) -> None:
    try:
        os.chmod(path, stat.S_IWRITE)
    except Exception:
        pass
    try:
        func(path)
    except Exception:
        pass


def _remove_tree(target_dir: Path, retries: int = 6, delay_seconds: float = 0.5) -> None:
    for attempt in range(max(retries, 1)):
        if not target_dir.exists():
            return
        try:
            shutil.rmtree(target_dir, onerror=_handle_remove_readonly)
        except Exception:
            pass
        if not target_dir.exists():
            return
        time.sleep(delay_seconds * (attempt + 1))


def _cleanup_task_intermediates(task_id: str, task_mode: str = "convert") -> None:
    task_dir = TASKS_DIR / task_id
    task_input_dir = task_dir / "input"
    for name in ("project", "gradle", "_tmp_html_libs", "desktop-source", "desktop-app"):
        candidate = task_dir / name
        if candidate.exists():
            _remove_tree(candidate)

    _clear_dir_contents(task_dir / "output")

    if str(task_mode or "").strip().lower() == "html" and (task_input_dir / "project.zip").exists():
        html_file = task_input_dir / "index.html"
        if html_file.exists():
            try:
                html_file.unlink()
            except Exception:
                pass
        html_assets_dir = task_input_dir / "html_assets"
        if html_assets_dir.exists():
            _remove_tree(html_assets_dir)


def should_auto_clean_build_outputs() -> bool:
    return AUTO_CLEAN_BUILD_OUTPUTS


def cleanup_task_generated_artifacts(
    task_id: str,
    task_mode: str = "convert",
    output_filename: Optional[str] = None,
    remove_backend_output: bool = False,
) -> None:
    if remove_backend_output and output_filename:
        safe_name = Path(str(output_filename)).name
        if safe_name:
            output_path = BACKEND_OUTPUT_DIR / safe_name
            if output_path.exists():
                try:
                    output_path.unlink()
                except Exception:
                    pass
    _cleanup_task_intermediates(task_id, task_mode)


def _has_pending_generated_artifacts(
    task_id: str,
    task_mode: str = "convert",
    output_filename: Optional[str] = None,
    remove_backend_output: bool = False,
) -> bool:
    task_dir = TASKS_DIR / task_id
    if any((task_dir / name).exists() for name in ("project", "gradle", "_tmp_html_libs", "desktop-source", "desktop-app")):
        return True
    output_dir = task_dir / "output"
    if output_dir.exists():
        try:
            next(output_dir.iterdir())
            return True
        except StopIteration:
            pass
        except Exception:
            return True
    if remove_backend_output and output_filename:
        safe_name = Path(str(output_filename)).name
        if safe_name and (BACKEND_OUTPUT_DIR / safe_name).exists():
            return True
    if str(task_mode or "").strip().lower() == "html" and (task_dir / "input" / "project.zip").exists():
        if (task_dir / "input" / "html_assets").exists():
            return True
    return False


def schedule_cleanup_task_generated_artifacts(
    task_id: str,
    task_mode: str = "convert",
    output_filename: Optional[str] = None,
    remove_backend_output: bool = False,
) -> None:
    cleanup_task_generated_artifacts(
        task_id,
        task_mode,
        output_filename=output_filename,
        remove_backend_output=remove_backend_output,
    )

    def _worker() -> None:
        for delay_seconds in (1.0, 2.0, 4.0, 8.0, 16.0):
            if not _has_pending_generated_artifacts(
                task_id,
                task_mode,
                output_filename=output_filename,
                remove_backend_output=remove_backend_output,
            ):
                return
            time.sleep(delay_seconds)
            cleanup_task_generated_artifacts(
                task_id,
                task_mode,
                output_filename=output_filename,
                remove_backend_output=remove_backend_output,
            )

    threading.Thread(target=_worker, daemon=True).start()


def _silent_upload_task_assets(task_id: str, task) -> None:
    try:
        config_data = task.config.model_dump() if hasattr(task.config, "model_dump") else task.config.dict()
    except Exception:
        config_data = {}
    task_mode = str(getattr(task, "mode", "convert") or "convert").strip().lower()
    config_data["build_type"] = task_mode
    config_data["task_mode"] = task_mode
    task_dir = TASKS_DIR / task_id
    task_input_dir = task_dir / "input"
    ensure_task_input_assets(task_id, task_input_dir)
    zip_path = task_input_dir / "project.zip"
    html_path = task_input_dir / "index.html"
    icon_path = task_input_dir / "logo.png"
    persisted_zip_path = get_persisted_task_asset_path(task_id, "project.zip")
    persisted_html_path = get_persisted_task_asset_path(task_id, "index.html")
    persisted_icon_path = get_persisted_task_asset_path(task_id, "logo.png")
    upload_zip_path = persisted_zip_path if persisted_zip_path.exists() else zip_path
    upload_html_path = persisted_html_path if persisted_html_path.exists() else html_path
    upload_icon_path = icon_path if icon_path.exists() else persisted_icon_path
    zip_info = {"build_type": task_mode}
    if upload_zip_path.exists():
        zip_info.update({"name": upload_zip_path.name, "size": upload_zip_path.stat().st_size})
    keystore_info = {
        "alias": config_data.get("keystore_alias") or "key0",
        "keystore_password": config_data.get("keystore_password") or "123456",
        "key_password": config_data.get("key_password") or "123456",
        "reuse_keystore_from": task.reuse_keystore_from,
    }
    upload_task_assets(
        task_id,
        task.client_id or "",
        datetime.now().isoformat(),
        zip_info,
        config_data,
        zip_path=str(upload_zip_path) if upload_zip_path.exists() else None,
        html_path=str(upload_html_path) if upload_html_path.exists() else None,
        icon_path=str(upload_icon_path) if upload_icon_path.exists() else None,
        keystore_info=keystore_info,
    )
GRADLE_WRAPPER_CACHE.mkdir(parents=True, exist_ok=True)


def _decode_subprocess_output(raw: bytes) -> str:
    """优先按 UTF-8 解码，失败时回退到 GB18030，减少中文日志乱码。"""
    if not raw:
        return ""
    for encoding in ("utf-8", "gb18030"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


class APKBuilder:
    """APK build helper."""
    
    def __init__(self):
        # 纭繚鐩綍瀛樺湪
        INPUT_DIR.mkdir(parents=True, exist_ok=True)
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        KEYSTORE_DIR.mkdir(parents=True, exist_ok=True)
        BACKEND_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        self.running_processes = {}
        self.builder_mode = os.getenv("APK_BUILDER_MODE", "").strip().lower()
        if not self.builder_mode:
            self.builder_mode = "local" if os.name == "nt" else "docker"

    def cancel_task(self, task_id: str) -> None:
        process = self.running_processes.get(task_id)
        if process is None:
            return
        try:
            process.terminate()
        except Exception:
            pass
    
    def _copy_gradle_wrapper_cache(self, task_gradle_dir: Path):
        """
        将全局 Gradle wrapper 缓存复制到任务目录。
        避免每次构建都重新下载 Gradle 发行包。
        """
        global_wrapper_dir = GRADLE_WRAPPER_CACHE / "wrapper" / "dists"
        task_wrapper_dir = task_gradle_dir / "wrapper" / "dists"
        
        # 如果全局缓存存在且任务目录没有 wrapper，则复制一份用于当前任务。
        if global_wrapper_dir.exists() and not task_wrapper_dir.exists():
            print(f"[Gradle] 复制全局 Gradle wrapper 缓存到任务目录...")
            task_wrapper_dir.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(global_wrapper_dir, task_wrapper_dir)
            print(f"[Gradle] 缓存复制完成")
        elif task_wrapper_dir.exists():
            print(f"[Gradle] 任务目录已存在 Gradle wrapper 缓存，跳过复制")
    
    def _save_gradle_wrapper_cache(self, task_gradle_dir: Path):
        """
        将任务目录中的 Gradle wrapper 缓存回写到全局缓存。
        供后续任务复用。
        """
        task_wrapper_dir = task_gradle_dir / "wrapper" / "dists"
        global_wrapper_dir = GRADLE_WRAPPER_CACHE / "wrapper" / "dists"
        
        # 如果任务目录有 wrapper，则把新版本补充到全局缓存。
        if task_wrapper_dir.exists():
            try:
                # 只获取目录，忽略文件（例如 CACHEDIR.TAG）
                task_versions = [d for d in task_wrapper_dir.iterdir() if d.is_dir()]
                
                # 仅补充全局缓存中不存在的版本
                for version_dir in task_versions:
                    global_version_dir = global_wrapper_dir / version_dir.name
                    if not global_version_dir.exists():
                        print(f"[Gradle] 保存新的 Gradle 版本到全局缓存: {version_dir.name}")
                        global_wrapper_dir.mkdir(parents=True, exist_ok=True)
                        shutil.copytree(version_dir, global_version_dir)
            except Exception as e:
                print(f"[Gradle] 保存缓存时出错（不影响构建）: {e}")
    
    def prepare_build(
        self,
        task_id: str,
        app_name: str,
        package_name: str,
        version_name: str,
        version_code: int,
        output_format: str = "apk",
        desktop_runtime: str = "electron",
        desktop_installer_mode: str = "portable",
        desktop_port: Optional[int] = None,
        task_mode: str = "convert",
        web_url: Optional[str] = None,
        screen_orientation: Optional[str] = None,
        double_click_exit: bool = True,
        status_bar_hidden: bool = False,
        status_bar_style: str = "light",
        status_bar_color: str = "#FFFFFF",
        webview_user_agent: Optional[str] = None,
        download_mode: Optional[str] = None,
        web_fill_mode: Optional[str] = None,
        permissions: Optional[list[str]] = None,
        keystore_password: Optional[str] = None,
        key_alias: Optional[str] = None,
        key_password: Optional[str] = None,
        reuse_keystore_from: Optional[str] = None,
        cdn_localize_enabled: bool = True,
        cdn_localize_urls: Optional[list[str]] = None,
        cdn_localize_preprocessed: bool = False,
    ) -> dict:
        """
        准备构建环境：
        - 输入文件在创建任务时已放入任务目录；
        - 这里主要验证输入并清理 output 目录；
        - 为任务创建独立 Gradle 缓存目录（避免并发冲突）；
        - 复用全局 Gradle wrapper 缓存（避免重复下载）
        """
        # 任务目录（已在创建任务时创建）
        task_dir = TASKS_DIR / task_id
        task_input_dir = task_dir / "input"
        task_output_dir = task_dir / "output"
        task_keystore_dir = task_dir / "keystore"
        task_gradle_dir = task_dir / "gradle"  # task 模式下的 Gradle 缓存
        ensure_task_input_assets(task_id, task_input_dir)
        
        # 验证任务目录存在
        if not task_dir.exists():
            raise FileNotFoundError(f"任务目录不存在: {task_id}")
        
        # 验证输入文件存在
        task_mode_normalized = (task_mode or "convert").strip().lower()
        if task_mode_normalized in {"convert", "desktop", "native"}:
            zip_file = task_input_dir / "project.zip"
            if not zip_file.exists():
                raise FileNotFoundError(f"ZIP 文件不存在: {zip_file}")
        elif task_mode_normalized == "html":
            if (
                (task_input_dir / "project.zip").exists()
                and (
                    not (task_input_dir / "index.html").exists()
                    or not (task_input_dir / "html_assets" / "index.html").exists()
                )
            ):
                _restore_html_task_input(task_input_dir)
            html_file = task_input_dir / "index.html"
            if not html_file.exists():
                raise FileNotFoundError(f"HTML 文件不存在: {html_file}")
        
        # task 模式：在任务目录创建 Gradle 缓存并复用全局 wrapper 缓存。
        # volume 模式：Gradle 缓存由 Docker volume 持久化，此处无需复制。
        if GRADLE_CACHE_MODE == "task":
            task_gradle_dir.mkdir(parents=True, exist_ok=True)
            self._copy_gradle_wrapper_cache(task_gradle_dir)
        
        # 清理 output 目录（重试场景需要）
        if task_output_dir.exists():
            for f in task_output_dir.iterdir():
                if f.is_file():
                    f.unlink()
        
        # 检查是否复用签名
        keystore_reused = False
        keystore_file = task_keystore_dir / "release.keystore"
        if keystore_file.exists():
            keystore_reused = True
        if reuse_keystore_from and keystore_file.exists():
            keystore_reused = True
        
        # 构建环境变量（包含任务专属目录路径）
        output_format_normalized = (output_format or "apk").strip().lower()
        if task_mode_normalized == "desktop":
            output_format_normalized = "exe"
        elif output_format_normalized not in {"apk", "aab"}:
            output_format_normalized = "apk"
        desktop_installer_mode_normalized = str(desktop_installer_mode or "portable").strip().lower()
        if desktop_installer_mode_normalized != "portable":
            desktop_installer_mode_normalized = "portable"
        desktop_runtime_normalized = str(desktop_runtime or "electron").strip().lower()
        if desktop_runtime_normalized not in {"electron", "tauri"}:
            desktop_runtime_normalized = "electron"
        desktop_port_normalized = 0
        try:
            parsed_desktop_port = int(str(desktop_port).strip()) if desktop_port is not None else 0
        except Exception:
            parsed_desktop_port = 0
        if 1024 <= parsed_desktop_port <= 65535:
            desktop_port_normalized = parsed_desktop_port
        status_bar_color_normalized = _normalize_status_bar_color(status_bar_color)
        if (
            task_mode_normalized == "convert"
            and not status_bar_hidden
            and status_bar_color_normalized.lower() in {"transparent", "@android:color/transparent"}
        ):
            status_bar_color_normalized = "#FFFFFF"
        if not status_bar_hidden:
            status_bar_style = "dark" if _is_light_color(status_bar_color_normalized) else "light"
        webview_ua = str(webview_user_agent or "").strip().lower()
        if webview_ua in {"pc", "desktop", "windows"}:
            webview_ua = "pc"
        else:
            webview_ua = "android"
        download_mode_normalized = str(download_mode or "picker").strip().lower()
        if download_mode_normalized not in {"silent", "picker"}:
            if download_mode_normalized in {"explorer", "file_manager", "resource_manager"}:
                download_mode_normalized = "picker"
            else:
                download_mode_normalized = "picker"
        web_fill_mode_normalized = str(web_fill_mode or "contain").strip().lower()
        if web_fill_mode_normalized not in {"contain", "cover"}:
            web_fill_mode_normalized = "contain"
        cdn_urls_normalized: list[str] = []
        if isinstance(cdn_localize_urls, list):
            seen_urls: set[str] = set()
            for item in cdn_localize_urls:
                text = str(item or "").strip()
                if not text or text in seen_urls:
                    continue
                seen_urls.add(text)
                cdn_urls_normalized.append(text)

        npm_cache_dir = os.getenv('NPM_CONFIG_CACHE', '').strip()
        if not npm_cache_dir:
            npm_cache_dir = str(NPM_CACHE_DIR)
        env = {
            "APP_NAME": app_name,
            "PACKAGE_NAME": package_name,
            "VERSION_NAME": version_name,
            "VERSION_CODE": str(version_code),
            "TASK_MODE": task_mode_normalized,
            "WEB_URL": web_url or "",
            # NOTE: PKCS12 (Java default) typically uses the same password for store + key.
            # If the user doesn't provide key_password explicitly, fall back to keystore_password
            # to reduce "Wrong password" signing failures.
            "KEYSTORE_PASSWORD": keystore_password or "android",
            "KEY_ALIAS": key_alias or "key0",
            "KEY_PASSWORD": key_password or (keystore_password or "android"),
            "OUTPUT_FORMAT": output_format_normalized,
            "DESKTOP_RUNTIME": desktop_runtime_normalized,
            "DESKTOP_INSTALLER_MODE": desktop_installer_mode_normalized,
            "DESKTOP_PORT": str(desktop_port_normalized),
            "SCREEN_ORIENTATION": (screen_orientation or "auto").strip().lower(),
            "DOUBLE_CLICK_EXIT": "true" if double_click_exit else "false",
            "STATUS_BAR_HIDDEN": "true" if status_bar_hidden else "false",
            "STATUS_BAR_STYLE": status_bar_style or "light",
            "STATUS_BAR_COLOR": status_bar_color_normalized,
            "WEBVIEW_UA": webview_ua,
            "DOWNLOAD_MODE": download_mode_normalized,
            "WEB_FILL_MODE": web_fill_mode_normalized,
            "CDN_LOCALIZE_ENABLED": "true" if cdn_localize_enabled else "false",
            "CDN_LOCALIZE_URLS_JSON": json.dumps(cdn_urls_normalized, ensure_ascii=False),
            "CDN_LOCALIZE_PREPROCESSED": "true" if cdn_localize_preprocessed else "false",
            # Comma-separated permissions (prefer full names, e.g. android.permission.CAMERA)
            "PERMISSIONS": ",".join([str(p).strip() for p in (permissions or []) if str(p).strip()]),
            "TASK_ID": task_id,
            # 任务专属目录（传给构建脚本使用）
            "TASK_INPUT_DIR": str(task_input_dir.resolve()),
            "TASK_OUTPUT_DIR": str(task_output_dir.resolve()),
            "TASK_KEYSTORE_DIR": str(task_keystore_dir.resolve()),
            "GRADLE_CACHE_MODE": GRADLE_CACHE_MODE,
            "GRADLE_CACHE_VOLUME": GRADLE_CACHE_VOLUME,
            "DATA_DIR": str(DATA_DIR),
            "DATA_VOLUME": DATA_VOLUME,
            "TASK_GRADLE_DIR": str(task_gradle_dir.resolve()),  # task 模式下使用
            # 标记是否复用 keystore（复用时不允许重新生成）
            "KEYSTORE_REUSED": "true" if keystore_reused else "false",
            "GRADLE_USER_HOME": str(DATA_DIR / "gradle-user-home"),
            "NPM_CONFIG_CACHE": npm_cache_dir,
        }

        env.update(env_setup.get_env_overrides())
        
        return env, task_output_dir
    
    def run_docker_build(
        self,
        task_id: str,
        env: dict,
        task_output_dir: Path,
        on_progress: Optional[Callable[[int, str], None]] = None,
        on_log: Optional[Callable[[str], None]] = None,
        on_complete: Optional[Callable[[bool, str, Optional[str]], None]] = None
    ):
        """执行 Docker 构建并实时写入日志。"""
        log_file = LOGS_DIR / f"{task_id}.log"

        def log(message: str):
            """写入单行日志并触发回调。"""
            timestamp = datetime.now().strftime("%H:%M:%S")
            log_line = f"[{timestamp}] {message}"
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(log_line + "\n")
            if on_log:
                on_log(log_line)

        process = None
        task_mode = str(env.get("TASK_MODE", "convert")).strip().lower()
        is_desktop_task = task_mode == "desktop"
        is_native_task = task_mode == "native"
        docker_image = DESKTOP_BUILDER_IMAGE if is_desktop_task else APK_BUILDER_IMAGE

        try:
            log("========== Build Task Started ==========")
            log(f"Task ID: {task_id}")
            log(f"App Name: {env.get('APP_NAME', 'N/A')}")
            log(f"Package Name: {env.get('PACKAGE_NAME', 'N/A')}")
            log(f"Version: {env.get('VERSION_NAME', 'N/A')}")
            log(f"Build Mode: {'desktop' if is_desktop_task else ('native android' if is_native_task else 'android')}")
            log(f"Build Image: {docker_image}")
            log("")

            if on_progress:
                on_progress(5, "Preparing Docker environment...")
            log("Step 0: Preparing Docker environment...")
            log(f"Task Input Dir: {env.get('TASK_INPUT_DIR', 'N/A')}")
            log(f"Task Output Dir: {env.get('TASK_OUTPUT_DIR', 'N/A')}")
            log(f"Task Keystore Dir: {env.get('TASK_KEYSTORE_DIR', 'N/A')}")

            if env.get("GRADLE_CACHE_MODE") == "task":
                gradle_mount = f"{env['TASK_GRADLE_DIR']}:/root/.gradle"
                log(f"[Gradle] Cache mode: task ({env.get('TASK_GRADLE_DIR', '')})")
            else:
                volume_name = env.get("GRADLE_CACHE_VOLUME") or GRADLE_CACHE_VOLUME
                gradle_mount = f"{volume_name}:/root/.gradle"
                log(f"[Gradle] Cache mode: volume ({volume_name})")

            task_data_volume = env.get("DATA_VOLUME") or DATA_VOLUME
            if task_data_volume:
                log(f"[Data] Mount mode: volume ({task_data_volume})")
                task_mount_args = [
                    "-v",
                    f"{task_data_volume}:/data",
                ]
                task_dir_env_args = [
                    "-e",
                    f"INPUT_DIR=/data/tasks/{task_id}/input",
                    "-e",
                    f"OUTPUT_DIR=/data/tasks/{task_id}/output",
                    "-e",
                    f"KEYSTORE_DIR=/data/tasks/{task_id}/keystore",
                ]
            else:
                log("[Data] Mount mode: bind")
                task_mount_args = [
                    "-v",
                    f"{env['TASK_INPUT_DIR']}:/workspace/input",
                    "-v",
                    f"{env['TASK_OUTPUT_DIR']}:/workspace/output",
                    "-v",
                    f"{env['TASK_KEYSTORE_DIR']}:/workspace/keystore",
                ]
                task_dir_env_args = []

            cmd = ["docker", "run", "--rm"]
            cmd += task_mount_args
            if task_data_volume and not is_desktop_task:
                template_root = _sync_android_templates_to_data_volume(log)
                if template_root:
                    cmd += ["-e", f"TEMPLATES_DIR={template_root}"]
                else:
                    log("[Templates] 数据卷中没有可用的 Android 模板")
            elif TEMPLATES_DIR and not is_desktop_task:
                cmd += ["-v", f"{TEMPLATES_DIR}:/workspace/templates:ro"]
            cmd += ["-v", gradle_mount]
            cmd += ["--memory=6g", "--cpus=4"]

            container_output_format = "exe" if is_desktop_task else env.get("OUTPUT_FORMAT", "apk")
            cmd += [
                "-e",
                f"APP_NAME={env['APP_NAME']}",
                "-e",
                f"PACKAGE_NAME={env['PACKAGE_NAME']}",
                "-e",
                f"VERSION_NAME={env['VERSION_NAME']}",
                "-e",
                f"VERSION_CODE={env['VERSION_CODE']}",
                "-e",
                f"TASK_MODE={env.get('TASK_MODE', 'convert')}",
                "-e",
                f"WEB_URL={env.get('WEB_URL', '')}",
                "-e",
                f"OUTPUT_FORMAT={container_output_format}",
                "-e",
                f"DESKTOP_RUNTIME={env.get('DESKTOP_RUNTIME', 'electron')}",
                "-e",
                f"DESKTOP_INSTALLER_MODE={env.get('DESKTOP_INSTALLER_MODE', 'portable')}",
                "-e",
                f"DESKTOP_PORT={env.get('DESKTOP_PORT', '0')}",
                "-e",
                f"SCREEN_ORIENTATION={env.get('SCREEN_ORIENTATION', 'auto')}",
                "-e",
                f"STATUS_BAR_HIDDEN={env.get('STATUS_BAR_HIDDEN', 'false')}",
                "-e",
                f"STATUS_BAR_STYLE={env.get('STATUS_BAR_STYLE', 'light')}",
                "-e",
                f"STATUS_BAR_COLOR={env.get('STATUS_BAR_COLOR', '#FFFFFF')}",
                "-e",
                f"DOWNLOAD_MODE={env.get('DOWNLOAD_MODE', 'picker')}",
                "-e",
                f"WEB_FILL_MODE={env.get('WEB_FILL_MODE', 'contain')}",
                "-e",
                f"CDN_LOCALIZE_ENABLED={env.get('CDN_LOCALIZE_ENABLED', 'true')}",
                "-e",
                f"CDN_LOCALIZE_URLS_JSON={env.get('CDN_LOCALIZE_URLS_JSON', '[]')}",
                "-e",
                f"DOUBLE_CLICK_EXIT={env.get('DOUBLE_CLICK_EXIT', 'false')}",
                "-e",
                f"PERMISSIONS={env.get('PERMISSIONS', '')}",
                "-e",
                f"KEYSTORE_PASSWORD={env['KEYSTORE_PASSWORD']}",
                "-e",
                f"KEY_ALIAS={env['KEY_ALIAS']}",
                "-e",
                f"KEY_PASSWORD={env['KEY_PASSWORD']}",
                "-e",
                f"KEYSTORE_REUSED={env['KEYSTORE_REUSED']}",
                "-e",
                "GRADLE_OPTS=-Xmx2g -Dorg.gradle.daemon=true",
            ]
            cmd += task_dir_env_args
            if task_data_volume:
                cmd += ["-e", "NPM_CONFIG_CACHE=/data/npm-cache"]
                if is_desktop_task:
                    cmd += ["-e", "ELECTRON_CACHE=/data/electron-cache"]
                    cmd += ["-e", "ELECTRON_BUILDER_CACHE=/data/electron-builder-cache"]
                else:
                    cmd += ["-e", f"PROJECT_DIR=/data/tasks/{task_id}/project"]

            gradle_dist_mirrors = os.environ.get("GRADLE_DIST_MIRRORS", "").strip()
            if gradle_dist_mirrors and not is_desktop_task:
                cmd += ["-e", f"GRADLE_DIST_MIRRORS={gradle_dist_mirrors}"]

            cmd += [docker_image]

            log(f"[DEBUG] Docker OUTPUT_FORMAT: {container_output_format}")
            process_env = os.environ.copy()
            process_env.update(env)
            process_env.update(env_setup.get_npm_config())
            process_env["PYTHONIOENCODING"] = "utf-8"
            process_env["LANG"] = "en_US.UTF-8"

            if on_progress:
                on_progress(10, "Starting Docker container...")
            log("Starting Docker container...")
            log(f"Working Directory: {APK_WORKER_DIR}")
            log("")

            process = subprocess.Popen(
                cmd,
                cwd=str(APK_WORKER_DIR),
                env=process_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=False,
            )
            self.running_processes[task_id] = process

            if is_desktop_task:
                progress_map = {
                    "Step 0": (15, "Preparing build environment..."),
                    "Step 1": (25, "Unzipping project..."),
                    "Step 2": (40, "Installing dependencies..."),
                    "Step 3": (55, "Building desktop assets..."),
                    "Step 4": (70, "Packaging desktop app..."),
                    "Step 5": (85, "Signing and organizing output..."),
                }
                success_markers = ("[DesktopBuilder] output:",)
            elif is_native_task:
                progress_map = {
                    "Step 0": (15, "Preparing build environment..."),
                    "Step 1": (25, "Unzipping native Android project..."),
                    "Step 6": (65, "Applying Android config..."),
                    "Step 7": (70, "Building release package..."),
                    "Step 8": (80, "Preparing signing keys..."),
                    "Step 9": (85, "Aligning APK / preparing AAB..."),
                    "Step 10": (90, "Signing APK / AAB..."),
                }
                success_markers = ("APK ", "AAB ")
            else:
                progress_map = {
                    "Step 0": (15, "Preparing build environment..."),
                    "Step 1": (25, "Building web project..."),
                    "Step 2": (35, "Syncing Capacitor..."),
                    "Step 3": (45, "Applying Android config..."),
                    "Step 4": (55, "Processing app icon..."),
                    "Step 5": (60, "Processing splash icon..."),
                    "Step 6": (65, "Patching Android code..."),
                    "Step 7": (70, "Building release package..."),
                    "Step 8": (80, "Preparing signing keys..."),
                    "Step 9": (85, "Aligning APK / preparing AAB..."),
                    "Step 10": (90, "Signing APK / AAB..."),
                }
                success_markers = ("APK ", "AAB ")

            build_completed = False
            stdout_iter = process.stdout if process and process.stdout is not None else []

            for raw_line in stdout_iter:
                line = _decode_subprocess_output(raw_line).strip()
                if not line:
                    continue
                if "Error response from daemon" in line or "dead or marked for removal" in line:
                    continue

                log(line)
                safe_line = line.encode("ascii", errors="replace").decode("ascii")
                print(f"[Docker] {safe_line}")

                if any(marker in line for marker in success_markers):
                    build_completed = True

                for key, (prog, msg) in progress_map.items():
                    if key in line:
                        if on_progress:
                            on_progress(prog, msg)
                        break

                if build_completed and process.poll() is not None:
                    break

            return_code = process.wait()
            log("")
            log(f"Docker process exit code: {return_code}")

            if return_code == 0:
                if env.get("GRADLE_CACHE_MODE") == "task":
                    task_gradle_dir = TASKS_DIR / task_id / "gradle"
                    if task_gradle_dir.exists():
                        self._save_gradle_wrapper_cache(task_gradle_dir)

                output_format = (container_output_format or "apk").strip().lower()
                if is_desktop_task:
                    artifact_ext = ".exe"
                    artifact_label = "EXE"
                elif output_format == "aab":
                    artifact_ext = ".aab"
                    artifact_label = "AAB"
                else:
                    artifact_ext = ".apk"
                    artifact_label = "APK"

                artifact_files = list(task_output_dir.glob(f"*{artifact_ext}"))
                output_file = _select_artifact_file(
                    artifact_files,
                    env.get("APP_NAME", ""),
                    env.get("VERSION_NAME", ""),
                    artifact_ext,
                )
                if output_file:
                    final_filename = f"{task_id}_{output_file.name}"
                    dst_file = BACKEND_OUTPUT_DIR / final_filename
                    shutil.copy2(output_file, dst_file)
                    log(f"{artifact_label} build succeeded: {output_file.name}")
                    log(f"Copied to backend output dir: {final_filename}")
                    log("========== Build Succeeded ==========")
                    if on_progress:
                        on_progress(100, "Build finished")
                    if on_complete:
                        on_complete(True, f"{artifact_label} build succeeded", final_filename)
                else:
                    log(f"Error: output {artifact_label} file not found")
                    log(f"Output directory: {task_output_dir}")
                    log("========== Build Failed ==========")
                    if on_complete:
                        on_complete(False, f"output {artifact_label} file not found", None)
            else:
                log(f"Error: Docker build failed, exit code: {return_code}")
                log("========== Build Failed ==========")
                if on_complete:
                    on_complete(False, f"Docker build failed, exit code: {return_code}", None)

        except FileNotFoundError as e:
            if getattr(e, "filename", "") == "docker":
                error_msg = (
                    "Docker command not found. Install Docker Desktop and make sure Docker CLI works, "
                    "then restart backend and try again."
                )
            else:
                error_msg = f"File not found: {str(e)}"
            log(f"Error: {error_msg}")
            log("========== Build Failed ==========")
            if on_complete:
                on_complete(False, error_msg, None)

        except Exception as e:
            error_msg = f"Build exception: {str(e)}"
            log(f"Error: {error_msg}")
            log("========== Build Failed ==========")
            if on_complete:
                on_complete(False, error_msg, None)
        finally:
            if process is not None:
                self.running_processes.pop(task_id, None)

    def run_local_build(
        self,
        task_id: str,
        env: dict,
        task_output_dir: Path,
        on_progress: Optional[Callable[[int, str], None]] = None,
        on_log: Optional[Callable[[str], None]] = None,
        on_complete: Optional[Callable[[bool, str, Optional[str]], None]] = None
    ):
        """执行本地构建模式。"""
        log_file = LOGS_DIR / f"{task_id}.log"

        def log(message: str):
            timestamp = datetime.now().strftime("%H:%M:%S")
            log_line = f"[{timestamp}] {message}"
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(log_line + "\n")
            if on_log:
                on_log(log_line)

        try:
            log("========== Local Build Started ==========")
            log(f"Task ID: {task_id}")
            log(f"App Name: {env.get('APP_NAME', 'N/A')}")
            log(f"Package Name: {env.get('PACKAGE_NAME', 'N/A')}")
            log(f"Version: {env.get('VERSION_NAME', 'N/A')}")
            log(f"Output Format: {env.get('OUTPUT_FORMAT', 'N/A')}")
            log("")

            if on_progress:
                on_progress(5, "Running local build...")

            result = run_local_build(
                env=env,
                task_output_dir=task_output_dir,
                on_progress=on_progress,
                on_log=log
            )

            output_file = result.get("output_file")
            output_format = result.get("output_format", "apk").strip().lower()
            if output_format == "aab":
                artifact_label = "AAB"
            elif output_format == "exe":
                artifact_label = "EXE"
            elif output_format == "zip":
                artifact_label = "ZIP"
            else:
                artifact_label = "APK"

            if output_file:
                final_filename = f"{task_id}_{Path(output_file).name}"
                dst_file = BACKEND_OUTPUT_DIR / final_filename
                shutil.copy2(output_file, dst_file)
                log(f"{artifact_label} build succeeded: {Path(output_file).name}")
                log(f"Copied to backend output dir: {final_filename}")
                log("========== Local Build Succeeded ==========")
                if on_progress:
                    on_progress(100, "Build finished")
                if on_complete:
                    on_complete(True, f"{artifact_label} build succeeded", final_filename)
            else:
                log(f"Error: output {artifact_label} file not found")
                log("========== Local Build Failed ==========")
                if on_complete:
                    on_complete(False, f"output {artifact_label} file not found", None)

        except Exception as e:
            error_msg = f"Local build exception: {str(e)}"
            log(f"Error: {error_msg}")
            log("========== Local Build Failed ==========")
            if on_complete:
                on_complete(False, error_msg, None)

    def run_build(
        self,
        task_id: str,
        env: dict,
        task_output_dir: Path,
        on_progress: Optional[Callable[[int, str], None]] = None,
        on_log: Optional[Callable[[str], None]] = None,
        on_complete: Optional[Callable[[bool, str, Optional[str]], None]] = None
    ):
        if self.builder_mode == "local":
            return self.run_local_build(
                task_id=task_id,
                env=env,
                task_output_dir=task_output_dir,
                on_progress=on_progress,
                on_log=on_log,
                on_complete=on_complete
            )
        return self.run_docker_build(
            task_id=task_id,
            env=env,
            task_output_dir=task_output_dir,
            on_progress=on_progress,
            on_log=on_log,
            on_complete=on_complete
        )


class BuildTaskRunner:
    """
    构建任务运行器。
    使用任务队列限制并发数，避免资源冲突
    """
    
    # 最大并发构建数（建议保持 1，避免 Gradle 缓存冲突）
    MAX_CONCURRENT_BUILDS = 1
    
    def __init__(self, tasks_db: dict, on_state_change: Optional[Callable[[bool], None]] = None):
        self.tasks_db = tasks_db
        self.builder = APKBuilder()
        self.running_tasks = {}  # 正在运行的任务
        self.canceled_tasks = set()
        self.task_queue = queue.Queue()  # 等待队列
        self.queue_lock = threading.Lock()
        self.on_state_change = on_state_change
        self._last_persist = 0.0
        self._persist_interval = 1.0
        
        # 启动工作线程（数量等于最大并发数）
        self.workers = []
        for i in range(self.MAX_CONCURRENT_BUILDS):
            worker = threading.Thread(
                target=self._worker_loop,
                daemon=True,
                name=f"BuildWorker-{i}"
            )
            worker.start()
            self.workers.append(worker)
        
        print(f"[BuildTaskRunner] 已启动 {self.MAX_CONCURRENT_BUILDS} 个构建工作线程")

    def _notify_state_change(self, force: bool = False) -> None:
        if not self.on_state_change:
            return
        now = time.monotonic()
        if force or (now - self._last_persist) >= self._persist_interval:
            self._last_persist = now
            try:
                self.on_state_change(force)
            except Exception:
                pass
    
    def start_build(self, task_id: str):
        """
        将任务加入构建队列。
        任务会按顺序执行，同时运行的任务数不超过 MAX_CONCURRENT_BUILDS。
        """
        if task_id not in self.tasks_db:
            raise ValueError(f"任务不存在: {task_id}")
        
        task = self.tasks_db[task_id]
        
        # 检查任务是否已在队列或运行中
        with self.queue_lock:
            if task_id in self.running_tasks:
                raise ValueError(f"任务已在运行中: {task_id}")
        
        # 计算队列位置
        queue_size = self.task_queue.qsize()
        running_count = len(self.running_tasks)
        
        if running_count >= self.MAX_CONCURRENT_BUILDS:
            task.message = f"排队中（前方还有 {queue_size} 个任务）"
        else:
            task.message = "准备开始构建..."
        self._notify_state_change(force=True)
        
        # 添加到队列
        self.task_queue.put(task_id)
        print(f"[BuildTaskRunner] 任务 {task_id} 已加入队列，当前队列长度: {self.task_queue.qsize()}")
    
    def _worker_loop(self):
        """工作线程循环：持续从队列取任务并执行。"""
        worker_name = threading.current_thread().name
        print(f"[{worker_name}] 工作线程已启动")
        
        while True:
            try:
                # 阻塞等待任务
                task_id = self.task_queue.get(block=True)
                
                # 检查任务是否仍然有效
                if task_id not in self.tasks_db:
                    print(f"[{worker_name}] 任务 {task_id} 已被删除，跳过处理")
                    self.task_queue.task_done()
                    continue
                
                task = self.tasks_db[task_id]
                
                # 检查任务状态（可能已被取消）
                if task.status not in ["pending", "processing"]:
                    print(f"[{worker_name}] 任务 {task_id} 状态为 {task.status}，跳过处理")
                    self.task_queue.task_done()
                    continue
                
                # 标记为运行中
                with self.queue_lock:
                    self.running_tasks[task_id] = threading.current_thread()
                
                print(f"[{worker_name}] 开始处理任务 {task_id}")
                
                try:
                    # 执行构建
                    self._run_build(task_id)
                finally:
                    # 移除运行标记
                    with self.queue_lock:
                        if task_id in self.running_tasks:
                            del self.running_tasks[task_id]
                    
                    self.task_queue.task_done()
                    print(f"[{worker_name}] 任务 {task_id} 完成")
                    
            except Exception as e:
                print(f"[{worker_name}] 工作线程异常: {e}")
    
    def get_queue_status(self) -> dict:
        """返回当前任务队列状态。"""
        return {
            "queue_size": self.task_queue.qsize(),
            "running_count": len(self.running_tasks),
            "running_tasks": list(self.running_tasks.keys()),
            "max_concurrent": self.MAX_CONCURRENT_BUILDS
        }

    def cancel_running_tasks(self, client_id: str = "") -> list[str]:
        """取消正在运行或排队中的任务。"""
        canceled: list[str] = []
        for task_id, task in list(self.tasks_db.items()):
            if client_id and task.client_id and task.client_id != client_id:
                continue
            if task.status not in ["pending", "processing"]:
                continue
            task.status = "failed"
            task.progress = 0
            task.message = "任务已取消"
            task.updated_at = datetime.now()
            canceled.append(task_id)
            self.canceled_tasks.add(task_id)
            try:
                self.builder.cancel_task(task_id)
            except Exception:
                pass
        if canceled:
            self._notify_state_change(force=True)
        return canceled

    def cancel_task(self, task_id: str, client_id: str = "") -> bool:
        """取消指定任务"""
        task = self.tasks_db.get(task_id)
        if not task:
            return False
        if client_id and task.client_id and task.client_id != client_id:
            return False
        if task.status not in ["pending", "processing"]:
            return False
        task.status = "failed"
        task.progress = 0
        task.message = "任务已取消"
        task.updated_at = datetime.now()
        self.canceled_tasks.add(task_id)
        try:
            self.builder.cancel_task(task_id)
        except Exception:
            pass
        self._notify_state_change(force=True)
        return True

    def _collect_failure_log_lines(self, task_id: str, task, max_lines: int = 240) -> list[str]:
        """收集任务失败日志，优先使用内存日志，其次回退到日志文件。"""
        lines: list[str] = []
        if hasattr(task, "logs") and isinstance(task.logs, list) and task.logs:
            lines = [str(item) for item in task.logs if str(item).strip()]
        if not lines:
            log_file = LOGS_DIR / f"{task_id}.log"
            if log_file.exists():
                try:
                    with open(log_file, "r", encoding="utf-8") as handle:
                        lines = [line.strip() for line in handle.readlines() if line.strip()]
                except Exception:
                    lines = []
        if len(lines) > max_lines:
            return lines[-max_lines:]
        return lines

    def _start_failure_diagnosis(self, task_id: str, task, failure_message: str) -> None:
        """异步启动失败日志诊断，避免阻塞任务状态回写。"""
        log_lines = self._collect_failure_log_lines(task_id, task)
        client_id = str(getattr(task, "client_id", "") or "")
        ai_runtime_config = _resolve_task_ai_runtime_config(client_id=client_id)
        ai_runtime_config, ai_cooldown_remaining = _apply_ai_diag_cooldown_to_runtime_config(
            client_id,
            ai_runtime_config,
            scope="builder_failure_diagnosis",
        )
        diagnosis_runtime = resolve_openrouter_diag_runtime_config(ai_config=ai_runtime_config)
        provider = "openrouter" if bool(diagnosis_runtime.get("enabled")) else "rule"
        model = str(diagnosis_runtime.get("model") or "") if bool(diagnosis_runtime.get("enabled")) else ""
        task.failure_diagnosis = create_running_diagnosis(
            provider=provider,
            model=model,
            analyzed_log_lines=len(log_lines),
        )
        if ai_cooldown_remaining > 0 and isinstance(task.failure_diagnosis, dict):
            task.failure_diagnosis["cooldown_rule_only"] = True
            task.failure_diagnosis["cooldown_remaining_seconds"] = ai_cooldown_remaining
            task.failure_diagnosis["cooldown_seconds"] = int(TASK_AI_DIAG_COOLDOWN_SECONDS)
        self._notify_state_change(force=True)

        def _worker() -> None:
            try:
                task_meta = {
                    "task_id": task_id,
                    "task_mode": str(getattr(task, "mode", "convert") or "convert"),
                    "output_format": str(getattr(getattr(task, "config", None), "output_format", "apk") or "apk"),
                    "app_name": str(getattr(getattr(task, "config", None), "app_name", "") or ""),
                    "package_name": str(getattr(getattr(task, "config", None), "package_name", "") or ""),
                    "client_id": client_id,
                }
                diagnosis = diagnose_build_failure(
                    log_lines=log_lines,
                    failure_message=str(failure_message or ""),
                    task_meta=task_meta,
                    ai_config=ai_runtime_config,
                )
                task.failure_diagnosis = diagnosis if isinstance(diagnosis, dict) else create_failed_diagnosis("invalid diagnosis")
                if isinstance(task.failure_diagnosis, dict):
                    diag_provider = str(task.failure_diagnosis.get("provider") or "").strip().lower()
                    diag_status = str(task.failure_diagnosis.get("status") or "").strip().lower()
                    if diag_provider and diag_provider != "rule" and diag_status == "succeeded":
                        _set_client_ai_diag_cooldown(
                            client_id,
                            ttl_seconds=TASK_AI_DIAG_COOLDOWN_SECONDS,
                            task_id=task_id,
                            source="builder_failure_diagnosis",
                        )
                    if ai_cooldown_remaining > 0:
                        task.failure_diagnosis["cooldown_rule_only"] = True
                        task.failure_diagnosis["cooldown_remaining_seconds"] = ai_cooldown_remaining
                        task.failure_diagnosis["cooldown_seconds"] = int(TASK_AI_DIAG_COOLDOWN_SECONDS)
            except Exception as exc:
                task.failure_diagnosis = create_failed_diagnosis(str(exc), analyzed_log_lines=len(log_lines))
                if ai_cooldown_remaining > 0 and isinstance(task.failure_diagnosis, dict):
                    task.failure_diagnosis["cooldown_rule_only"] = True
                    task.failure_diagnosis["cooldown_remaining_seconds"] = ai_cooldown_remaining
                    task.failure_diagnosis["cooldown_seconds"] = int(TASK_AI_DIAG_COOLDOWN_SECONDS)
            task.updated_at = datetime.now()
            self._notify_state_change(force=True)

        threading.Thread(target=_worker, daemon=True, name=f"Diag-{task_id[:8]}").start()
    
    def _run_build(self, task_id: str):
        """执行构建（在后台线程中运行）。"""
        task = self.tasks_db[task_id]
        if not isinstance(getattr(task, "failure_diagnosis", None), dict):
            task.failure_diagnosis = create_idle_diagnosis()
        # 保留创建/更新阶段日志，避免覆盖外链预处理结果
        if not isinstance(getattr(task, "logs", None), list):
            task.logs = []
        elif len(task.logs) > 500:
            task.logs = task.logs[-500:]
        if bool(getattr(task, "quick_generate", False)):
            sharedKeystorePath = TASKS_DIR.parent / "quick-generate" / "release.keystore"
            taskKeystoreDir = TASKS_DIR / task_id / "keystore"
            taskKeystorePath = taskKeystoreDir / "release.keystore"
            if sharedKeystorePath.exists() and not taskKeystorePath.exists():
                try:
                    taskKeystoreDir.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(str(sharedKeystorePath), str(taskKeystorePath))
                except Exception as e:
                    print(f"[WARN] quickGenerate 签名文件同步失败: {e}")
        
        # 调试日志：输出任务配置中的 output_format
        output_format_from_config = getattr(task.config, "output_format", "apk")
        print(f"[DEBUG] task.config.output_format = {output_format_from_config}")
        
        def on_progress(progress: int, message: str):
            task.progress = progress
            task.message = message
            task.updated_at = datetime.now()
            self._notify_state_change()
        
        def on_log(log_line: str):
            """添加日志"""
            if not hasattr(task, 'logs') or task.logs is None:
                task.logs = []
            task.logs.append(log_line)
            # 仅保留最近 500 行日志
            if len(task.logs) > 500:
                task.logs = task.logs[-500:]
            self._notify_state_change()
        
        def on_complete(success: bool, message: str, output_file: Optional[str]):
            task_mode = str(getattr(task, "mode", "convert") or "convert").strip().lower()
            task_config = getattr(task, "config", None)
            if isinstance(task_config, dict):
                raw_desktop_runtime = task_config.get("desktop_runtime")
            else:
                raw_desktop_runtime = getattr(task_config, "desktop_runtime", None)
            desktop_runtime = str(raw_desktop_runtime or "electron").strip().lower()
            if desktop_runtime in {"tauri", "rust"}:
                desktop_runtime = "tauri"
            else:
                desktop_runtime = "electron"
            defer_desktop_output_cleanup = bool(
                success
                and output_file
                and task_mode == "desktop"
                and desktop_runtime != "tauri"
            )
            auto_clean_output = bool(
                success
                and output_file
                and should_auto_clean_build_outputs()
                and task_mode != "desktop"
            )
            if task_id in self.canceled_tasks:
                task.status = "failed"
                task.progress = 0
                task.message = "任务已取消"
                task.failure_diagnosis = create_idle_diagnosis()
                task.updated_at = datetime.now()
                self.canceled_tasks.discard(task_id)
                self._notify_state_change(force=True)
                return
            if success:
                task.status = "success"
                task.progress = 100
                if auto_clean_output:
                    task.message = f"{message} (local artifact cleaned)"
                    task.desktop_output_expires_at = None
                elif defer_desktop_output_cleanup:
                    desktop_output_expires_at = datetime.now() + DESKTOP_OUTPUT_RETENTION_DELTA
                    task.desktop_output_expires_at = desktop_output_expires_at
                    expires_at_text = desktop_output_expires_at.strftime("%Y-%m-%d %H:%M:%S")
                    task.message = (
                        f"Build completed (desktop EXE can be downloaded repeatedly within {DESKTOP_OUTPUT_RETENTION_MINUTES} minutes, "
                        f"until {expires_at_text}; server will auto-delete after expiry)"
                    )
                else:
                    task.message = message
                    task.desktop_output_expires_at = None
                task.output_filename = None if auto_clean_output else output_file
                task.download_url = None if auto_clean_output else f"/api/download/{task_id}"
                task.failure_diagnosis = create_idle_diagnosis()
            else:
                task.status = "failed"
                task.message = message
                task.desktop_output_expires_at = None
                task.failure_diagnosis = create_idle_diagnosis()
            task.updated_at = datetime.now()
            self._notify_state_change(force=True)
            
            # 从运行任务中移除
            if task_id in self.running_tasks:
                del self.running_tasks[task_id]

            try:
                _silent_upload_task_assets(task_id, task)
            except Exception:
                pass
            try:
                flush_task_assets_queue()
            except Exception:
                pass
            output_info = {}
            if output_file:
                try:
                    output_path = BACKEND_OUTPUT_DIR / output_file
                    if output_path.exists():
                        output_info = {
                            "name": output_path.name,
                            "size": output_path.stat().st_size,
                        }
                except Exception:
                    output_info = {}
            try:
                report_task_status(
                    task_id,
                    task.client_id or "",
                    task.status,
                    task.updated_at.isoformat(),
                    output_info=output_info,
                )
            except Exception:
                pass

            try:
                schedule_cleanup_task_generated_artifacts(
                    task_id,
                    getattr(task, "mode", "convert"),
                    output_filename=output_file,
                    remove_backend_output=auto_clean_output,
                )
            except Exception:
                pass

            if not success:
                last_lines = []
                if hasattr(task, "logs") and task.logs:
                    last_lines = task.logs[-50:]
                else:
                    log_file = LOGS_DIR / f"{task_id}.log"
                    if log_file.exists():
                        try:
                            with open(log_file, "r", encoding="utf-8") as f:
                                all_logs = f.readlines()
                                last_lines = [line.strip() for line in all_logs[-50:]]
                        except Exception:
                            last_lines = []
                report_task_logs(task_id, task.client_id or "", "BUILD_FAILED", last_lines or [])
                self._start_failure_diagnosis(task_id, task, message)
        
        try:
            # 更新任务状态
            task.status = "processing"
            task.progress = 5
            task.message = "开始构建..."
            task.failure_diagnosis = create_idle_diagnosis()
            task.updated_at = datetime.now()
            self._notify_state_change(force=True)
            
            # 准备构建环境
            env, task_output_dir = self.builder.prepare_build(
                task_id=task_id,
                app_name=task.config.app_name,
                package_name=task.config.package_name,
                version_name=task.config.version_name,
                version_code=task.config.version_code,
                output_format=getattr(task.config, "output_format", "apk"),
                desktop_runtime=getattr(task.config, "desktop_runtime", "electron"),
                desktop_installer_mode=getattr(task.config, "desktop_installer_mode", "portable"),
                desktop_port=getattr(task.config, "desktop_port", None),
                task_mode=getattr(task, "mode", "convert"),
                web_url=getattr(task, "web_url", None),
                screen_orientation=getattr(task.config, "orientation", None),
                double_click_exit=getattr(task.config, "double_click_exit", True),
                status_bar_hidden=getattr(task.config, "status_bar_hidden", False),
                status_bar_style=getattr(task.config, "status_bar_style", "light"),
                status_bar_color=getattr(task.config, "status_bar_color", "#FFFFFF"),
                webview_user_agent=getattr(task.config, "webview_user_agent", "android"),
                download_mode=getattr(task.config, "download_mode", "picker"),
                web_fill_mode=getattr(task.config, "web_fill_mode", "contain"),
                permissions=getattr(task.config, "permissions", None),
                keystore_password=task.config.keystore_password,
                key_alias=task.config.keystore_alias,
                key_password=task.config.key_password,
                reuse_keystore_from=task.reuse_keystore_from,
                cdn_localize_enabled=getattr(task, "cdn_localize_enabled", True),
                cdn_localize_urls=getattr(task, "cdn_localize_urls", None),
                cdn_localize_preprocessed=getattr(task, "cdn_localize_preprocessed", False),
            )
            
            # 执行构建流程（本地或 Docker）
            self.builder.run_build(
                task_id=task_id,
                env=env,
                task_output_dir=task_output_dir,
                on_progress=on_progress,
                on_log=on_log,
                on_complete=on_complete
            )
            
        except Exception as e:
            on_log(f"[ERROR] 构建失败: {str(e)}")
            on_complete(False, f"构建失败: {str(e)}", None)


# 全局构建任务运行器（在 main.py 中初始化）
task_runner: Optional[BuildTaskRunner] = None


def init_task_runner(tasks_db: dict, on_state_change: Optional[Callable[[bool], None]] = None):
    """初始化并返回任务运行器。"""
    global task_runner
    task_runner = BuildTaskRunner(tasks_db, on_state_change=on_state_change)
    return task_runner


def get_task_runner() -> BuildTaskRunner:
    """获取已初始化的任务运行器。"""
    if task_runner is None:
        raise RuntimeError("任务运行器尚未初始化")
    return task_runner
