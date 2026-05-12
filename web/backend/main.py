from typing_compat import patch_typing_eval_type

patch_typing_eval_type()

from fastapi import FastAPI, UploadFile, File, HTTPException, Body, Request, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from starlette.background import BackgroundTask
from typing import List
from datetime import datetime, timedelta
from pathlib import Path, PurePosixPath
import uuid
import sys
import os
import json
import shutil
import re
import subprocess
import binascii
import struct
import zlib
import threading
import time
import urllib.request
import urllib.error
import urllib.parse
import zipfile
import hashlib
import secrets
from redis import Redis
from redis.exceptions import RedisError

from models import (
    BuildTask, BuildTaskCreate, BuildTaskListItemResponse, BuildTaskResponse,
    BuildStatus, AppConfig, UpdateTaskRequest,
    AuthRegisterRequest, AuthLoginRequest, AuthSmsSendRequest, AuthSmsLoginRequest,
    AuthSessionResponse, AuthMeResponse, AuthUserProfile
)
from builder import (
    init_task_runner,
    get_task_runner,
    APK_WORKER_DIR,
    BACKEND_OUTPUT_DIR,
    cleanup_task_generated_artifacts,
    delete_task_asset_dir,
    ensure_task_input_assets,
    get_persisted_task_asset_path,
    LOGS_DIR,
    persist_task_asset,
    restore_task_input_asset,
    should_auto_clean_build_outputs,
    TASKS_DIR,
    UPLOAD_DIR as BACKEND_UPLOAD_DIR,
)
import env_setup
from admin_client import (
    report_task_start,
    fetch_announcements,
    check_update,
    fetch_feature_flags,
    submit_feedback,
    upload_task_assets,
    flush_task_assets_queue,
    check_admin_service,
)
from system_info import get_system_info
from build_failure_diagnosis import (
    create_failed_diagnosis,
    create_idle_diagnosis,
    create_running_diagnosis,
    diagnose_build_failure,
    normalize_diag_language,
    OPENROUTER_DIAG_ENABLED,
    OPENROUTER_MODEL,
)

app = FastAPI(
    title="APK转换服务",
    description="将Google AI Studio生成的Web App转换为Android APK",
    version="1.0.0"
)

BUILDER_MODE = os.getenv("APK_BUILDER_MODE", "").strip().lower()
if not BUILDER_MODE:
    BUILDER_MODE = "local" if os.name == "nt" else "docker"
LOCAL_MODE = BUILDER_MODE == "local"
GITHUB_REPO_OWNER = (os.getenv("GITHUB_REPO_OWNER", "Jminchannel") or "Jminchannel").strip() or "Jminchannel"
GITHUB_REPO_NAME = (os.getenv("GITHUB_REPO_NAME", "ConvertAPK-Desktop") or "ConvertAPK-Desktop").strip() or "ConvertAPK-Desktop"
GITHUB_REPO_URL = f"https://github.com/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}"
GITHUB_REPO_API_URL = f"https://api.github.com/repos/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}"
try:
    GITHUB_REPO_STATS_TTL = max(int(os.getenv("GITHUB_REPO_STATS_TTL", "600") or "600"), 60)
except ValueError:
    GITHUB_REPO_STATS_TTL = 600
_github_repo_stats_lock = threading.Lock()
_github_repo_stats_cache = {
    "stars": None,
    "fetched_at": 0.0,
}
UPLOAD_MAX_SIZE_MB_DEFAULT = 200
UPLOAD_MAX_SIZE_MB_MIN = 1
UPLOAD_MAX_SIZE_MB_MAX = 10240
UPLOAD_STREAM_CHUNK_SIZE = 1024 * 1024


def _normalize_upload_max_size_mb(value) -> int:
    try:
        size_mb = int(value)
    except Exception:
        return UPLOAD_MAX_SIZE_MB_DEFAULT
    if size_mb < UPLOAD_MAX_SIZE_MB_MIN:
        return UPLOAD_MAX_SIZE_MB_MIN
    if size_mb > UPLOAD_MAX_SIZE_MB_MAX:
        return UPLOAD_MAX_SIZE_MB_MAX
    return size_mb


def _load_client_feature_flags(client_id: str | None = None) -> dict:
    sms_login_default_enabled = _env_bool(
        "CLIENT_SMS_LOGIN_ENABLED",
        default=bool(str(os.getenv("AUTH_SMS_REDIS_URL") or "").strip()),
    )
    flags = {
        "web_link_to_apk_enabled": False,
        "zip_to_desktop_enabled": False,
        "rewarded_build_ads_enabled": False,
        "client_login_enabled": True,
        "client_sms_login_enabled": sms_login_default_enabled,
        "client_register_enabled": True,
        "upload_max_size_mb": UPLOAD_MAX_SIZE_MB_DEFAULT,
        "risk_scan_block_keywords": [],
        "risk_scan_domain_keywords": [],
    }
    try:
        data = fetch_feature_flags(client_id=_normalize_client_id(client_id))
    except Exception:
        data = None
    if isinstance(data, dict):
        flags["web_link_to_apk_enabled"] = bool(data.get("web_link_to_apk_enabled"))
        flags["zip_to_desktop_enabled"] = bool(data.get("zip_to_desktop_enabled"))
        flags["rewarded_build_ads_enabled"] = bool(data.get("rewarded_build_ads_enabled"))
        if "client_login_enabled" in data:
            flags["client_login_enabled"] = bool(data.get("client_login_enabled"))
        if "client_sms_login_enabled" in data:
            flags["client_sms_login_enabled"] = bool(data.get("client_sms_login_enabled"))
        if "client_register_enabled" in data:
            flags["client_register_enabled"] = bool(data.get("client_register_enabled"))
        if "upload_max_size_mb" in data:
            flags["upload_max_size_mb"] = _normalize_upload_max_size_mb(data.get("upload_max_size_mb"))
        if "risk_scan_block_keywords" in data and isinstance(data.get("risk_scan_block_keywords"), list):
            flags["risk_scan_block_keywords"] = [
                str(item).strip()
                for item in data.get("risk_scan_block_keywords")
                if str(item or "").strip()
            ]
        if "risk_scan_domain_keywords" in data and isinstance(data.get("risk_scan_domain_keywords"), list):
            flags["risk_scan_domain_keywords"] = [
                str(item).strip()
                for item in data.get("risk_scan_domain_keywords")
                if str(item or "").strip()
            ]
    return flags


def _is_web_link_mode_enabled(client_id: str | None = None) -> bool:
    flags = _load_client_feature_flags(client_id=client_id)
    return bool(flags.get("web_link_to_apk_enabled"))


def _is_desktop_mode_enabled(client_id: str | None = None) -> bool:
    flags = _load_client_feature_flags(client_id=client_id)
    return bool(flags.get("zip_to_desktop_enabled"))


def _is_client_login_enabled(client_id: str | None = None) -> bool:
    flags = _load_client_feature_flags(client_id=client_id)
    return bool(flags.get("client_login_enabled", True))


def _is_client_register_enabled(client_id: str | None = None) -> bool:
    flags = _load_client_feature_flags(client_id=client_id)
    return bool(flags.get("client_register_enabled", True))


def _is_client_sms_login_enabled(client_id: str | None = None) -> bool:
    flags = _load_client_feature_flags(client_id=client_id)
    return bool(flags.get("client_sms_login_enabled", False))


def _get_upload_max_size_mb(client_id: str | None = None) -> int:
    flags = _load_client_feature_flags(client_id=client_id)
    return _normalize_upload_max_size_mb(flags.get("upload_max_size_mb"))


def _fetch_github_repo_stats() -> dict:
    now = time.time()
    with _github_repo_stats_lock:
        cached_stars = _github_repo_stats_cache.get("stars")
        cached_at = float(_github_repo_stats_cache.get("fetched_at") or 0.0)
    if cached_stars is not None and (now - cached_at) < GITHUB_REPO_STATS_TTL:
        return {
            "repo_url": GITHUB_REPO_URL,
            "stars": cached_stars,
            "cached": True,
            "fetched_at": cached_at,
        }

    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "ConvertAPK-Desktop",
    }
    githubApiToken = (os.getenv("GITHUB_API_TOKEN") or os.getenv("GITHUB_TOKEN") or "").strip()
    if githubApiToken:
        headers["Authorization"] = f"Bearer {githubApiToken}"

    request = urllib.request.Request(GITHUB_REPO_API_URL, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            payload = json.loads(response.read().decode("utf-8"))
        stars = int(payload.get("stargazers_count") or 0)
    except Exception:
        if cached_stars is not None:
            return {
                "repo_url": GITHUB_REPO_URL,
                "stars": cached_stars,
                "cached": True,
                "stale": True,
                "fetched_at": cached_at,
            }
        return {
            "repo_url": GITHUB_REPO_URL,
            "stars": None,
            "cached": False,
            "stale": True,
            "fetched_at": cached_at,
        }

    with _github_repo_stats_lock:
        _github_repo_stats_cache["stars"] = stars
        _github_repo_stats_cache["fetched_at"] = now
    return {
        "repo_url": GITHUB_REPO_URL,
        "stars": stars,
        "cached": False,
        "fetched_at": now,
    }


def _normalize_client_id(value: str | None) -> str:
    return str(value or "").strip()


def _require_client_id(value: str | None) -> str:
    client_id = _normalize_client_id(value)
    if not client_id:
        raise HTTPException(status_code=400, detail="client_id is required")
    return client_id


def _assert_task_owner(task: BuildTask, client_id: str) -> None:
    if not task.client_id or task.client_id != client_id:
        raise HTTPException(status_code=403, detail="无权操作此任务")

AUTH_PASSWORD_MIN_LENGTH = 6
AUTH_PASSWORD_MAX_LENGTH = 128
AUTH_PASSWORD_ITERATIONS = 240000
AUTH_SESSION_TTL_DAYS = 30
try:
    AUTH_PASSWORD_ITERATIONS = max(int(os.getenv("AUTH_PASSWORD_ITERATIONS", "240000") or "240000"), 120000)
except ValueError:
    AUTH_PASSWORD_ITERATIONS = 240000
try:
    AUTH_SESSION_TTL_DAYS = max(int(os.getenv("AUTH_SESSION_TTL_DAYS", "30") or "30"), 1)
except ValueError:
    AUTH_SESSION_TTL_DAYS = 30
AUTH_SESSION_TTL = timedelta(days=AUTH_SESSION_TTL_DAYS)
AUTH_USERS_STATE_PATH = TASKS_DIR / "users.json"
AUTH_USERS_STATE_LOCK = threading.Lock()
AUTH_SESSIONS_LOCK = threading.Lock()
AUTH_EMAIL_PATTERN = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
AUTH_PHONE_E164_PATTERN = re.compile(r"^\+[1-9]\d{7,18}$")
AUTH_SMS_CODE_PATTERN = re.compile(r"^\d{6}$")
users_db: dict[str, dict] = {}
email_to_user_id: dict[str, str] = {}
phone_to_user_id: dict[str, str] = {}
client_to_user_id: dict[str, str] = {}
github_id_to_user_id: dict[str, str] = {}
sessions_db: dict[str, dict] = {}
github_oauth_states_db: dict[str, dict] = {}
AUTH_GITHUB_STATE_LOCK = threading.Lock()
AUTH_SMS_REDIS_LOCK = threading.Lock()
AUTH_SMS_REDIS_CLIENT: Redis | None = None


def _env_bool(name: str, default: bool = False) -> bool:
    raw = str(os.getenv(name, "")).strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}

AUTH_GITHUB_CLIENT_ID = str(os.getenv("AUTH_GITHUB_CLIENT_ID") or "").strip()
AUTH_GITHUB_CLIENT_SECRET = str(os.getenv("AUTH_GITHUB_CLIENT_SECRET") or "").strip()
AUTH_GITHUB_SCOPE = str(os.getenv("AUTH_GITHUB_SCOPE") or "read:user user:email").strip() or "read:user user:email"
AUTH_GITHUB_AUTHORIZE_URL = str(os.getenv("AUTH_GITHUB_AUTHORIZE_URL") or "https://github.com/login/oauth/authorize").strip() or "https://github.com/login/oauth/authorize"
AUTH_GITHUB_TOKEN_URL = str(os.getenv("AUTH_GITHUB_TOKEN_URL") or "https://github.com/login/oauth/access_token").strip() or "https://github.com/login/oauth/access_token"
AUTH_GITHUB_USER_URL = str(os.getenv("AUTH_GITHUB_USER_URL") or "https://api.github.com/user").strip() or "https://api.github.com/user"
AUTH_GITHUB_EMAILS_URL = str(os.getenv("AUTH_GITHUB_EMAILS_URL") or "https://api.github.com/user/emails").strip() or "https://api.github.com/user/emails"
AUTH_GITHUB_CALLBACK_URL = str(os.getenv("AUTH_GITHUB_CALLBACK_URL") or "").strip()
AUTH_GITHUB_STATE_TTL_SECONDS = 600
try:
    AUTH_GITHUB_STATE_TTL_SECONDS = max(int(os.getenv("AUTH_GITHUB_STATE_TTL_SECONDS", "600") or "600"), 120)
except ValueError:
    AUTH_GITHUB_STATE_TTL_SECONDS = 600
AUTH_DEFAULT_RETURN_URL = str(os.getenv("AUTH_DEFAULT_RETURN_URL") or "http://localhost:8080/").strip() or "http://localhost:8080/"
AUTH_REDIRECT_ALLOWED_ORIGINS_RAW = str(
    os.getenv(
        "AUTH_REDIRECT_ALLOWED_ORIGINS")
    or "http://localhost:8080,http://127.0.0.1:8080,http://localhost:3000,http://127.0.0.1:3000"
).strip()
AUTH_REDIRECT_ALLOWED_ORIGINS = {
    str(item or "").strip().lower().rstrip("/")
    for item in AUTH_REDIRECT_ALLOWED_ORIGINS_RAW.split(",")
    if str(item or "").strip()
}

AUTH_SMS_REDIS_URL = str(os.getenv("AUTH_SMS_REDIS_URL") or "").strip()
AUTH_SMS_REDIS_PREFIX = str(os.getenv("AUTH_SMS_REDIS_PREFIX") or "convertapk:auth:sms:").strip() or "convertapk:auth:sms:"
AUTH_SMS_PROVIDER = str(os.getenv("AUTH_SMS_PROVIDER") or "mock").strip().lower() or "mock"
AUTH_SMS_PROVIDER_WEBHOOK_URL = str(os.getenv("AUTH_SMS_PROVIDER_WEBHOOK_URL") or "").strip()
AUTH_SMS_PROVIDER_WEBHOOK_TOKEN = str(os.getenv("AUTH_SMS_PROVIDER_WEBHOOK_TOKEN") or "").strip()
AUTH_SMS_CODE_TTL_SECONDS = 300
AUTH_SMS_RESEND_INTERVAL_SECONDS = 60
AUTH_SMS_DAILY_LIMIT = 30
AUTH_SMS_IP_HOURLY_LIMIT = 60
AUTH_SMS_VERIFY_MAX_ATTEMPTS = 8
AUTH_SMS_DEBUG_RETURN_CODE = _env_bool("AUTH_SMS_DEBUG_RETURN_CODE", default=False)
try:
    AUTH_SMS_CODE_TTL_SECONDS = max(int(os.getenv("AUTH_SMS_CODE_TTL_SECONDS", "300") or "300"), 120)
except ValueError:
    AUTH_SMS_CODE_TTL_SECONDS = 300
try:
    AUTH_SMS_RESEND_INTERVAL_SECONDS = max(int(os.getenv("AUTH_SMS_RESEND_INTERVAL_SECONDS", "60") or "60"), 15)
except ValueError:
    AUTH_SMS_RESEND_INTERVAL_SECONDS = 60
try:
    AUTH_SMS_DAILY_LIMIT = max(int(os.getenv("AUTH_SMS_DAILY_LIMIT", "30") or "30"), 1)
except ValueError:
    AUTH_SMS_DAILY_LIMIT = 30
try:
    AUTH_SMS_IP_HOURLY_LIMIT = max(int(os.getenv("AUTH_SMS_IP_HOURLY_LIMIT", "60") or "60"), 1)
except ValueError:
    AUTH_SMS_IP_HOURLY_LIMIT = 60
try:
    AUTH_SMS_VERIFY_MAX_ATTEMPTS = max(int(os.getenv("AUTH_SMS_VERIFY_MAX_ATTEMPTS", "8") or "8"), 3)
except ValueError:
    AUTH_SMS_VERIFY_MAX_ATTEMPTS = 8

MARKETPLACE_POLICY_ENABLED = _env_bool("MARKETPLACE_POLICY_ENABLED", default=True)
MARKETPLACE_POLICY_ALLOWLIST_CLIENT_IDS_RAW = str(
    os.getenv("MARKETPLACE_POLICY_ALLOWLIST_CLIENT_IDS") or ""
).strip()
MARKETPLACE_POLICY_ALLOWLIST_CLIENT_IDS = {
    str(item or "").strip().lower()
    for item in MARKETPLACE_POLICY_ALLOWLIST_CLIENT_IDS_RAW.split(",")
    if str(item or "").strip()
}
MARKETPLACE_DECLARED_USE_CASE_MIN_LENGTH = 6
MARKETPLACE_DECLARED_USE_CASE_MAX_LENGTH = 200
MARKETPLACE_BLOCK_KEYWORDS = (
    "app store",
    "application store",
    "apk store",
    "app marketplace",
    "download center",
    "应用商店",
    "应用市场",
    "软件商店",
    "软件市场",
    "应用中心",
    "下载中心",
    "应用分发",
    "分发平台",
)
RISK_REVIEW_ENABLED = _env_bool("TASK_RISK_REVIEW_ENABLED", default=True)
RISK_REVIEW_ALLOWLIST_CLIENT_IDS_RAW = str(
    os.getenv("TASK_RISK_REVIEW_ALLOWLIST_CLIENT_IDS") or ""
).strip()
RISK_REVIEW_ALLOWLIST_CLIENT_IDS = {
    str(item or "").strip().lower()
    for item in RISK_REVIEW_ALLOWLIST_CLIENT_IDS_RAW.split(",")
    if str(item or "").strip()
}
RISK_REVIEW_ADMIN_TOKEN = str(
    os.getenv("TASK_RISK_REVIEW_ADMIN_TOKEN")
    or os.getenv("ADMIN_CLIENT_TOKEN")
    or ""
).strip()
RISK_REVIEW_STATUS_NOT_REQUIRED = "not_required"
RISK_REVIEW_STATUS_PENDING = "pending"
RISK_REVIEW_STATUS_APPROVED = "approved"
RISK_REVIEW_STATUS_REJECTED = "rejected"
RISK_SCAN_BLOCK_KEYWORDS = tuple(
    dict.fromkeys(
        (
            *MARKETPLACE_BLOCK_KEYWORDS,
            "app center",
            "software store",
            "app mall",
            "distribution channel",
            "third-party app market",
            "mod apk",
            "cracked apk",
            "应用商城",
            "应用下载站",
            "渠道分发",
            "下载平台",
        )
    )
)
RISK_SCAN_DOMAIN_KEYWORDS = (
    "apkpure",
    "apkcombo",
    "apkmirror",
    "uptodown",
    "coolapk",
    "taptap",
    "wandoujia",
    "appchina",
    "yingyongbao",
    "appgallery",
    "getapps",
    "9apps",
    "apk-dl",
)


def _normalize_runtime_keywords(raw_keywords, fallback_keywords: tuple[str, ...]) -> tuple[str, ...]:
    if not isinstance(raw_keywords, (list, tuple)):
        return fallback_keywords
    seen: set[str] = set()
    normalized: list[str] = []
    for item in raw_keywords:
        keyword = str(item or "").strip()
        if not keyword:
            continue
        dedupe_key = keyword.lower()
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        normalized.append(keyword)
    if not normalized:
        return fallback_keywords
    return tuple(normalized)


def _resolve_risk_scan_keyword_sets(client_id: str | None) -> tuple[tuple[str, ...], tuple[str, ...]]:
    flags = _load_client_feature_flags(client_id=client_id)
    block_keywords = _normalize_runtime_keywords(
        flags.get("risk_scan_block_keywords"),
        RISK_SCAN_BLOCK_KEYWORDS,
    )
    domain_keywords = _normalize_runtime_keywords(
        flags.get("risk_scan_domain_keywords"),
        RISK_SCAN_DOMAIN_KEYWORDS,
    )
    return block_keywords, domain_keywords


RISK_SCAN_TEXT_EXTENSIONS = {
    ".html",
    ".htm",
    ".js",
    ".mjs",
    ".cjs",
    ".ts",
    ".tsx",
    ".jsx",
    ".vue",
    ".json",
    ".xml",
    ".txt",
}
RISK_SCAN_SKIP_DIRS = {"node_modules", ".git", "android", "__macosx", ".gradle"}
RISK_SCAN_MAX_FILE_BYTES = 2 * 1024 * 1024
RISK_SCAN_MAX_FILES_PER_ARCHIVE = 1200
RISK_SCAN_MAX_MATCHES_PER_SOURCE = 24


def _normalize_phone(value: str | None) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    compact = raw.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if compact.startswith("00"):
        compact = f"+{compact[2:]}"
    if compact.startswith("+"):
        digits = re.sub(r"\D", "", compact[1:])
        normalized = f"+{digits}" if digits else ""
    else:
        digits = re.sub(r"\D", "", compact)
        if len(digits) == 11 and digits.startswith("1"):
            normalized = f"+86{digits}"
        elif 8 <= len(digits) <= 15:
            normalized = f"+{digits}"
        else:
            normalized = ""
    if normalized and AUTH_PHONE_E164_PATTERN.fullmatch(normalized):
        return normalized
    return ""


def _validate_phone_or_raise(value: str | None) -> str:
    phone = _normalize_phone(value)
    if not phone:
        raise HTTPException(status_code=400, detail="phone format is invalid")
    return phone


def _validate_sms_code_or_raise(value: str | None) -> str:
    code = str(value or "").strip()
    if not AUTH_SMS_CODE_PATTERN.fullmatch(code):
        raise HTTPException(status_code=400, detail="sms code format is invalid")
    return code


def _normalize_declared_use_case(value: str | None) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    return re.sub(r"\s+", " ", raw)


def _validate_task_compliance_or_raise(compliance_ack: bool, declared_use_case: str) -> None:
    if not bool(compliance_ack):
        raise HTTPException(status_code=400, detail="compliance confirmation is required")
    if len(declared_use_case) < MARKETPLACE_DECLARED_USE_CASE_MIN_LENGTH:
        raise HTTPException(status_code=400, detail="declared use case is required")
    if len(declared_use_case) > MARKETPLACE_DECLARED_USE_CASE_MAX_LENGTH:
        raise HTTPException(status_code=400, detail="declared use case is too long")


def _detect_marketplace_keyword(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return ""
    compact = re.sub(r"[\s_\-]+", "", normalized)
    for keyword in MARKETPLACE_BLOCK_KEYWORDS:
        probe = str(keyword or "").strip().lower()
        if not probe:
            continue
        if probe in normalized:
            return keyword
        probe_compact = re.sub(r"[\s_\-]+", "", probe)
        if probe_compact and probe_compact in compact:
            return keyword
    return ""


def _compact_text_for_risk_scan(value: str | None) -> tuple[str, str]:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return "", ""
    collapsed = re.sub(r"\s+", " ", normalized)
    compact = re.sub(r"[\s_\-./]+", "", collapsed)
    return collapsed, compact


def _collect_risk_keyword_hits(value: str | None, keywords: tuple[str, ...], max_hits: int = 24) -> list[str]:
    normalized, compact = _compact_text_for_risk_scan(value)
    if not normalized:
        return []
    hits: list[str] = []
    seen: set[str] = set()
    for keyword in keywords:
        probe = str(keyword or "").strip().lower()
        if not probe:
            continue
        probe_compact = re.sub(r"[\s_\-./]+", "", probe)
        matched = probe in normalized or (probe_compact and probe_compact in compact)
        if not matched:
            continue
        if probe in seen:
            continue
        seen.add(probe)
        hits.append(str(keyword))
        if len(hits) >= max_hits:
            break
    return hits


def _build_risk_value_preview(value: str | None, max_len: int = 120) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    compact = re.sub(r"\s+", " ", text)
    if len(compact) <= max_len:
        return compact
    return f"{compact[:max_len]}..."


def _extract_domain_from_url(raw_url: str | None) -> str:
    value = str(raw_url or "").strip()
    if not value:
        return ""
    normalized = _normalize_external_url(value)
    if not normalized and "://" not in value:
        normalized = _normalize_external_url(f"https://{value}")
    if not normalized:
        return ""
    try:
        parsed = urllib.parse.urlsplit(normalized)
    except Exception:
        return ""
    host = str(parsed.hostname or "").strip().lower().strip(".")
    return host


def _collect_domains_from_external_items(items: list[dict]) -> list[str]:
    domains: list[str] = []
    seen: set[str] = set()
    for item in items:
        domain = _extract_domain_from_url(str(item.get("url") or ""))
        if not domain or domain in seen:
            continue
        seen.add(domain)
        domains.append(domain)
    return sorted(domains)


def _collect_risk_matches_from_text(
    text: str,
    source_label: str,
    collector: dict[str, set[str]],
    block_keywords: tuple[str, ...],
) -> None:
    if not text:
        return
    hits = _collect_risk_keyword_hits(
        text,
        block_keywords,
        max_hits=RISK_SCAN_MAX_MATCHES_PER_SOURCE,
    )
    if not hits:
        return
    slot = collector.setdefault(source_label, set())
    for keyword in hits:
        slot.add(keyword)


def _format_risk_text_matches(collector: dict[str, set[str]]) -> list[dict]:
    items: list[dict] = []
    for source, keywords in collector.items():
        ordered = sorted(str(keyword) for keyword in keywords if str(keyword).strip())
        if not ordered:
            continue
        items.append({
            "source": source,
            "keywords": ordered,
        })
    items.sort(key=lambda item: (item["source"], ",".join(item["keywords"])))
    return items


def _scan_risk_keywords_in_html(html_path: Path, block_keywords: tuple[str, ...]) -> dict:
    collector: dict[str, set[str]] = {}
    try:
        text = html_path.read_text(encoding="utf-8", errors="ignore")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read HTML file: {str(exc)}")
    _collect_risk_matches_from_text(text, html_path.name, collector, block_keywords)
    return {
        "scanned_files": 1,
        "matches": _format_risk_text_matches(collector),
    }


def _scan_risk_keywords_in_zip(zip_path: Path, block_keywords: tuple[str, ...]) -> dict:
    collector: dict[str, set[str]] = {}
    scanned_files = 0
    try:
        with zipfile.ZipFile(zip_path, "r") as archive:
            for info, parts in _iter_zip_entries(archive):
                if scanned_files >= RISK_SCAN_MAX_FILES_PER_ARCHIVE:
                    break
                lower_parts = [part.lower() for part in parts]
                if any(part in RISK_SCAN_SKIP_DIRS for part in lower_parts):
                    continue
                suffix = PurePosixPath(parts[-1]).suffix.lower()
                if suffix not in RISK_SCAN_TEXT_EXTENSIONS:
                    continue
                file_size = int(info.file_size or 0)
                if file_size <= 0 or file_size > RISK_SCAN_MAX_FILE_BYTES:
                    continue
                try:
                    with archive.open(info, "r") as source:
                        content = source.read(RISK_SCAN_MAX_FILE_BYTES + 1)
                    if len(content) > RISK_SCAN_MAX_FILE_BYTES:
                        continue
                    text = content.decode("utf-8", errors="ignore")
                except Exception:
                    continue
                scanned_files += 1
                file_label = str(PurePosixPath(*parts))
                _collect_risk_matches_from_text(text, file_label, collector, block_keywords)
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="ZIP format is invalid, please upload again")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to scan ZIP text risk: {str(exc)}")
    return {
        "scanned_files": scanned_files,
        "matches": _format_risk_text_matches(collector),
    }


def _scan_task_risk_inputs(
    *,
    client_id: str | None,
    app_name: str | None,
    package_name: str | None,
    declared_use_case: str,
    web_url: str | None,
    zip_path: Path | None = None,
    html_path: Path | None = None,
) -> dict:
    block_keywords, domain_keywords = _resolve_risk_scan_keyword_sets(client_id)
    field_hits: list[dict] = []
    text_hits: list[dict] = []
    domain_hits: list[dict] = []
    scan_errors: list[str] = []
    scanned_text_files = 0
    external_link_items: list[dict] = []

    field_candidates = [
        ("app_name", app_name),
        ("package_name", package_name),
        ("declared_use_case", declared_use_case),
    ]
    if web_url:
        field_candidates.append(("web_url", web_url))
    for field_name, value in field_candidates:
        hits = _collect_risk_keyword_hits(value, block_keywords)
        for keyword in hits:
            field_hits.append({
                "field": field_name,
                "keyword": keyword,
                "sample": _build_risk_value_preview(value),
            })

    if zip_path and zip_path.exists():
        try:
            text_result = _scan_risk_keywords_in_zip(zip_path, block_keywords)
            scanned_text_files += int(text_result.get("scanned_files") or 0)
            text_hits.extend(list(text_result.get("matches") or []))
        except HTTPException as exc:
            scan_errors.append(f"text_scan_zip_failed:{str(exc.detail or exc)}")
        except Exception as exc:
            scan_errors.append(f"text_scan_zip_failed:{str(exc)}")
        try:
            external_link_items = _scan_external_links_in_zip(zip_path)
        except HTTPException as exc:
            scan_errors.append(f"external_links_zip_failed:{str(exc.detail or exc)}")
        except Exception as exc:
            scan_errors.append(f"external_links_zip_failed:{str(exc)}")
    elif html_path and html_path.exists():
        try:
            text_result = _scan_risk_keywords_in_html(html_path, block_keywords)
            scanned_text_files += int(text_result.get("scanned_files") or 0)
            text_hits.extend(list(text_result.get("matches") or []))
        except HTTPException as exc:
            scan_errors.append(f"text_scan_html_failed:{str(exc.detail or exc)}")
        except Exception as exc:
            scan_errors.append(f"text_scan_html_failed:{str(exc)}")
        try:
            external_link_items = _scan_external_links_in_html(html_path)
        except HTTPException as exc:
            scan_errors.append(f"external_links_html_failed:{str(exc.detail or exc)}")
        except Exception as exc:
            scan_errors.append(f"external_links_html_failed:{str(exc)}")

    external_domains = _collect_domains_from_external_items(external_link_items)
    web_domain = _extract_domain_from_url(web_url)
    if web_domain and web_domain not in external_domains:
        external_domains.append(web_domain)
        external_domains.sort()

    for domain in external_domains:
        hits = _collect_risk_keyword_hits(domain, domain_keywords, max_hits=6)
        for keyword in hits:
            domain_hits.append({
                "domain": domain,
                "keyword": keyword,
            })

    risk_hit_count = len(field_hits) + len(text_hits) + len(domain_hits)
    high_risk = risk_hit_count > 0 or bool(scan_errors)
    return {
        "risk_level": "high" if high_risk else "normal",
        "hit_count": risk_hit_count,
        "field_hits": field_hits[:128],
        "html_hits": text_hits[:128],
        "domain_hits": domain_hits[:128],
        "external_domains": external_domains[:256],
        "external_link_count": len(external_link_items),
        "external_links_preview": [
            str(item.get("url") or "")
            for item in external_link_items[:40]
            if str(item.get("url") or "").strip()
        ],
        "scanned_text_files": scanned_text_files,
        "scan_errors": scan_errors[:32],
        "scanned_at": datetime.now().isoformat(),
    }


def _is_marketplace_policy_allowlisted(client_id: str | None) -> bool:
    normalized_client_id = str(client_id or "").strip().lower()
    if not normalized_client_id:
        return False
    return normalized_client_id in MARKETPLACE_POLICY_ALLOWLIST_CLIENT_IDS


def _is_risk_review_allowlisted(client_id: str | None) -> bool:
    normalized_client_id = str(client_id or "").strip().lower()
    if not normalized_client_id:
        return False
    if normalized_client_id in RISK_REVIEW_ALLOWLIST_CLIENT_IDS:
        return True
    return _is_marketplace_policy_allowlisted(normalized_client_id)


def _requires_risk_review(client_id: str | None, risk_scan: dict) -> bool:
    if not RISK_REVIEW_ENABLED:
        return False
    if str(risk_scan.get("risk_level") or "").strip().lower() != "high":
        return False
    if _is_risk_review_allowlisted(client_id):
        return False
    return True


def _is_task_review_approved(task: BuildTask) -> bool:
    if not bool(getattr(task, "review_required", False)):
        return True
    review_status = str(getattr(task, "review_status", "") or "").strip().lower()
    return review_status == RISK_REVIEW_STATUS_APPROVED


def _datetime_to_iso_or_none(value) -> str | None:
    if isinstance(value, datetime):
        return value.isoformat()
    return None


def _build_task_risk_sync_meta(task: BuildTask) -> dict:
    risk_scan = getattr(task, "risk_scan", {})
    if not isinstance(risk_scan, dict):
        risk_scan = {}
    return {
        "risk_level": str(getattr(task, "risk_level", "normal") or "normal"),
        "review_required": bool(getattr(task, "review_required", False)),
        "review_status": str(getattr(task, "review_status", "") or RISK_REVIEW_STATUS_NOT_REQUIRED),
        "review_requested_at": _datetime_to_iso_or_none(getattr(task, "review_requested_at", None)),
        "review_decision_at": _datetime_to_iso_or_none(getattr(task, "review_decision_at", None)),
        "review_decision_by": str(getattr(task, "review_decision_by", "") or ""),
        "review_note": str(getattr(task, "review_note", "") or ""),
        "risk_scan": risk_scan,
    }


def _extract_bearer_token(raw_value: str | None) -> str:
    header = str(raw_value or "").strip()
    if not header:
        return ""
    if not header.lower().startswith("bearer "):
        return ""
    return header[7:].strip()


def _require_risk_review_admin_access(request: Request) -> str:
    expected_token = RISK_REVIEW_ADMIN_TOKEN
    if not expected_token:
        raise HTTPException(status_code=503, detail="risk review admin token is not configured")
    raw_token = str(request.headers.get("X-Admin-Token") or "").strip()
    if not raw_token:
        raw_token = _extract_bearer_token(request.headers.get("Authorization"))
    if not raw_token:
        raise HTTPException(status_code=401, detail="risk review admin token is required")
    if not secrets.compare_digest(raw_token, expected_token):
        raise HTTPException(status_code=403, detail="risk review admin token is invalid")
    return "admin"


def _sync_task_risk_review_to_admin(task_id: str, task: BuildTask) -> None:
    try:
        config_data = task.config.model_dump() if hasattr(task.config, "model_dump") else task.config.dict()
    except Exception:
        config_data = {}
    config_data["build_type"] = task.mode
    config_data["task_mode"] = task.mode
    if task.mode == "web" and task.web_url:
        config_data["web_url"] = task.web_url
    risk_meta = _build_task_risk_sync_meta(task)
    config_data.update(risk_meta)

    risk_scan = risk_meta.get("risk_scan", {}) if isinstance(risk_meta.get("risk_scan"), dict) else {}
    zip_info = {
        "build_type": task.mode,
        "risk_level": risk_meta.get("risk_level", "normal"),
        "review_required": bool(risk_meta.get("review_required")),
        "review_status": str(risk_meta.get("review_status") or RISK_REVIEW_STATUS_NOT_REQUIRED),
        "risk_hit_count": int(risk_scan.get("hit_count") or 0),
    }

    task_input_dir = TASKS_DIR / task_id / "input"
    ensure_task_input_assets(task_id, task_input_dir)
    persisted_zip_path = get_persisted_task_asset_path(task_id, "project.zip")
    persisted_html_path = get_persisted_task_asset_path(task_id, "index.html")
    zip_path = persisted_zip_path if persisted_zip_path.exists() else _resolve_task_asset_path(task_id, "project.zip")
    html_path = persisted_html_path if persisted_html_path.exists() else _resolve_task_asset_path(task_id, "index.html")
    icon_path = _resolve_task_asset_path(task_id, "logo.png")
    if zip_path.exists():
        zip_info.update({
            "name": zip_path.name,
            "size": zip_path.stat().st_size,
        })

    upload_task_assets(
        task_id,
        task.client_id or "",
        task.updated_at.isoformat(),
        zip_info,
        config_data,
        zip_path=str(zip_path) if zip_path.exists() else None,
        html_path=str(html_path) if html_path.exists() else None,
        icon_path=str(icon_path) if icon_path.exists() else None,
        keystore_path=None,
        keystore_info={},
    )
    flush_task_assets_queue()


def _enforce_marketplace_policy_or_raise(
    *,
    client_id: str,
    app_name: str | None,
    package_name: str | None,
    declared_use_case: str,
    web_url: str | None,
) -> None:
    if not MARKETPLACE_POLICY_ENABLED:
        return
    if _is_marketplace_policy_allowlisted(client_id):
        return

    field_candidates = [
        ("app_name", app_name),
        ("package_name", package_name),
        ("declared_use_case", declared_use_case),
    ]
    if web_url:
        field_candidates.append(("web_url", web_url))

    for field_name, value in field_candidates:
        matched_keyword = _detect_marketplace_keyword(value)
        if matched_keyword:
            raise HTTPException(
                status_code=403,
                detail=f"task blocked by policy: suspected marketplace app ({field_name}:{matched_keyword})",
            )


def _extract_request_ip(request: Request | None) -> str:
    if request is None:
        return "unknown"
    forwarded_for = str(request.headers.get("X-Forwarded-For") or "").strip()
    if forwarded_for:
        candidate = str(forwarded_for.split(",")[0]).strip()
        if candidate:
            return candidate
    if request.client and request.client.host:
        return str(request.client.host).strip() or "unknown"
    return "unknown"


def _sms_redis_key(suffix: str) -> str:
    return f"{AUTH_SMS_REDIS_PREFIX}{suffix}"


def _get_sms_redis_client() -> Redis:
    global AUTH_SMS_REDIS_CLIENT
    if not AUTH_SMS_REDIS_URL:
        raise HTTPException(status_code=503, detail="sms login unavailable")
    if AUTH_SMS_REDIS_CLIENT is not None:
        return AUTH_SMS_REDIS_CLIENT
    with AUTH_SMS_REDIS_LOCK:
        if AUTH_SMS_REDIS_CLIENT is not None:
            return AUTH_SMS_REDIS_CLIENT
        try:
            client = Redis.from_url(
                AUTH_SMS_REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
                health_check_interval=30,
            )
            client.ping()
        except Exception:
            raise HTTPException(status_code=503, detail="sms login unavailable")
        AUTH_SMS_REDIS_CLIENT = client
        return client


def _hash_sms_code(code: str, salt_hex: str) -> str:
    salt = bytes.fromhex(salt_hex)
    digest = hashlib.pbkdf2_hmac("sha256", code.encode("utf-8"), salt, AUTH_PASSWORD_ITERATIONS, dklen=32)
    return digest.hex()


def _check_and_incr_sms_rate_limit(redis_client: Redis, key: str, window_seconds: int, limit: int, detail: str) -> None:
    count = int(redis_client.incr(key))
    if count <= 1:
        redis_client.expire(key, int(window_seconds))
    if count > int(limit):
        raise HTTPException(status_code=429, detail=detail)


def _send_sms_code_via_provider(phone: str, code: str) -> tuple[bool, str]:
    provider = str(AUTH_SMS_PROVIDER or "mock").strip().lower()
    if provider == "mock":
        print(f"[AUTH SMS] {phone} code={code}")
        return True, ""
    if provider == "webhook":
        if not AUTH_SMS_PROVIDER_WEBHOOK_URL:
            return False, "sms provider webhook is not configured"
        headers = {"Content-Type": "application/json"}
        if AUTH_SMS_PROVIDER_WEBHOOK_TOKEN:
            headers["Authorization"] = f"Bearer {AUTH_SMS_PROVIDER_WEBHOOK_TOKEN}"
        payload = {
            "phone": phone,
            "code": code,
            "scene": "login",
            "ttl_seconds": AUTH_SMS_CODE_TTL_SECONDS,
        }
        req = urllib.request.Request(
            AUTH_SMS_PROVIDER_WEBHOOK_URL,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            method="POST",
            headers=headers,
        )
        try:
            with urllib.request.urlopen(req, timeout=8) as response:
                if 200 <= int(response.status) < 300:
                    return True, ""
                return False, f"provider http status {response.status}"
        except urllib.error.HTTPError as exc:
            return False, f"provider http status {exc.code}"
        except Exception as exc:
            return False, str(exc)
    return False, f"unsupported sms provider: {provider}"


def _normalize_email(value: str | None) -> str:
    return str(value or "").strip().lower()


def _validate_email_or_raise(value: str | None) -> str:
    email = _normalize_email(value)
    if not email:
        raise HTTPException(status_code=400, detail="email is required")
    if len(email) > 254:
        raise HTTPException(status_code=400, detail="email is too long")
    if not AUTH_EMAIL_PATTERN.fullmatch(email):
        raise HTTPException(status_code=400, detail="email format is invalid")
    return email


def _validate_password_or_raise(value: str | None) -> str:
    password = str(value or "")
    if len(password) < AUTH_PASSWORD_MIN_LENGTH:
        raise HTTPException(status_code=400, detail=f"password must be at least {AUTH_PASSWORD_MIN_LENGTH} characters")
    if len(password) > AUTH_PASSWORD_MAX_LENGTH:
        raise HTTPException(status_code=400, detail=f"password must be at most {AUTH_PASSWORD_MAX_LENGTH} characters")
    return password


def _hash_password(password: str, salt_hex: str) -> str:
    salt = bytes.fromhex(salt_hex)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, AUTH_PASSWORD_ITERATIONS, dklen=32)
    return digest.hex()


def _verify_password(password: str, salt_hex: str, expected_hash: str) -> bool:
    actual_hash = _hash_password(password, salt_hex)
    return secrets.compare_digest(actual_hash, str(expected_hash or ""))


def _is_github_oauth_enabled() -> bool:
    return bool(AUTH_GITHUB_CLIENT_ID and AUTH_GITHUB_CLIENT_SECRET)


def _normalize_github_id(value: str | int | None) -> str:
    return str(value or "").strip()


def _normalize_auth_provider(value: str | None) -> str:
    provider = str(value or "").strip().lower()
    if provider in {"github", "local", "sms"}:
        return provider
    return "local"


def _normalize_return_url(value: str | None) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        parsed = urllib.parse.urlsplit(raw)
    except Exception:
        return ""
    scheme = str(parsed.scheme or "").strip().lower()
    netloc = str(parsed.netloc or "").strip()
    if scheme not in {"http", "https"} or not netloc:
        return ""
    origin = f"{scheme}://{netloc}".rstrip("/").lower()
    if AUTH_REDIRECT_ALLOWED_ORIGINS and origin not in AUTH_REDIRECT_ALLOWED_ORIGINS:
        return ""
    path = parsed.path or "/"
    return urllib.parse.urlunsplit((scheme, netloc, path, parsed.query, parsed.fragment))


def _build_fragment_redirect_url(base_url: str, fragment_values: dict[str, str]) -> str:
    fallback_url = _normalize_return_url(AUTH_DEFAULT_RETURN_URL) or "http://localhost:8080/"
    target_url = _normalize_return_url(base_url) or fallback_url
    parsed = urllib.parse.urlsplit(target_url)
    fragment_pairs = urllib.parse.parse_qsl(parsed.fragment, keep_blank_values=True)
    fragment_map = {str(key): str(value) for key, value in fragment_pairs}
    for key, value in fragment_values.items():
        normalized_key = str(key or "").strip()
        if not normalized_key:
            continue
        normalized_value = str(value or "").strip()
        if not normalized_value:
            continue
        fragment_map[normalized_key] = normalized_value
    fragment = urllib.parse.urlencode(fragment_map)
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, parsed.query, fragment))


def _build_github_callback_redirect(return_url: str, token: str | None = None, error: str | None = None) -> str:
    values = {"auth_provider": "github"}
    if token:
        values["auth_token"] = str(token or "").strip()
    if error:
        values["auth_error"] = str(error or "").strip()
    return _build_fragment_redirect_url(return_url, values)


def _prune_github_oauth_states_locked() -> None:
    now = time.time()
    expired = [
        state
        for state, item in github_oauth_states_db.items()
        if (now - float(item.get("created_at") or 0.0)) > AUTH_GITHUB_STATE_TTL_SECONDS
    ]
    for state in expired:
        github_oauth_states_db.pop(state, None)


def _save_github_oauth_state(client_id: str, return_url: str) -> str:
    state = secrets.token_urlsafe(32)
    with AUTH_GITHUB_STATE_LOCK:
        _prune_github_oauth_states_locked()
        github_oauth_states_db[state] = {
            "client_id": _require_client_id(client_id),
            "return_url": _normalize_return_url(return_url) or _normalize_return_url(AUTH_DEFAULT_RETURN_URL),
            "created_at": time.time(),
        }
    return state


def _pop_github_oauth_state(state: str | None) -> dict | None:
    normalized_state = str(state or "").strip()
    if not normalized_state:
        return None
    with AUTH_GITHUB_STATE_LOCK:
        _prune_github_oauth_states_locked()
        return github_oauth_states_db.pop(normalized_state, None)


def _build_github_oauth_headers(access_token: str | None = None) -> dict:
    headers = {
        "Accept": "application/json",
        "User-Agent": "ConvertAPK-Desktop",
    }
    normalized_access_token = str(access_token or "").strip()
    if normalized_access_token:
        headers["Authorization"] = f"Bearer {normalized_access_token}"
    return headers


def _http_json_request(url: str, method: str = "GET", headers: dict | None = None, body: bytes | None = None):
    request = urllib.request.Request(url=url, data=body, headers=headers or {}, method=method)
    with urllib.request.urlopen(request, timeout=12) as response:
        payload = response.read().decode("utf-8", errors="ignore")
    try:
        data = json.loads(payload or "{}")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"github response parse failed: {str(exc)}")
    return data


def _exchange_github_oauth_code(code: str, state: str) -> str:
    if not _is_github_oauth_enabled():
        raise HTTPException(status_code=503, detail="github oauth is not configured")
    payload = {
        "client_id": AUTH_GITHUB_CLIENT_ID,
        "client_secret": AUTH_GITHUB_CLIENT_SECRET,
        "code": str(code or "").strip(),
        "state": str(state or "").strip(),
    }
    if AUTH_GITHUB_CALLBACK_URL:
        payload["redirect_uri"] = AUTH_GITHUB_CALLBACK_URL
    body = urllib.parse.urlencode(payload).encode("utf-8")
    try:
        raw_data = _http_json_request(
            url=AUTH_GITHUB_TOKEN_URL,
            method="POST",
            headers=_build_github_oauth_headers(),
            body=body,
        )
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise HTTPException(status_code=502, detail=f"github token exchange failed: {detail or str(exc)}")
    if not isinstance(raw_data, dict):
        raise HTTPException(status_code=502, detail="github token response is invalid")
    token = str(raw_data.get("access_token") or "").strip()
    if not token:
        error_message = str(raw_data.get("error_description") or raw_data.get("error") or "").strip()
        raise HTTPException(status_code=502, detail=f"github token exchange failed: {error_message or 'empty token'}")
    return token


def _pick_github_email(emails_payload) -> str:
    if not isinstance(emails_payload, list):
        return ""
    verified_primary = ""
    verified_backup = ""
    fallback = ""
    for item in emails_payload:
        if not isinstance(item, dict):
            continue
        email = _normalize_email(item.get("email"))
        if not email:
            continue
        verified = bool(item.get("verified"))
        primary = bool(item.get("primary"))
        if verified and primary:
            verified_primary = email
            break
        if verified and not verified_backup:
            verified_backup = email
        if primary and not fallback:
            fallback = email
        if not fallback:
            fallback = email
    if verified_primary:
        return verified_primary
    if verified_backup:
        return verified_backup
    return fallback


def _fetch_github_identity(access_token: str) -> dict:
    token = str(access_token or "").strip()
    if not token:
        raise HTTPException(status_code=400, detail="github access token is required")
    try:
        raw_user_data = _http_json_request(
            url=AUTH_GITHUB_USER_URL,
            method="GET",
            headers=_build_github_oauth_headers(token),
        )
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise HTTPException(status_code=502, detail=f"github user fetch failed: {detail or str(exc)}")
    if not isinstance(raw_user_data, dict):
        raise HTTPException(status_code=502, detail="github user response is invalid")
    github_id = _normalize_github_id(raw_user_data.get("id"))
    github_login = str(raw_user_data.get("login") or "").strip()
    email = _normalize_email(raw_user_data.get("email"))
    if not github_id:
        raise HTTPException(status_code=502, detail="github user id is missing")
    if not email:
        try:
            emails_data = _http_json_request(
                url=AUTH_GITHUB_EMAILS_URL,
                method="GET",
                headers=_build_github_oauth_headers(token),
            )
            email = _pick_github_email(emails_data if isinstance(emails_data, list) else [])
        except HTTPException:
            email = ""
        except urllib.error.HTTPError:
            email = ""
    if not email:
        email = f"github_{github_id}@users.noreply.github.local"
    return {
        "github_id": github_id,
        "github_login": github_login,
        "email": email,
    }


def _upsert_user_by_github_identity(identity: dict) -> tuple[str, dict]:
    github_id = _normalize_github_id(identity.get("github_id"))
    github_login = str(identity.get("github_login") or "").strip()
    email = _normalize_email(identity.get("email"))
    if not github_id:
        raise HTTPException(status_code=400, detail="github_id is required")
    if not email:
        raise HTTPException(status_code=400, detail="email is required")

    user_id = github_id_to_user_id.get(github_id)
    user = users_db.get(user_id) if user_id else None
    if not user:
        user_id_by_email = email_to_user_id.get(email)
        if user_id_by_email:
            user = users_db.get(user_id_by_email)
            user_id = user_id_by_email
    if not user:
        user_id = f"user_{uuid.uuid4().hex}"
        now_iso = datetime.now().isoformat()
        random_password = secrets.token_urlsafe(32)
        salt_hex = secrets.token_hex(16)
        user = {
            "id": user_id,
            "email": email,
            "phone": "",
            "password_salt": salt_hex,
            "password_hash": _hash_password(random_password, salt_hex),
            "client_ids": [],
            "created_at": now_iso,
            "updated_at": now_iso,
            "last_login_at": now_iso,
            "auth_provider": "github",
            "github_id": github_id,
            "github_login": github_login,
        }
    existing_github_id = _normalize_github_id(user.get("github_id"))
    if existing_github_id and existing_github_id != github_id:
        raise HTTPException(status_code=409, detail="github account conflict")
    now_iso = datetime.now().isoformat()
    user["email"] = email
    user["github_id"] = github_id
    user["github_login"] = github_login
    user["updated_at"] = now_iso
    user["last_login_at"] = now_iso
    user["auth_provider"] = "github"
    users_db[user_id] = user
    _rebuild_auth_indexes()
    return user_id, user


def _upsert_user_by_phone(phone: str) -> tuple[str, dict]:
    normalized_phone = _validate_phone_or_raise(phone)
    user_id = phone_to_user_id.get(normalized_phone)
    user = users_db.get(user_id) if user_id else None
    now_iso = datetime.now().isoformat()
    if not user:
        user_id = f"user_{uuid.uuid4().hex}"
        random_password = secrets.token_urlsafe(32)
        salt_hex = secrets.token_hex(16)
        user = {
            "id": user_id,
            "email": "",
            "phone": normalized_phone,
            "password_salt": salt_hex,
            "password_hash": _hash_password(random_password, salt_hex),
            "client_ids": [],
            "created_at": now_iso,
            "updated_at": now_iso,
            "last_login_at": now_iso,
            "auth_provider": "sms",
            "github_id": "",
            "github_login": "",
        }
    user["phone"] = normalized_phone
    provider = _normalize_auth_provider(user.get("auth_provider"))
    if provider in {"local", "sms"} and not _normalize_email(user.get("email")) and not _normalize_github_id(user.get("github_id")):
        user["auth_provider"] = "sms"
    user["updated_at"] = now_iso
    user["last_login_at"] = now_iso
    users_db[user_id] = user
    _rebuild_auth_indexes()
    return user_id, user


def _parse_iso_datetime(value, default_value: datetime | None = None) -> datetime:
    if isinstance(value, datetime):
        return value
    raw = str(value or "").strip()
    if raw:
        try:
            return datetime.fromisoformat(raw)
        except Exception:
            pass
    return default_value or datetime.now()


def _serialize_auth_user(user: dict) -> dict:
    return {
        "id": str(user.get("id") or "").strip(),
        "email": _normalize_email(user.get("email")),
        "phone": _normalize_phone(user.get("phone")),
        "auth_provider": _normalize_auth_provider(user.get("auth_provider")),
        "github_id": _normalize_github_id(user.get("github_id")),
        "github_login": str(user.get("github_login") or "").strip(),
        "password_salt": str(user.get("password_salt") or "").strip(),
        "password_hash": str(user.get("password_hash") or "").strip(),
        "client_ids": [str(item).strip() for item in list(user.get("client_ids") or []) if str(item or "").strip()],
        "created_at": _parse_iso_datetime(user.get("created_at")).isoformat(),
        "updated_at": _parse_iso_datetime(user.get("updated_at")).isoformat(),
        "last_login_at": _parse_iso_datetime(user.get("last_login_at")).isoformat() if user.get("last_login_at") else None,
    }


def _user_to_profile(user: dict) -> AuthUserProfile:
    email = _normalize_email(user.get("email"))
    phone = _normalize_phone(user.get("phone"))
    return AuthUserProfile(
        id=str(user.get("id") or "").strip(),
        email=email or None,
        phone=phone or None,
        auth_provider=_normalize_auth_provider(user.get("auth_provider")),
        github_id=_normalize_github_id(user.get("github_id")) or None,
        github_login=str(user.get("github_login") or "").strip() or None,
        client_ids=[str(item).strip() for item in list(user.get("client_ids") or []) if str(item or "").strip()],
        created_at=_parse_iso_datetime(user.get("created_at")),
        updated_at=_parse_iso_datetime(user.get("updated_at")),
        last_login_at=_parse_iso_datetime(user.get("last_login_at")) if user.get("last_login_at") else None,
    )


def _rebuild_auth_indexes() -> None:
    email_to_user_id.clear()
    phone_to_user_id.clear()
    client_to_user_id.clear()
    github_id_to_user_id.clear()
    for user_id, user in users_db.items():
        normalized_user_id = str(user_id or "").strip()
        if not normalized_user_id:
            continue
        user["auth_provider"] = _normalize_auth_provider(user.get("auth_provider"))
        email = _normalize_email(user.get("email"))
        if email and email not in email_to_user_id:
            email_to_user_id[email] = normalized_user_id
        phone = _normalize_phone(user.get("phone"))
        user["phone"] = phone
        if phone and phone not in phone_to_user_id:
            phone_to_user_id[phone] = normalized_user_id
        github_id = _normalize_github_id(user.get("github_id"))
        user["github_id"] = github_id
        user["github_login"] = str(user.get("github_login") or "").strip()
        if github_id and github_id not in github_id_to_user_id:
            github_id_to_user_id[github_id] = normalized_user_id
        client_ids = [str(item).strip() for item in list(user.get("client_ids") or []) if str(item or "").strip()]
        user["client_ids"] = client_ids
        for client_id in client_ids:
            if client_id not in client_to_user_id:
                client_to_user_id[client_id] = normalized_user_id


def _persist_auth_users_db() -> None:
    AUTH_USERS_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with AUTH_USERS_STATE_LOCK:
        payload = [_serialize_auth_user(user) for user in users_db.values()]
        tmp_path = AUTH_USERS_STATE_PATH.with_suffix(".json.tmp")
        tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp_path.replace(AUTH_USERS_STATE_PATH)


def _load_auth_users_db() -> None:
    if not AUTH_USERS_STATE_PATH.exists():
        return
    try:
        data = json.loads(AUTH_USERS_STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return
    if not isinstance(data, list):
        return
    for item in data:
        if not isinstance(item, dict):
            continue
        user_id = str(item.get("id") or "").strip()
        email = _normalize_email(item.get("email"))
        phone = _normalize_phone(item.get("phone"))
        auth_provider = _normalize_auth_provider(item.get("auth_provider"))
        github_id = _normalize_github_id(item.get("github_id"))
        github_login = str(item.get("github_login") or "").strip()
        password_salt = str(item.get("password_salt") or "").strip()
        password_hash = str(item.get("password_hash") or "").strip()
        if not user_id or (not email and not phone):
            continue
        users_db[user_id] = {
            "id": user_id,
            "email": email,
            "phone": phone,
            "auth_provider": auth_provider,
            "github_id": github_id,
            "github_login": github_login,
            "password_salt": password_salt,
            "password_hash": password_hash,
            "client_ids": [str(client).strip() for client in list(item.get("client_ids") or []) if str(client or "").strip()],
            "created_at": _parse_iso_datetime(item.get("created_at")).isoformat(),
            "updated_at": _parse_iso_datetime(item.get("updated_at")).isoformat(),
            "last_login_at": _parse_iso_datetime(item.get("last_login_at")).isoformat() if item.get("last_login_at") else None,
        }
    _rebuild_auth_indexes()


def _bind_client_to_user(user_id: str, client_id: str) -> None:
    normalized_user_id = str(user_id or "").strip()
    normalized_client_id = _require_client_id(client_id)
    user = users_db.get(normalized_user_id)
    if not user:
        raise HTTPException(status_code=404, detail="user not found")
    owner_user_id = client_to_user_id.get(normalized_client_id)
    if owner_user_id and owner_user_id != normalized_user_id:
        raise HTTPException(status_code=409, detail="client_id has been bound to another account")
    client_ids = [str(item).strip() for item in list(user.get("client_ids") or []) if str(item or "").strip()]
    if normalized_client_id not in client_ids:
        client_ids.append(normalized_client_id)
    user["client_ids"] = sorted(set(client_ids))
    user["updated_at"] = datetime.now().isoformat()
    users_db[normalized_user_id] = user
    _rebuild_auth_indexes()


def _get_user_id_by_client_id(client_id: str | None) -> str | None:
    normalized_client_id = _normalize_client_id(client_id)
    if not normalized_client_id:
        return None
    return client_to_user_id.get(normalized_client_id)


def _get_user_client_ids(user_id: str | None) -> set[str]:
    normalized_user_id = str(user_id or "").strip()
    if not normalized_user_id:
        return set()
    user = users_db.get(normalized_user_id)
    if not user:
        return set()
    return {str(item).strip() for item in list(user.get("client_ids") or []) if str(item or "").strip()}


def _assert_task_owner(task: BuildTask, client_id: str) -> None:
    normalized_client_id = _require_client_id(client_id)
    task_client_id = _normalize_client_id(task.client_id)
    if task_client_id and task_client_id == normalized_client_id:
        return
    task_user_id = _get_user_id_by_client_id(task_client_id)
    request_user_id = _get_user_id_by_client_id(normalized_client_id)
    if task_user_id and request_user_id and task_user_id == request_user_id:
        return
    raise HTTPException(status_code=403, detail="无权操作此任务")


def _extract_auth_token(request: Request) -> str:
    auth_header = str(request.headers.get("Authorization") or "").strip()
    if not auth_header:
        return ""
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()
    return ""


def _prune_expired_sessions() -> None:
    now = datetime.now()
    expired_tokens = [token for token, session in sessions_db.items() if _parse_iso_datetime(session.get("expires_at")) <= now]
    for token in expired_tokens:
        sessions_db.pop(token, None)


def _create_auth_session(user_id: str, client_id: str) -> tuple[str, datetime]:
    expires_at = datetime.now() + AUTH_SESSION_TTL
    token = secrets.token_urlsafe(48)
    with AUTH_SESSIONS_LOCK:
        _prune_expired_sessions()
        sessions_db[token] = {
            "user_id": str(user_id or "").strip(),
            "client_id": _normalize_client_id(client_id),
            "issued_at": datetime.now().isoformat(),
            "expires_at": expires_at.isoformat(),
        }
    return token, expires_at


def _resolve_user_by_request(request: Request) -> tuple[dict | None, str]:
    token = _extract_auth_token(request)
    if not token:
        return None, ""
    with AUTH_SESSIONS_LOCK:
        _prune_expired_sessions()
        session = sessions_db.get(token)
    if not session:
        return None, token
    expires_at = _parse_iso_datetime(session.get("expires_at"))
    if expires_at <= datetime.now():
        with AUTH_SESSIONS_LOCK:
            sessions_db.pop(token, None)
        return None, token
    user_id = str(session.get("user_id") or "").strip()
    user = users_db.get(user_id)
    if not user:
        with AUTH_SESSIONS_LOCK:
            sessions_db.pop(token, None)
        return None, token
    return user, token


def _require_auth_user(request: Request) -> tuple[dict, str]:
    user, token = _resolve_user_by_request(request)
    if not user or not token:
        raise HTTPException(status_code=401, detail="authentication required")
    return user, token


def _build_auth_session_response(user: dict, token: str, expires_at: datetime) -> AuthSessionResponse:
    return AuthSessionResponse(
        token=token,
        token_type="Bearer",
        expires_at=expires_at,
        user=_user_to_profile(user),
    )


def _safe_filename(value: str, fallback: str = "app") -> str:
    raw = (value or "").strip()
    if not raw:
        return fallback
    safe = "".join(ch if ch.isalnum() or ch in ("-", "_") else "-" for ch in raw)
    safe = "-".join(filter(None, safe.split("-")))
    return safe or fallback


def _iter_zip_entries(zip_file: zipfile.ZipFile):
    for info in zip_file.infolist():
        if info.is_dir():
            continue
        raw_name = str(info.filename or "").replace("\\", "/").strip()
        if not raw_name:
            continue
        normalized = PurePosixPath(raw_name.lstrip("/"))
        parts = [part for part in normalized.parts if part and part != "."]
        if not parts:
            continue
        if any(part == ".." for part in parts):
            continue
        yield info, parts


def _detect_zip_build_mode(zip_path: Path) -> tuple[str, str | None]:
    try:
        with zipfile.ZipFile(zip_path, "r") as archive:
            index_candidates = []
            for _, parts in _iter_zip_entries(archive):
                lower_parts = [part.lower() for part in parts]
                if any(part in {"node_modules", ".git", "android", "__macosx"} for part in lower_parts):
                    continue
                filename = lower_parts[-1]
                if filename == "package.json":
                    return "convert", None
                if filename == "index.html":
                    entry_name = str(PurePosixPath(*parts))
                    index_candidates.append((len(parts), len(entry_name), entry_name))
            if not index_candidates:
                return "invalid", None
            index_candidates.sort(key=lambda item: (item[0], item[1], item[2]))
            return "html", index_candidates[0][2]
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="ZIP format is invalid, please upload again")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to inspect ZIP: {str(exc)}")


def _extract_html_assets_from_zip(zip_path: Path, zip_entry_name: str, dst_assets_dir: Path) -> None:
    try:
        with zipfile.ZipFile(zip_path, "r") as archive:
            normalized_index = PurePosixPath(str(zip_entry_name or "").replace("\\", "/").lstrip("/"))
            index_parts = [part for part in normalized_index.parts if part and part != "."]
            if not index_parts or index_parts[-1].lower() != "index.html":
                raise HTTPException(status_code=400, detail="index.html was not found in ZIP")

            root_parts = index_parts[:-1]
            total_size = 0
            extracted_count = 0
            max_total_size = 1024 * 1024 * 1024
            max_single_size = 200 * 1024 * 1024
            root_parts_tuple = tuple(root_parts)

            dst_assets_dir.mkdir(parents=True, exist_ok=True)

            for info, parts in _iter_zip_entries(archive):
                lower_parts = [part.lower() for part in parts]
                if any(part in {"node_modules", ".git", "android", "__macosx"} for part in lower_parts):
                    continue
                if root_parts and tuple(parts[: len(root_parts_tuple)]) != root_parts_tuple:
                    continue

                relative_parts = parts[len(root_parts_tuple):] if root_parts else parts
                if not relative_parts:
                    continue

                file_size = int(info.file_size or 0)
                if file_size > max_single_size:
                    raise HTTPException(status_code=400, detail="A file in ZIP is too large")

                total_size += file_size
                if total_size > max_total_size:
                    raise HTTPException(status_code=400, detail="ZIP assets are too large")

                dst_file = dst_assets_dir.joinpath(*relative_parts)
                dst_file.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info, "r") as src, open(dst_file, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                extracted_count += 1

            if extracted_count <= 0 or not (dst_assets_dir / "index.html").exists():
                raise HTTPException(status_code=400, detail="index.html was not found in ZIP")
    except HTTPException:
        raise
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="ZIP format is invalid, please upload again")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to extract HTML assets: {str(exc)}")


EXTERNAL_LINK_PATTERN = re.compile(r'(?P<url>(?:https?:)?//[^\s"\'<>()`]+)', re.IGNORECASE)
EXTERNAL_LINK_SCAN_EXTENSIONS = {
    ".html", ".htm", ".css", ".js", ".mjs", ".cjs",
    ".json", ".ts", ".tsx", ".jsx", ".vue", ".xml",
}
EXTERNAL_LINK_SCAN_SKIP_DIRS = {"node_modules", ".git", "android", "__macosx", ".gradle"}
EXTERNAL_LINK_SCAN_MAX_FILE_BYTES = 2 * 1024 * 1024
EXTERNAL_LINK_SCAN_MAX_FILES_PER_ARCHIVE = 1500
EXTERNAL_LINK_SCAN_MAX_MATCHES_PER_FILE = 5000


def _resolve_upload_file(filename: str) -> Path:
    name = str(filename or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="filename is required")
    root = BACKEND_UPLOAD_DIR.resolve()
    candidate = (BACKEND_UPLOAD_DIR / name).resolve()
    try:
        candidate.relative_to(root)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid filename")
    return candidate


def _replace_file_from_upload(src_path: Path, dst_path: Path) -> None:
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    if dst_path.exists():
        dst_path.unlink()
    shutil.move(str(src_path), str(dst_path))


def _clone_or_copy_file(src_path: Path, dst_path: Path) -> None:
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    if dst_path.exists():
        dst_path.unlink()
    try:
        os.link(str(src_path), str(dst_path))
    except Exception:
        shutil.copy2(str(src_path), str(dst_path))


def _resolve_task_asset_path(task_id: str, filename: str) -> Path:
    input_path = TASKS_DIR / task_id / "input" / filename
    if input_path.exists():
        return input_path
    return get_persisted_task_asset_path(task_id, filename)


def _store_task_asset(task_id: str, task_input_dir: Path, filename: str, source_path: Path, move: bool = False) -> Path:
    persist_task_asset(task_id, filename, source_path, move=move)
    restored_path = restore_task_input_asset(task_id, filename, task_input_dir)
    return restored_path or (task_input_dir / filename)


def _persist_task_source_copy(task_id: str, filename: str, source_path: Path) -> Path:
    return persist_task_asset(task_id, filename, source_path, move=False)


def _sync_task_asset_snapshot(task_id: str, task_input_dir: Path, filename: str) -> Path | None:
    asset_path = task_input_dir / filename
    if not asset_path.exists():
        return None
    return persist_task_asset(task_id, filename, asset_path, move=False)


def _detach_working_task_asset(task_id: str, task_input_dir: Path, filename: str) -> Path | None:
    working_path = task_input_dir / filename
    persisted_path = get_persisted_task_asset_path(task_id, filename)
    if not working_path.exists() or not persisted_path.exists():
        return working_path if working_path.exists() else None
    try:
        same_file = os.path.samefile(str(working_path), str(persisted_path))
    except Exception:
        same_file = False
    if not same_file:
        return working_path
    temp_path = task_input_dir / f".detach_{filename}"
    if temp_path.exists():
        temp_path.unlink()
    shutil.copy2(str(working_path), str(temp_path))
    working_path.unlink()
    temp_path.replace(working_path)
    return working_path


def _normalize_external_url(raw_url: str) -> str | None:
    value = str(raw_url or "").strip()
    if not value:
        return None
    if value.startswith("//"):
        value = f"https:{value}"
    try:
        parsed = urllib.parse.urlsplit(value)
    except Exception:
        return None
    scheme = (parsed.scheme or "").strip().lower()
    if scheme not in {"http", "https"}:
        return None
    netloc = (parsed.netloc or "").strip()
    if not netloc:
        return None
    path = parsed.path or "/"
    return urllib.parse.urlunsplit((scheme, netloc, path, parsed.query, ""))


def _normalize_cdn_localize_urls(values) -> list[str]:
    if not isinstance(values, list):
        return []
    result: list[str] = []
    seen: set[str] = set()
    for item in values:
        normalized = _normalize_external_url(str(item or ""))
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def _guess_external_url_type(url: str) -> str:
    path = (urllib.parse.urlsplit(url).path or "").lower()
    if path.endswith(".css"):
        return "css"
    if path.endswith((".js", ".mjs", ".cjs")):
        return "script"
    if path.endswith((".woff", ".woff2", ".ttf", ".otf", ".eot")):
        return "font"
    if path.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico", ".avif")):
        return "image"
    if path.endswith((".mp3", ".wav", ".ogg", ".aac", ".m4a", ".flac", ".mp4", ".webm", ".mov")):
        return "media"
    return "other"


def _collect_external_links_from_text(text: str, file_label: str, collector: dict[str, dict]) -> None:
    match_count = 0
    for match in EXTERNAL_LINK_PATTERN.finditer(text):
        if match_count >= EXTERNAL_LINK_SCAN_MAX_MATCHES_PER_FILE:
            break
        normalized = _normalize_external_url(match.group("url"))
        if not normalized:
            continue
        item = collector.setdefault(
            normalized,
            {"url": normalized, "occurrences": 0, "files": set(), "types": set()},
        )
        item["occurrences"] += 1
        item["files"].add(file_label)
        item["types"].add(_guess_external_url_type(normalized))
        match_count += 1


def _build_external_link_items(collector: dict[str, dict]) -> list[dict]:
    items: list[dict] = []
    for raw in collector.values():
        file_list = sorted(str(item) for item in raw["files"])
        type_list = sorted(str(item) for item in raw["types"])
        item_type = type_list[0] if len(type_list) == 1 else "mixed"
        items.append(
            {
                "url": raw["url"],
                "type": item_type,
                "occurrences": int(raw["occurrences"]),
                "file_count": len(file_list),
                "files": file_list[:8],
            }
        )
    items.sort(key=lambda x: (-x["occurrences"], -x["file_count"], x["url"]))
    return items


def _scan_external_links_in_zip(zip_path: Path) -> list[dict]:
    collector: dict[str, dict] = {}
    scanned_files = 0
    try:
        with zipfile.ZipFile(zip_path, "r") as archive:
            for info, parts in _iter_zip_entries(archive):
                if scanned_files >= EXTERNAL_LINK_SCAN_MAX_FILES_PER_ARCHIVE:
                    break
                lower_parts = [part.lower() for part in parts]
                if any(part in EXTERNAL_LINK_SCAN_SKIP_DIRS for part in lower_parts):
                    continue
                suffix = PurePosixPath(parts[-1]).suffix.lower()
                if suffix not in EXTERNAL_LINK_SCAN_EXTENSIONS:
                    continue
                file_size = int(info.file_size or 0)
                if file_size <= 0 or file_size > EXTERNAL_LINK_SCAN_MAX_FILE_BYTES:
                    continue
                try:
                    with archive.open(info, "r") as source:
                        content = source.read(EXTERNAL_LINK_SCAN_MAX_FILE_BYTES + 1)
                    if len(content) > EXTERNAL_LINK_SCAN_MAX_FILE_BYTES:
                        continue
                    text = content.decode("utf-8", errors="ignore")
                except Exception:
                    continue
                scanned_files += 1
                file_label = str(PurePosixPath(*parts))
                _collect_external_links_from_text(text, file_label, collector)
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="ZIP format is invalid, please upload again")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to scan ZIP external links: {str(exc)}")
    return _build_external_link_items(collector)


def _scan_external_links_in_html(html_path: Path) -> list[dict]:
    collector: dict[str, dict] = {}
    try:
        text = html_path.read_text(encoding="utf-8", errors="ignore")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read HTML file: {str(exc)}")
    _collect_external_links_from_text(text, html_path.name, collector)
    return _build_external_link_items(collector)


CDN_LOCALIZE_SCRIPT_PATH = Path(__file__).resolve().parents[2] / "apk-worker" / "scripts" / "offlineize_html_assets.mjs"
CDN_LOCALIZE_FAILED_PATTERN = re.compile(r"\[offlineize\]\s+failed:\s+(?P<url>\S+)", re.IGNORECASE)
CDN_LOCALIZE_TIMEOUT_SECONDS = 300
CDN_LOCALIZE_SKIP_DIRS = {"node_modules", ".git", "android", "__macosx", ".gradle"}


def _append_task_log(task: BuildTask, message: str) -> None:
    """向任务日志追加一行（带时间戳）"""
    if not message:
        return
    logs = task.logs if isinstance(task.logs, list) else []
    timestamp = datetime.now().strftime("%H:%M:%S")
    logs.append(f"[{timestamp}] {message}")
    if len(logs) > 500:
        logs = logs[-500:]
    task.logs = logs


def _collect_task_failure_log_lines(task_id: str, task: BuildTask, max_lines: int = 240) -> list[str]:
    """收集任务失败日志，优先使用内存日志，回退到日志文件。"""
    lines: list[str] = []
    if isinstance(getattr(task, "logs", None), list) and task.logs:
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


def _schedule_task_failure_diagnosis(
    task_id: str,
    task: BuildTask,
    force: bool = False,
    language: str | None = None,
) -> bool:
    """调度失败任务诊断，避免重复并发分析。"""
    if task.status != BuildStatus.FAILED:
        return False
    normalized_language = normalize_diag_language(language)

    current_diagnosis = getattr(task, "failure_diagnosis", {})
    if not isinstance(current_diagnosis, dict):
        current_diagnosis = {}

    current_status = str(current_diagnosis.get("status", "")).strip().lower()
    if not force and current_status in {"running", "succeeded"}:
        return False

    with TASK_DIAGNOSIS_LOCK:
        if task_id in TASK_DIAGNOSIS_RUNNING_IDS:
            return False
        TASK_DIAGNOSIS_RUNNING_IDS.add(task_id)

    log_lines = _collect_task_failure_log_lines(task_id, task)
    task.failure_diagnosis = create_running_diagnosis(
        provider="openrouter" if OPENROUTER_DIAG_ENABLED else "rule",
        model=OPENROUTER_MODEL if OPENROUTER_DIAG_ENABLED else "",
        analyzed_log_lines=len(log_lines),
        language=normalized_language,
    )
    task.updated_at = datetime.now()
    try:
        persist_tasks_db(force=True)
    except Exception:
        pass

    def _worker() -> None:
        try:
            task_meta = {
                "task_id": task_id,
                "task_mode": str(getattr(task, "mode", "convert") or "convert"),
                "output_format": str(getattr(getattr(task, "config", None), "output_format", "apk") or "apk"),
                "app_name": str(getattr(getattr(task, "config", None), "app_name", "") or ""),
                "package_name": str(getattr(getattr(task, "config", None), "package_name", "") or ""),
                "language": normalized_language,
            }
            diagnosis = diagnose_build_failure(
                log_lines=log_lines,
                failure_message=str(getattr(task, "message", "") or ""),
                task_meta=task_meta,
                language=normalized_language,
            )
            task.failure_diagnosis = (
                diagnosis
                if isinstance(diagnosis, dict)
                else create_failed_diagnosis("invalid diagnosis payload", language=normalized_language)
            )
        except Exception as exc:
            task.failure_diagnosis = create_failed_diagnosis(
                str(exc),
                analyzed_log_lines=len(log_lines),
                language=normalized_language,
            )
        finally:
            task.updated_at = datetime.now()
            with TASK_DIAGNOSIS_LOCK:
                TASK_DIAGNOSIS_RUNNING_IDS.discard(task_id)
            try:
                persist_tasks_db(force=True)
            except Exception:
                pass

    threading.Thread(target=_worker, daemon=True, name=f"TaskDiagnosis-{task_id[:8]}").start()
    return True


def _resolve_node_executable() -> str:
    """优先使用环境配置中的 Node，可回退到系统 PATH"""
    try:
        status = env_setup.get_status()
        node_dir = str((status or {}).get("paths", {}).get("node", "")).strip()
        if node_dir:
            node_name = "node.exe" if os.name == "nt" else "node"
            candidate = Path(node_dir) / node_name
            if candidate.exists():
                return str(candidate)
    except Exception:
        pass
    return "node"


def _split_process_output(text: str) -> list[str]:
    return [line.strip() for line in str(text or "").splitlines() if str(line).strip()]


def _collect_failed_urls(lines: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for line in lines:
        match = CDN_LOCALIZE_FAILED_PATTERN.search(line)
        if not match:
            continue
        url = str(match.group("url") or "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        result.append(url)
    return result


def _run_offlineize_script(entry_html: Path, allow_urls: list[str]) -> dict:
    if not CDN_LOCALIZE_SCRIPT_PATH.exists():
        return {
            "ok": False,
            "failed_urls": [],
            "error": f"offlineize script not found: {CDN_LOCALIZE_SCRIPT_PATH}",
        }
    if not entry_html.exists():
        return {"ok": False, "failed_urls": [], "error": f"entry html not found: {entry_html}"}

    entry_abs = entry_html.resolve()
    command = [_resolve_node_executable(), str(CDN_LOCALIZE_SCRIPT_PATH), str(entry_abs)]
    for url in allow_urls:
        normalized = str(url or "").strip()
        if normalized:
            command.extend(["--allow-url", normalized])

    process_env = os.environ.copy()
    try:
        process_env.update(env_setup.get_env_overrides())
    except Exception:
        pass

    try:
        completed = subprocess.run(
            command,
            cwd=str(entry_abs.parent),
            env=process_env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=CDN_LOCALIZE_TIMEOUT_SECONDS,
        )
    except FileNotFoundError as exc:
        return {"ok": False, "failed_urls": [], "error": f"node runtime not found: {exc}"}
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "failed_urls": [],
            "error": f"offlineize timeout after {CDN_LOCALIZE_TIMEOUT_SECONDS}s",
        }
    except Exception as exc:
        return {"ok": False, "failed_urls": [], "error": f"offlineize failed: {str(exc)}"}

    lines = _split_process_output(completed.stdout) + _split_process_output(completed.stderr)
    failed_urls = _collect_failed_urls(lines)
    if completed.returncode != 0:
        detail = ""
        if lines:
            detail = f": {' | '.join(lines[-4:])}"
        return {
            "ok": False,
            "failed_urls": failed_urls,
            "error": f"offlineize exit code {completed.returncode}{detail}",
        }
    return {"ok": True, "failed_urls": failed_urls, "error": ""}


def _pick_zip_index_entry(zip_path: Path) -> str | None:
    candidates: list[tuple[int, int, str]] = []
    try:
        with zipfile.ZipFile(zip_path, "r") as archive:
            for _, parts in _iter_zip_entries(archive):
                lower_parts = [part.lower() for part in parts]
                if any(part in CDN_LOCALIZE_SKIP_DIRS for part in lower_parts):
                    continue
                if lower_parts[-1] != "index.html":
                    continue
                entry_name = str(PurePosixPath(*parts))
                candidates.append((len(parts), len(entry_name), entry_name))
    except Exception:
        return None
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1], item[2]))
    return candidates[0][2]


def _extract_zip_to_dir(zip_path: Path, dst_dir: Path) -> None:
    with zipfile.ZipFile(zip_path, "r") as archive:
        for info, parts in _iter_zip_entries(archive):
            target = dst_dir.joinpath(*parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info, "r") as source, open(target, "wb") as output:
                shutil.copyfileobj(source, output)


def _pack_dir_to_zip(src_dir: Path, dst_zip: Path) -> None:
    with zipfile.ZipFile(dst_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        files = sorted([path for path in src_dir.rglob("*") if path.is_file()], key=lambda item: item.as_posix())
        for file_path in files:
            archive.write(file_path, file_path.relative_to(src_dir).as_posix())


def _replace_dir_with_retry(src_dir: Path, dst_dir: Path, retries: int = 4) -> bool:
    """优先 move，失败时重试并回退 copy，返回是否使用了 move"""
    if dst_dir.exists():
        shutil.rmtree(dst_dir, ignore_errors=True)
    last_error = None
    for attempt in range(max(1, retries)):
        try:
            shutil.move(str(src_dir), str(dst_dir))
            return True
        except Exception as exc:
            last_error = exc
            if attempt < retries - 1:
                time.sleep(0.15 * (attempt + 1))
    try:
        dst_dir.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src_dir, dst_dir, dirs_exist_ok=True)
        return False
    except Exception:
        if last_error:
            raise last_error
        raise


def _preprocess_html_task_input(task_input_dir: Path, allow_urls: list[str]) -> dict:
    html_index = task_input_dir / "index.html"
    html_assets_dir = task_input_dir / "html_assets"
    html_assets_index = html_assets_dir / "index.html"

    if not html_assets_index.exists():
        if not html_index.exists():
            return {
                "preprocessed": False,
                "failed_urls": [],
                "log_lines": ["[CDN] 未找到 HTML 入口文件，跳过预处理。"],
            }
        html_assets_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(html_index), str(html_assets_index))

    temp_dir = task_input_dir / "_tmp_cdn_localize_html"
    if temp_dir.exists():
        shutil.rmtree(temp_dir, ignore_errors=True)

    try:
        shutil.copytree(html_assets_dir, temp_dir)
        run_result = _run_offlineize_script(temp_dir / "index.html", allow_urls)
        failed_urls = run_result.get("failed_urls", [])
        if not run_result.get("ok"):
            return {
                "preprocessed": False,
                "failed_urls": failed_urls,
                "log_lines": [f"[CDN] HTML 外链预处理执行失败，已保留原始外链：{run_result.get('error') or 'unknown error'}"],
            }

        used_move = _replace_dir_with_retry(temp_dir, html_assets_dir)
        if used_move:
            temp_dir = None
        if html_assets_index.exists():
            shutil.copy2(str(html_assets_index), str(html_index))
        return {"preprocessed": True, "failed_urls": failed_urls, "log_lines": ["[CDN] HTML 外链预处理完成。"]}
    except Exception as exc:
        return {
            "preprocessed": False,
            "failed_urls": [],
            "log_lines": [f"[CDN] HTML 外链预处理异常，已保留原始外链：{str(exc)}"],
        }
    finally:
        if temp_dir and Path(temp_dir).exists():
            shutil.rmtree(temp_dir, ignore_errors=True)


def _preprocess_convert_task_input(task_input_dir: Path, allow_urls: list[str]) -> dict:
    project_zip = task_input_dir / "project.zip"
    if not project_zip.exists():
        return {
            "preprocessed": False,
            "failed_urls": [],
            "log_lines": ["[CDN] 未找到 project.zip，跳过外链预处理。"],
        }

    entry_name = _pick_zip_index_entry(project_zip)
    if not entry_name:
        return {
            "preprocessed": False,
            "failed_urls": [],
            "log_lines": ["[CDN] ZIP 中未检测到 index.html，跳过外链预处理。"],
        }

    temp_dir = task_input_dir / "_tmp_cdn_localize_zip"
    if temp_dir.exists():
        shutil.rmtree(temp_dir, ignore_errors=True)

    try:
        temp_dir.mkdir(parents=True, exist_ok=True)
        _extract_zip_to_dir(project_zip, temp_dir)
        entry_path = temp_dir.joinpath(*PurePosixPath(entry_name).parts)
        run_result = _run_offlineize_script(entry_path, allow_urls)
        failed_urls = run_result.get("failed_urls", [])
        if not run_result.get("ok"):
            return {
                "preprocessed": False,
                "failed_urls": failed_urls,
                "log_lines": [f"[CDN] ZIP 外链预处理执行失败，已保留原始外链：{run_result.get('error') or 'unknown error'}"],
            }
        _pack_dir_to_zip(temp_dir, project_zip)
        return {
            "preprocessed": True,
            "failed_urls": failed_urls,
            "log_lines": [f"[CDN] ZIP 外链预处理完成，入口文件：{entry_name}"],
        }
    except Exception as exc:
        return {
            "preprocessed": False,
            "failed_urls": [],
            "log_lines": [f"[CDN] ZIP 外链预处理异常，已保留原始外链：{str(exc)}"],
        }
    finally:
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)


def _preprocess_task_cdn_localization(
    task_mode: str,
    task_input_dir: Path,
    enabled: bool,
    selected_urls: list[str],
) -> dict:
    normalized_mode = str(task_mode or "").strip().lower()
    allow_urls = _normalize_cdn_localize_urls(selected_urls)
    selection_desc = f"选中 {len(allow_urls)} 条" if allow_urls else "全部"

    if normalized_mode not in {"convert", "html"}:
        return {"preprocessed": False, "failed_urls": [], "log_lines": []}
    if not enabled:
        return {
            "preprocessed": False,
            "failed_urls": [],
            "log_lines": ["[CDN] 已关闭外链本地化，保留原始外链引用。"],
        }

    log_lines = [f"[CDN] 开始外链本地化预处理（模式: {normalized_mode}，范围: {selection_desc}）。"]
    inner = _preprocess_html_task_input(task_input_dir, allow_urls) if normalized_mode == "html" else _preprocess_convert_task_input(task_input_dir, allow_urls)
    failed_urls = _normalize_cdn_localize_urls(inner.get("failed_urls", []))
    log_lines.extend(inner.get("log_lines", []))
    if failed_urls:
        log_lines.append("[CDN] 以下外链本地化失败，已保留原链接：")
        for url in failed_urls:
            log_lines.append(f"[CDN] {url}")
    return {
        "preprocessed": bool(inner.get("preprocessed")),
        "failed_urls": failed_urls,
        "log_lines": log_lines,
    }

FRONTEND_LOGGED = False
FRONTEND_LOG_PATH = Path(os.getenv("APPDATA", ".")) / "ConvertAPK" / "frontend-resolve.log"
BACKEND_ENV_LOG_PATH = Path(os.getenv("APPDATA", ".")) / "ConvertAPK" / "backend-env.log"


def _mask_token(token: str) -> str:
    if not token:
        return ""
    if len(token) <= 6:
        return "*" * len(token)
    return f"{token[:2]}***{token[-2:]}"


def _log_backend_env() -> None:
    try:
        BACKEND_ENV_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        admin_url = os.getenv("ADMIN_API_URL", "") or os.getenv("CONVERTAPK_ADMIN_URL", "")
        admin_token = os.getenv("ADMIN_CLIENT_TOKEN", "") or os.getenv("CONVERTAPK_CLIENT_TOKEN", "")
        lines = [
            f"ADMIN_API_URL={admin_url}",
            f"ADMIN_CLIENT_TOKEN={_mask_token(admin_token)}",
            f"CONVERTAPK_PORT={os.getenv('CONVERTAPK_PORT', '')}",
        ]
        BACKEND_ENV_LOG_PATH.write_text("\n".join(lines), encoding="utf-8")
    except Exception:
        pass


def _log_frontend_candidates(candidates: list[Path], env: dict) -> None:
    global FRONTEND_LOGGED
    if FRONTEND_LOGGED:
        return
    FRONTEND_LOGGED = True
    try:
        FRONTEND_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            f"sys.executable={sys.executable}",
            f"cwd={Path.cwd()}",
            f"FRONTEND_DIST_DIR={env.get('FRONTEND_DIST_DIR', '')}",
            f"ELECTRON_RESOURCES={env.get('ELECTRON_RESOURCES', '')}",
        ]
        for candidate in candidates:
            exists = candidate.exists()
            has_index = (candidate / "index.html").exists()
            lines.append(f"candidate={candidate} exists={exists} index={has_index}")
        FRONTEND_LOG_PATH.write_text("\n".join(lines), encoding="utf-8")
    except Exception:
        pass


def resolve_frontend_dist() -> Path | None:
    candidates = []
    frontend_dist_env = os.getenv("FRONTEND_DIST_DIR", "").strip()
    if frontend_dist_env:
        candidates.append(Path(frontend_dist_env).expanduser())
    candidates.append((Path(__file__).parent.parent / "frontend" / "dist").resolve())
    exe_dir = Path(sys.executable).parent
    candidates.append(exe_dir / "frontend")
    candidates.append(exe_dir.parent / "frontend")
    cwd = Path.cwd()
    candidates.append(cwd / "frontend")
    candidates.append(cwd / "resources" / "frontend")
    resources_env = os.getenv("ELECTRON_RESOURCES", "").strip()
    if resources_env:
        candidates.append(Path(resources_env) / "frontend")

    _log_frontend_candidates(candidates, os.environ)

    for candidate in candidates:
        if candidate.exists() and (candidate / "index.html").exists():
            return candidate
    return None


_log_backend_env()

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def ensure_env_ready(request: Request, call_next):
    ok, reason = check_admin_service()
    if not ok:
        return JSONResponse(
            status_code=503,
            content={
                "detail": "服务已停用，请联系作者",
                "reason": reason,
            },
        )
    return await call_next(request)


def _should_cleanup_desktop_output_on_download(task: BuildTask) -> bool:
    return str(getattr(task, "mode", "") or "").strip().lower() == "desktop"


def _consume_desktop_output(task: BuildTask, reason: str) -> str | None:
    if not _should_cleanup_desktop_output_on_download(task):
        return None
    output_name = str(getattr(task, "output_filename", "") or "").strip()
    if not output_name:
        return None
    task.output_filename = None
    task.download_url = None
    task.updated_at = datetime.now()
    if reason == "download":
        task.message = "EXE 已下载，安装包已从服务器移除"
    else:
        task.message = "已退出网站，桌面安装包已从服务器移除"
    if reason == "download":
        task.message = "EXE 下载成功，仅可下载一次；为降低服务器占用，安装包已自动删除"
    else:
        task.message = "已离开网站，EXE 仅可下载一次；为降低服务器占用，安装包已自动删除"
    try:
        persist_tasks_db(force=True)
    except Exception:
        pass
    return output_name


def _get_desktop_output_unavailable_detail(task: BuildTask) -> str:
    message = str(getattr(task, "message", "") or "").strip()
    if message:
        return message
    return "桌面安装包已不可下载（仅提供一次下载机会，为降低服务器占用已自动清理）"

# 内存存储（MVP版本）
tasks_db = {}
TASKS_STATE_PATH = TASKS_DIR / "tasks.json"
TASKS_STATE_LOCK = threading.Lock()
TASK_DIAGNOSIS_LOCK = threading.Lock()
TASK_DIAGNOSIS_RUNNING_IDS: set[str] = set()

# One-click (Quick) generate defaults (client-side shortcut).
QUICK_GENERATE_STATE_PATH = TASKS_DIR / "quick-generate.json"
QUICK_GENERATE_STATE_LOCK = threading.Lock()
QUICK_GENERATE_SHARED_KEYSTORE_PATH = TASKS_DIR.parent / "quick-generate" / "release.keystore"
QUICK_GENERATE_KEYSTORE_LOCK = threading.Lock()
TEMPLATES_DIR = APK_WORKER_DIR.parent / "templates"
QUICK_GENERATE_ICON_PATH = TEMPLATES_DIR / "demoLogo.png"
QUICK_GENERATE_APP_NAME = "demo"
QUICK_GENERATE_PACKAGE_NAME = "com.convertapk.demo"
QUICK_GENERATE_KEY_ALIAS = "key0"
QUICK_GENERATE_KEYSTORE_PASSWORD = "123456"
QUICK_GENERATE_KEY_PASSWORD = "123456"
QUICK_GENERATE_PERMISSIONS = [
    "INTERNET",
    "ACCESS_NETWORK_STATE",
    "ACCESS_WIFI_STATE",
    "CAMERA",
    "READ_EXTERNAL_STORAGE",
    "WRITE_EXTERNAL_STORAGE",
    "ACCESS_FINE_LOCATION",
    "ACCESS_COARSE_LOCATION",
    "RECORD_AUDIO",
    "READ_PHONE_STATE",
    "CALL_PHONE",
    "READ_CONTACTS",
    "WRITE_CONTACTS",
    "VIBRATE",
    "WAKE_LOCK",
    "RECEIVE_BOOT_COMPLETED",
    "FOREGROUND_SERVICE",
    "REQUEST_INSTALL_PACKAGES",
    "SYSTEM_ALERT_WINDOW",
    "BLUETOOTH",
    "BLUETOOTH_ADMIN",
    "NFC",
    "READ_CALENDAR",
    "WRITE_CALENDAR",
]


def _resolve_quick_generate_icon_path() -> Path | None:
    """
    Quick-generate icon may live in different locations depending on how the backend
    is launched (source tree, packaged executable, etc.). Resolve it robustly.
    """
    candidates: list[Path] = []

    # Source tree / normal path.
    candidates.append(QUICK_GENERATE_ICON_PATH)

    # Based on backend file location (repo layout: <root>/web/backend/main.py).
    try:
        root_from_file = Path(__file__).resolve().parent.parent.parent
        candidates.append(root_from_file / "templates" / "demoLogo.png")
        candidates.append(root_from_file / "apk-worker" / "templates" / "demoLogo.png")
    except Exception:
        pass

    # Current working directory.
    candidates.append(Path.cwd() / "templates" / "demoLogo.png")
    candidates.append(Path.cwd() / "apk-worker" / "templates" / "demoLogo.png")

    # Packaged apps (PyInstaller).
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass) / "apk-worker" / "templates" / "demoLogo.png")
        candidates.append(Path(meipass) / "templates" / "demoLogo.png")

    # Next to executable / resources.
    try:
        exe_dir = Path(sys.executable).resolve().parent
        candidates.append(exe_dir / "templates" / "demoLogo.png")
        candidates.append(exe_dir / "apk-worker" / "templates" / "demoLogo.png")
        candidates.append(exe_dir.parent / "templates" / "demoLogo.png")
        candidates.append(exe_dir.parent / "apk-worker" / "templates" / "demoLogo.png")
        candidates.append(exe_dir.parent.parent / "templates" / "demoLogo.png")
        candidates.append(exe_dir.parent.parent / "apk-worker" / "templates" / "demoLogo.png")
        candidates.append(exe_dir / "resources" / "templates" / "demoLogo.png")
        candidates.append(exe_dir / "resources" / "apk-worker" / "templates" / "demoLogo.png")
        candidates.append(exe_dir.parent / "resources" / "templates" / "demoLogo.png")
        candidates.append(exe_dir.parent / "resources" / "apk-worker" / "templates" / "demoLogo.png")
        candidates.append(exe_dir.parent.parent / "resources" / "templates" / "demoLogo.png")
        candidates.append(exe_dir.parent.parent / "resources" / "apk-worker" / "templates" / "demoLogo.png")
    except Exception:
        pass

    seen = set()
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except Exception:
            resolved = candidate
        key = str(resolved)
        if key in seen:
            continue
        seen.add(key)
        try:
            if resolved.exists():
                return resolved
        except Exception:
            continue

    return None


def _png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    crc = binascii.crc32(chunk_type)
    crc = binascii.crc32(data, crc)
    return (
        struct.pack(">I", len(data))
        + chunk_type
        + data
        + struct.pack(">I", crc & 0xFFFFFFFF)
    )


def _write_quick_generate_placeholder_icon(path: Path, size: int = 1024) -> None:
    """
    Fallback icon when demoLogo.png is missing.
    Generates a simple 1024x1024 RGBA PNG using only stdlib.
    """
    w = int(size)
    h = int(size)
    if w < 1 or h < 1:
        w = h = 1

    cx = (w - 1) / 2.0
    cy = (h - 1) / 2.0
    radius = min(w, h) * 0.36
    r2 = radius * radius
    x2 = [(x - cx) ** 2 for x in range(w)]

    rows: list[bytes] = []
    denom = max(1, h - 1)
    for y in range(h):
        dy2 = (y - cy) ** 2
        base = 22 + int(40 * y / denom)
        row = bytearray(1 + w * 4)
        row[0] = 0  # filter: None
        idx = 1
        for x in range(w):
            dist2 = x2[x] + dy2
            if dist2 < r2:
                # Subtle highlight (a soft "badge" look).
                dist = (dist2 / r2) ** 0.5
                bump = int(130 * (1.0 - dist))
                r = min(255, base + bump)
                g = min(255, base + bump + 6)
                b = min(255, base + bump + 34)
            else:
                r = base
                g = base
                b = min(255, base + 10)
            row[idx] = r
            row[idx + 1] = g
            row[idx + 2] = b
            row[idx + 3] = 255
            idx += 4
        rows.append(bytes(row))

    raw = b"".join(rows)
    compressed = zlib.compress(raw, level=9)

    png = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)  # 8-bit RGBA
    png += _png_chunk(b"IHDR", ihdr)
    png += _png_chunk(b"IDAT", compressed)
    png += _png_chunk(b"IEND", b"")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png)


def _bump_patch_version(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return "1.0.1"
    parts: list[int] = []
    for item in raw.split("."):
        try:
            parts.append(max(0, int(item)))
        except Exception:
            parts.append(0)
    while len(parts) < 3:
        parts.append(0)
    parts[-1] += 1
    return ".".join(str(p) for p in parts)


def _load_quick_generate_state() -> dict:
    default = {"version_name": "1.0.0", "version_code": 1}
    try:
        if not QUICK_GENERATE_STATE_PATH.exists():
            return default
        data = json.loads(QUICK_GENERATE_STATE_PATH.read_text(encoding="utf-8"))
        version_name = str(data.get("version_name") or default["version_name"]).strip() or default["version_name"]
        try:
            version_code = int(data.get("version_code") or default["version_code"])
        except Exception:
            version_code = default["version_code"]
        if version_code < 1:
            version_code = 1
        return {"version_name": version_name, "version_code": version_code}
    except Exception:
        return default


def _persist_quick_generate_state(state: dict) -> None:
    QUICK_GENERATE_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = QUICK_GENERATE_STATE_PATH.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(QUICK_GENERATE_STATE_PATH)


def _alloc_quick_generate_versions() -> tuple[str, int]:
    with QUICK_GENERATE_STATE_LOCK:
        current = _load_quick_generate_state()
        version_name = current.get("version_name") or "1.0.0"
        version_code = int(current.get("version_code") or 1)
        next_state = {
            "version_name": _bump_patch_version(version_name),
            "version_code": version_code + 1,
        }
        _persist_quick_generate_state(next_state)
        return version_name, version_code


def _findQuickGenerateKeystoreFromTasks(requireSuccess: bool = True) -> Path | None:
    latestPath = None
    latestUpdatedAt = datetime.min
    for task in list(tasks_db.values()):
        if not bool(getattr(task, "quick_generate", False)):
            continue
        taskId = str(getattr(task, "id", "") or "").strip()
        if not taskId:
            continue
        taskKeystorePath = TASKS_DIR / taskId / "keystore" / "release.keystore"
        if not taskKeystorePath.exists():
            continue
        status = getattr(task, "status", "")
        statusValue = status.value if hasattr(status, "value") else str(status)
        if requireSuccess and statusValue != BuildStatus.SUCCESS.value:
            continue
        updatedAt = getattr(task, "updated_at", None)
        if isinstance(updatedAt, datetime):
            if latestPath is None or updatedAt >= latestUpdatedAt:
                latestPath = taskKeystorePath
                latestUpdatedAt = updatedAt
        elif latestPath is None:
            latestPath = taskKeystorePath
    return latestPath


def _ensureQuickGenerateSharedKeystore() -> Path | None:
    with QUICK_GENERATE_KEYSTORE_LOCK:
        if QUICK_GENERATE_SHARED_KEYSTORE_PATH.exists():
            return QUICK_GENERATE_SHARED_KEYSTORE_PATH
        sourcePath = _findQuickGenerateKeystoreFromTasks(requireSuccess=True)
        if not sourcePath or not sourcePath.exists():
            return None
        try:
            QUICK_GENERATE_SHARED_KEYSTORE_PATH.parent.mkdir(parents=True, exist_ok=True)
            tmpPath = QUICK_GENERATE_SHARED_KEYSTORE_PATH.with_suffix(".keystore.tmp")
            shutil.copy2(str(sourcePath), str(tmpPath))
            tmpPath.replace(QUICK_GENERATE_SHARED_KEYSTORE_PATH)
            return QUICK_GENERATE_SHARED_KEYSTORE_PATH
        except Exception:
            return None


def _task_to_dict(task: BuildTask) -> dict:
    data = task.model_dump()
    status = task.status
    data["status"] = status.value if hasattr(status, "value") else str(status)
    data["created_at"] = task.created_at.isoformat()
    data["updated_at"] = task.updated_at.isoformat()
    return data


def _task_from_dict(data: dict) -> BuildTask | None:
    try:
        status = data.get("status")
        if status:
            try:
                data["status"] = BuildStatus(status)
            except Exception:
                data["status"] = BuildStatus.PENDING
        if data.get("created_at"):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        if data.get("updated_at"):
            data["updated_at"] = datetime.fromisoformat(data["updated_at"])
        task = BuildTask(**data)
        if task.status == BuildStatus.PROCESSING:
            task.status = BuildStatus.PENDING
            task.message = "上次运行中断，等待重新开始"
            task.updated_at = datetime.now()
        return task
    except Exception:
        return None


def persist_tasks_db(force: bool = False) -> None:
    TASKS_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with TASKS_STATE_LOCK:
        payload = [_task_to_dict(task) for task in tasks_db.values()]
        tmp_path = TASKS_STATE_PATH.with_suffix(".json.tmp")
        tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp_path.replace(TASKS_STATE_PATH)


def _onTasksStateChange(force: bool = False) -> None:
    persist_tasks_db(force=force)
    _ensureQuickGenerateSharedKeystore()


def load_tasks_db() -> None:
    if not TASKS_STATE_PATH.exists():
        return
    try:
        data = json.loads(TASKS_STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return
    if not isinstance(data, list):
        return
    for item in data:
        if not isinstance(item, dict):
            continue
        task = _task_from_dict(item)
        if not task:
            continue
        task_dir = TASKS_DIR / task.id
        if not task_dir.exists():
            persisted_zip = get_persisted_task_asset_path(task.id, "project.zip")
            persisted_icon = get_persisted_task_asset_path(task.id, "logo.png")
            if not persisted_zip.exists() and not persisted_icon.exists():
                continue
            (task_dir / "output").mkdir(parents=True, exist_ok=True)
            (task_dir / "keystore").mkdir(parents=True, exist_ok=True)
            ensure_task_input_assets(task.id, task_dir / "input")
        tasks_db[task.id] = task

# 上传/输出目录（支持通过环境变量 APK_BUILDER_DATA_DIR 迁移到数据卷）
BACKEND_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
BACKEND_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

load_tasks_db()
_load_auth_users_db()

@app.get("/")
async def root():
    frontend_dist = resolve_frontend_dist()
    if frontend_dist:
        return FileResponse(str(frontend_dist / "index.html"))
    return {
        "message": "APK转换服务API",
        "version": "1.0.0",
        "frontend_found": False,
        "frontend_log": str(FRONTEND_LOG_PATH),
    }


@app.get("/assets/{path:path}", include_in_schema=False)
async def assets(path: str):
    frontend_dist = resolve_frontend_dist()
    if not frontend_dist:
        raise HTTPException(status_code=404, detail="Not Found")
    asset_file = frontend_dist / "assets" / path
    if not asset_file.exists():
        raise HTTPException(status_code=404, detail="Not Found")
    return FileResponse(str(asset_file))


@app.post("/api/auth/register", response_model=AuthSessionResponse)
async def auth_register(payload: AuthRegisterRequest):
    """用户注册并绑定当前客户端"""
    client_id = _require_client_id(payload.client_id)
    if not _is_client_register_enabled(client_id):
        raise HTTPException(status_code=403, detail="register is disabled by admin for current client")
    email = _validate_email_or_raise(payload.email)
    password = _validate_password_or_raise(payload.password)
    if email in email_to_user_id:
        raise HTTPException(status_code=409, detail="email already exists")

    user_id = f"user_{uuid.uuid4().hex}"
    now_iso = datetime.now().isoformat()
    salt_hex = secrets.token_hex(16)
    users_db[user_id] = {
        "id": user_id,
        "email": email,
        "phone": "",
        "auth_provider": "local",
        "github_id": "",
        "github_login": "",
        "password_salt": salt_hex,
        "password_hash": _hash_password(password, salt_hex),
        "client_ids": [],
        "created_at": now_iso,
        "updated_at": now_iso,
        "last_login_at": now_iso,
    }
    _bind_client_to_user(user_id, client_id)
    _persist_auth_users_db()
    user = users_db[user_id]
    token, expires_at = _create_auth_session(user_id, client_id)
    return _build_auth_session_response(user, token, expires_at)


@app.post("/api/auth/login", response_model=AuthSessionResponse)
async def auth_login(payload: AuthLoginRequest):
    """用户登录并绑定当前客户端"""
    client_id = _require_client_id(payload.client_id)
    if not _is_client_login_enabled(client_id):
        raise HTTPException(status_code=403, detail="login is disabled by admin for current client")
    email = _validate_email_or_raise(payload.email)
    password = _validate_password_or_raise(payload.password)
    user_id = email_to_user_id.get(email)
    if not user_id:
        raise HTTPException(status_code=401, detail="email or password is incorrect")
    user = users_db.get(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="email or password is incorrect")
    if not _verify_password(password, str(user.get("password_salt") or ""), str(user.get("password_hash") or "")):
        raise HTTPException(status_code=401, detail="email or password is incorrect")

    _bind_client_to_user(user_id, client_id)
    now_iso = datetime.now().isoformat()
    user["last_login_at"] = now_iso
    user["updated_at"] = now_iso
    users_db[user_id] = user
    _persist_auth_users_db()
    token, expires_at = _create_auth_session(user_id, client_id)
    return _build_auth_session_response(user, token, expires_at)


@app.post("/api/auth/sms/send-code")
async def auth_sms_send_code(payload: AuthSmsSendRequest, request: Request):
    """发送短信验证码"""
    client_id = _require_client_id(payload.client_id)
    if not _is_client_login_enabled(client_id):
        raise HTTPException(status_code=403, detail="login is disabled by admin for current client")
    if not _is_client_sms_login_enabled(client_id):
        raise HTTPException(status_code=403, detail="sms login is disabled by admin for current client")
    phone = _validate_phone_or_raise(payload.phone)
    redis_client = _get_sms_redis_client()
    code = f"{secrets.randbelow(1_000_000):06d}"
    code_key = _sms_redis_key(f"code:{phone}")
    send_lock_key = _sms_redis_key(f"send-lock:{phone}")
    day_bucket = datetime.utcnow().strftime("%Y%m%d")
    hour_bucket = datetime.utcnow().strftime("%Y%m%d%H")
    day_limit_key = _sms_redis_key(f"send-day:{phone}:{day_bucket}")
    ip = _extract_request_ip(request)
    ip_limit_key = _sms_redis_key(f"send-ip:{ip}:{hour_bucket}")
    salt_hex = secrets.token_hex(16)
    code_hash = _hash_sms_code(code, salt_hex)
    try:
        _check_and_incr_sms_rate_limit(
            redis_client=redis_client,
            key=ip_limit_key,
            window_seconds=3700,
            limit=AUTH_SMS_IP_HOURLY_LIMIT,
            detail="sms send rate limited",
        )
        if not redis_client.set(send_lock_key, "1", ex=AUTH_SMS_RESEND_INTERVAL_SECONDS, nx=True):
            raise HTTPException(status_code=429, detail="sms send too frequently")
        _check_and_incr_sms_rate_limit(
            redis_client=redis_client,
            key=day_limit_key,
            window_seconds=2 * 24 * 3600,
            limit=AUTH_SMS_DAILY_LIMIT,
            detail="sms send daily limit reached",
        )
        redis_client.hset(
            code_key,
            mapping={
                "code_hash": code_hash,
                "salt": salt_hex,
                "attempts": "0",
                "issued_at": str(int(time.time())),
            },
        )
        redis_client.expire(code_key, AUTH_SMS_CODE_TTL_SECONDS)
    except HTTPException:
        raise
    except RedisError:
        raise HTTPException(status_code=503, detail="sms login unavailable")

    sent, detail = _send_sms_code_via_provider(phone, code)
    if not sent:
        try:
            redis_client.delete(code_key)
        except Exception:
            pass
        raise HTTPException(status_code=502, detail=f"sms send failed: {detail or 'unknown error'}")

    response = {
        "ok": True,
        "expires_in": AUTH_SMS_CODE_TTL_SECONDS,
        "resend_after": AUTH_SMS_RESEND_INTERVAL_SECONDS,
    }
    if AUTH_SMS_DEBUG_RETURN_CODE:
        response["debug_code"] = code
    return response


@app.post("/api/auth/sms/login", response_model=AuthSessionResponse)
async def auth_sms_login(payload: AuthSmsLoginRequest):
    """短信验证码登录"""
    client_id = _require_client_id(payload.client_id)
    if not _is_client_login_enabled(client_id):
        raise HTTPException(status_code=403, detail="login is disabled by admin for current client")
    if not _is_client_sms_login_enabled(client_id):
        raise HTTPException(status_code=403, detail="sms login is disabled by admin for current client")
    phone = _validate_phone_or_raise(payload.phone)
    code = _validate_sms_code_or_raise(payload.code)
    redis_client = _get_sms_redis_client()
    code_key = _sms_redis_key(f"code:{phone}")
    try:
        code_data = redis_client.hgetall(code_key)
        if not code_data:
            raise HTTPException(status_code=400, detail="sms code has expired")
        attempts = int(redis_client.hincrby(code_key, "attempts", 1))
        if attempts > AUTH_SMS_VERIFY_MAX_ATTEMPTS:
            redis_client.delete(code_key)
            raise HTTPException(status_code=429, detail="sms code attempts exceeded")
    except HTTPException:
        raise
    except RedisError:
        raise HTTPException(status_code=503, detail="sms login unavailable")

    expected_hash = str(code_data.get("code_hash") or "").strip()
    salt_hex = str(code_data.get("salt") or "").strip()
    if not expected_hash or not salt_hex:
        try:
            redis_client.delete(code_key)
        except Exception:
            pass
        raise HTTPException(status_code=400, detail="sms code has expired")

    actual_hash = _hash_sms_code(code, salt_hex)
    if not secrets.compare_digest(actual_hash, expected_hash):
        raise HTTPException(status_code=401, detail="sms code is incorrect")

    try:
        redis_client.delete(code_key)
    except RedisError:
        raise HTTPException(status_code=503, detail="sms login unavailable")

    user_id, user = _upsert_user_by_phone(phone)
    _bind_client_to_user(user_id, client_id)
    users_db[user_id] = user
    _persist_auth_users_db()
    token, expires_at = _create_auth_session(user_id, client_id)
    return _build_auth_session_response(user, token, expires_at)


@app.get("/api/auth/me", response_model=AuthMeResponse)
async def auth_me(request: Request, client_id: str | None = None):
    """获取当前会话用户，并可选绑定新的客户端ID"""
    user, _ = _resolve_user_by_request(request)
    if not user:
        return AuthMeResponse(authenticated=False, user=None)

    normalized_client_id = _normalize_client_id(client_id)
    if normalized_client_id:
        user_id = str(user.get("id") or "").strip()
        before = _get_user_client_ids(user_id)
        _bind_client_to_user(user_id, normalized_client_id)
        after = _get_user_client_ids(user_id)
        if before != after:
            _persist_auth_users_db()
        user = users_db.get(user_id, user)
    return AuthMeResponse(authenticated=True, user=_user_to_profile(user))


@app.post("/api/auth/logout")
async def auth_logout(request: Request):
    """退出当前会话"""
    token = _extract_auth_token(request)
    if token:
        with AUTH_SESSIONS_LOCK:
            sessions_db.pop(token, None)
    return {"ok": True}


@app.get("/api/auth/github/login")
async def auth_github_login(client_id: str, return_url: str | None = None):
    """鐢熸垚 GitHub OAuth 鎺堟潈鍦板潃"""
    normalized_client_id = _require_client_id(client_id)
    if not _is_client_login_enabled(normalized_client_id):
        raise HTTPException(status_code=403, detail="login is disabled by admin for current client")
    if not _is_github_oauth_enabled():
        raise HTTPException(status_code=503, detail="github oauth is not configured")
    normalized_return_url = _normalize_return_url(return_url) or _normalize_return_url(AUTH_DEFAULT_RETURN_URL)
    state = _save_github_oauth_state(normalized_client_id, normalized_return_url or "")
    query = {
        "client_id": AUTH_GITHUB_CLIENT_ID,
        "scope": AUTH_GITHUB_SCOPE,
        "state": state,
    }
    if AUTH_GITHUB_CALLBACK_URL:
        query["redirect_uri"] = AUTH_GITHUB_CALLBACK_URL
    authorize_url = f"{AUTH_GITHUB_AUTHORIZE_URL}?{urllib.parse.urlencode(query)}"
    return {
        "oauth_enabled": True,
        "authorize_url": authorize_url,
    }


@app.get("/api/auth/github/callback")
async def auth_github_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
):
    """澶勭悊 GitHub OAuth 鍥炶皟"""
    state_payload = _pop_github_oauth_state(state)
    fallback_return_url = _normalize_return_url(AUTH_DEFAULT_RETURN_URL) or "http://localhost:8080/"
    return_url = fallback_return_url
    if isinstance(state_payload, dict):
        return_url = _normalize_return_url(state_payload.get("return_url")) or fallback_return_url
    if not state_payload:
        redirect_url = _build_github_callback_redirect(return_url, error="invalid_state")
        return RedirectResponse(url=redirect_url, status_code=302)

    oauth_error = str(error_description or error or "").strip()
    if oauth_error:
        redirect_url = _build_github_callback_redirect(return_url, error=oauth_error)
        return RedirectResponse(url=redirect_url, status_code=302)

    normalized_code = str(code or "").strip()
    if not normalized_code:
        redirect_url = _build_github_callback_redirect(return_url, error="missing_code")
        return RedirectResponse(url=redirect_url, status_code=302)

    client_id = _normalize_client_id(state_payload.get("client_id"))
    if not client_id:
        redirect_url = _build_github_callback_redirect(return_url, error="missing_client_id")
        return RedirectResponse(url=redirect_url, status_code=302)
    if not _is_client_login_enabled(client_id):
        redirect_url = _build_github_callback_redirect(return_url, error="login_disabled")
        return RedirectResponse(url=redirect_url, status_code=302)

    try:
        access_token = _exchange_github_oauth_code(normalized_code, str(state or ""))
        identity = _fetch_github_identity(access_token)
        user_id, user = _upsert_user_by_github_identity(identity)
        _bind_client_to_user(user_id, client_id)
        _persist_auth_users_db()
        token, _ = _create_auth_session(user_id, client_id)
    except HTTPException as exc:
        redirect_url = _build_github_callback_redirect(return_url, error=str(exc.detail or "github_login_failed"))
        return RedirectResponse(url=redirect_url, status_code=302)
    except Exception:
        redirect_url = _build_github_callback_redirect(return_url, error="github_login_failed")
        return RedirectResponse(url=redirect_url, status_code=302)

    redirect_url = _build_github_callback_redirect(return_url, token=token)
    return RedirectResponse(url=redirect_url, status_code=302)


@app.post("/api/upload")
async def upload_file(client_id: str | None = None, file: UploadFile = File(...)):
    """上传ZIP文件"""
    normalized_name = str(file.filename or "").strip()
    if not normalized_name.lower().endswith('.zip'):
        raise HTTPException(status_code=400, detail="只支持ZIP文件")
    
    max_size_mb = _get_upload_max_size_mb(client_id)
    max_size_bytes = max_size_mb * 1024 * 1024
    file_id = str(uuid.uuid4())
    filename = f"{file_id}_{normalized_name}"
    file_path = BACKEND_UPLOAD_DIR / filename
    total_size = 0
    
    try:
        with open(file_path, "wb") as buffer:
            while True:
                chunk = await file.read(UPLOAD_STREAM_CHUNK_SIZE)
                if not chunk:
                    break
                total_size += len(chunk)
                if total_size > max_size_bytes:
                    raise HTTPException(status_code=413, detail=f"upload file exceeds limit: {max_size_mb}MB")
                buffer.write(chunk)
    except HTTPException:
        if file_path.exists():
            file_path.unlink(missing_ok=True)
        raise
    except Exception as e:
        if file_path.exists():
            file_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"文件保存失败: {str(e)}")
    
    finally:
        try:
            await file.close()
        except Exception:
            pass
    
    return {
        "filename": filename,
        "original_name": normalized_name,
        "size": total_size,
        "message": "上传成功"
    }


@app.post("/api/upload-html")
async def upload_html(client_id: str | None = None, file: UploadFile = File(...)):
    """上传HTML文件"""
    normalized_name = str(file.filename or "").strip()
    filename_lower = normalized_name.lower()
    if not (filename_lower.endswith(".html") or filename_lower.endswith(".htm")):
        raise HTTPException(status_code=400, detail="只支持HTML文件")

    max_size_mb = _get_upload_max_size_mb(client_id)
    max_size_bytes = max_size_mb * 1024 * 1024
    file_id = str(uuid.uuid4())
    filename = f"{file_id}_{normalized_name}"
    file_path = BACKEND_UPLOAD_DIR / filename
    total_size = 0

    try:
        with open(file_path, "wb") as buffer:
            while True:
                chunk = await file.read(UPLOAD_STREAM_CHUNK_SIZE)
                if not chunk:
                    break
                total_size += len(chunk)
                if total_size > max_size_bytes:
                    raise HTTPException(status_code=413, detail=f"upload file exceeds limit: {max_size_mb}MB")
                buffer.write(chunk)
    except HTTPException:
        if file_path.exists():
            file_path.unlink(missing_ok=True)
        raise
    except Exception as e:
        if file_path.exists():
            file_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"文件保存失败: {str(e)}")

    finally:
        try:
            await file.close()
        except Exception:
            pass

    return {
        "filename": filename,
        "original_name": normalized_name,
        "size": total_size,
        "message": "上传成功"
    }


@app.post("/api/external-links/scan")
async def scan_external_links(payload: dict = Body(...)):
    mode = str(payload.get("mode", "") or "").strip().lower()
    filename = str(payload.get("filename", "") or "").strip()
    html_filename = str(payload.get("html_filename", "") or "").strip()

    if mode not in {"convert", "html"}:
        if filename.lower().endswith(".zip"):
            mode = "convert"
        elif filename.lower().endswith((".html", ".htm")):
            mode = "html"
        elif html_filename.lower().endswith((".html", ".htm")):
            mode = "html"

    if mode == "convert":
        if not filename:
            raise HTTPException(status_code=400, detail="filename is required for convert mode")
        if not filename.lower().endswith(".zip"):
            raise HTTPException(status_code=400, detail="convert mode requires zip filename")
        zip_path = _resolve_upload_file(filename)
        if not zip_path.exists():
            raise HTTPException(status_code=404, detail="uploaded zip file not found")
        items = _scan_external_links_in_zip(zip_path)
        return {"mode": "convert", "count": len(items), "items": items}

    if mode == "html":
        html_name = html_filename or filename
        if not html_name:
            raise HTTPException(status_code=400, detail="html filename is required for html mode")
        if not html_name.lower().endswith((".html", ".htm")):
            raise HTTPException(status_code=400, detail="html mode requires .html/.htm filename")
        html_path = _resolve_upload_file(html_name)
        if not html_path.exists():
            raise HTTPException(status_code=404, detail="uploaded html file not found")
        items = _scan_external_links_in_html(html_path)
        return {"mode": "html", "count": len(items), "items": items}

    raise HTTPException(status_code=400, detail="mode must be convert or html")


@app.post("/api/upload-icon")
async def upload_icon(file: UploadFile = File(...)):
    """上传应用图标（PNG格式，1024x1024）"""
    if not file.filename.lower().endswith('.png'):
        raise HTTPException(status_code=400, detail="只支持PNG格式图标")
    
    file_id = str(uuid.uuid4())
    # 保存为 logo.png 格式，便于构建脚本识别
    filename = f"{file_id}_logo.png"
    file_path = BACKEND_UPLOAD_DIR / filename
    
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"图标保存失败: {str(e)}")
    
    file_size = file_path.stat().st_size
    
    return {
        "filename": filename,
        "original_name": file.filename,
        "size": file_size,
        "message": "图标上传成功"
    }


@app.get("/api/quick-generate/icon", include_in_schema=False)
async def quick_generate_icon():
    """Quick Generate default icon preview."""
    icon_path = _resolve_quick_generate_icon_path()
    if not icon_path:
        # Provide a deterministic placeholder icon instead of failing hard.
        icon_path = TASKS_DIR / "quick-generate-placeholder.png"
        if not icon_path.exists():
            try:
                _write_quick_generate_placeholder_icon(icon_path)
            except Exception:
                raise HTTPException(status_code=404, detail="Not Found")
    return FileResponse(
        path=str(icon_path),
        filename="demoLogo.png",
        media_type="image/png",
    )


@app.post("/api/upload-keystore")
async def upload_keystore(file: UploadFile = File(...)):
    """上传签名文件（.jks / .keystore）"""
    filename_lower = (file.filename or "").lower()
    if not (filename_lower.endswith(".jks") or filename_lower.endswith(".keystore")):
        raise HTTPException(status_code=400, detail="仅支持 .jks 或 .keystore 文件")

    file_id = str(uuid.uuid4())
    filename = f"{file_id}_{file.filename}"
    file_path = BACKEND_UPLOAD_DIR / filename

    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"上传密钥文件失败: {str(e)}")

    file_size = file_path.stat().st_size

    return {
        "filename": filename,
        "original_name": file.filename,
        "size": file_size,
        "message": "密钥文件上传成功"
    }



@app.post("/api/tasks", response_model=BuildTaskResponse)
async def create_task(task_data: BuildTaskCreate):
    """创建构建任务"""
    task_id = str(uuid.uuid4())
    now = datetime.now()
    client_id = _require_client_id(task_data.client_id)
    declared_use_case = _normalize_declared_use_case(task_data.declared_use_case)
    _validate_task_compliance_or_raise(task_data.compliance_ack, declared_use_case)

    mode = (task_data.mode or "convert").strip().lower()
    if mode not in {"convert", "web", "html", "desktop"}:
        raise HTTPException(status_code=400, detail="mode must be convert, web, html, or desktop")
    web_url = None
    if mode == "web":
        if not _is_web_link_mode_enabled(client_id):
            raise HTTPException(status_code=403, detail="web mode is disabled by admin")
        web_url = str(task_data.web_url or "").strip()
        if not web_url:
            raise HTTPException(status_code=400, detail="web_url is required for web mode")
    if mode == "desktop":
        if not _is_desktop_mode_enabled(client_id):
            raise HTTPException(status_code=403, detail="desktop mode is disabled by admin")
    html_filename = None
    if mode == "html":
        html_filename = str(task_data.html_filename or "").strip()
        if not html_filename:
            raise HTTPException(status_code=400, detail="html_filename is required for html mode")

    if not RISK_REVIEW_ENABLED:
        _enforce_marketplace_policy_or_raise(
            client_id=client_id,
            app_name=task_data.config.app_name,
            package_name=task_data.config.package_name,
            declared_use_case=declared_use_case,
            web_url=web_url,
        )

    quick_generate = bool(task_data.quick_generate)
    if mode == "desktop" and quick_generate:
        raise HTTPException(status_code=400, detail="desktop mode does not support quick generate")
    quick_icon_path = None
    quickSharedKeystorePath = None
    if quick_generate:
        quick_icon_path = _resolve_quick_generate_icon_path()
        quickSharedKeystorePath = _ensureQuickGenerateSharedKeystore()
    
    # 验证复用的任务是否存在
    reuse_from = None if quick_generate else task_data.reuse_keystore_from
    if reuse_from:
        reuse_task = tasks_db.get(reuse_from)
        if not reuse_task:
            raise HTTPException(status_code=400, detail="要复用签名的任务不存在")
        _assert_task_owner(reuse_task, client_id)
    
    # 创建任务专属目录
    task_dir = TASKS_DIR / task_id
    task_input_dir = task_dir / "input"
    task_output_dir = task_dir / "output"
    task_keystore_dir = task_dir / "keystore"
    
    task_input_dir.mkdir(parents=True, exist_ok=True)
    task_output_dir.mkdir(parents=True, exist_ok=True)
    task_keystore_dir.mkdir(parents=True, exist_ok=True)

    effective_config = task_data.config
    
    # 移动ZIP文件到任务目录（仅 convert 模式）
    if mode in {"convert", "desktop"}:
        if not task_data.filename:
            raise HTTPException(status_code=400, detail="filename is required for zip-based mode")
        src_zip = BACKEND_UPLOAD_DIR / task_data.filename
        if not src_zip.exists():
            raise HTTPException(status_code=400, detail="ZIP文件不存在，请重新上传")
        detected_mode, detected_index_entry = _detect_zip_build_mode(src_zip)
        if detected_mode == "invalid":
            raise HTTPException(
                status_code=400,
                detail="ZIP中未检测到package.json，且未找到index.html，无法识别为Node.js或HTML项目",
            )
        dst_zip = _store_task_asset(task_id, task_input_dir, "project.zip", src_zip, move=True)
        if mode == "convert" and detected_mode == "html":
            dst_assets_dir = task_input_dir / "html_assets"
            _extract_html_assets_from_zip(dst_zip, detected_index_entry or "index.html", dst_assets_dir)
            dst_html = task_input_dir / "index.html"
            shutil.copy2(str(dst_assets_dir / "index.html"), str(dst_html))
            mode = "html"
            html_filename = "index.html"
    elif mode == "html":
        src_html = BACKEND_UPLOAD_DIR / html_filename
        if not src_html.exists():
            raise HTTPException(status_code=400, detail="HTML文件不存在，请重新上传")
        _persist_task_source_copy(task_id, "index.html", src_html)
        dst_html = task_input_dir / "index.html"
        shutil.move(str(src_html), str(dst_html))

    cdn_localize_urls = _normalize_cdn_localize_urls(task_data.cdn_localize_urls)
    cdn_localize_select_all = False
    if mode in {"convert", "html"}:
        cdn_localize_enabled = True if task_data.cdn_localize_enabled is None else bool(task_data.cdn_localize_enabled)
        cdn_localize_select_all = bool(getattr(task_data, "cdn_localize_select_all", False))
    else:
        cdn_localize_enabled = False
    if not cdn_localize_enabled:
        cdn_localize_urls = []
        cdn_localize_select_all = False
    elif cdn_localize_select_all:
        cdn_localize_urls = []

    cdn_localize_preprocessed = False
    cdn_localize_log_lines: list[str] = []
    if mode in {"convert", "html"}:
        if mode == "convert":
            _detach_working_task_asset(task_id, task_input_dir, "project.zip")
        elif mode == "html":
            _detach_working_task_asset(task_id, task_input_dir, "index.html")
        preprocess_result = _preprocess_task_cdn_localization(
            task_mode=mode,
            task_input_dir=task_input_dir,
            enabled=cdn_localize_enabled,
            selected_urls=cdn_localize_urls,
        )
        cdn_localize_preprocessed = bool(preprocess_result.get("preprocessed"))
        cdn_localize_log_lines = [str(item) for item in preprocess_result.get("log_lines", []) if str(item).strip()]

    if quick_generate:
        version_name, version_code = _alloc_quick_generate_versions()
        effective_config = AppConfig(
            app_name=QUICK_GENERATE_APP_NAME,
            package_name=QUICK_GENERATE_PACKAGE_NAME,
            version_name=version_name,
            version_code=version_code,
            output_format="apk",
            orientation="portrait",
            double_click_exit=True,
            status_bar_hidden=True,
            status_bar_style="light",
            status_bar_color="transparent",
            permissions=QUICK_GENERATE_PERMISSIONS,
            keystore_alias=QUICK_GENERATE_KEY_ALIAS,
            keystore_password=QUICK_GENERATE_KEYSTORE_PASSWORD,
            key_password=QUICK_GENERATE_KEY_PASSWORD,
        )
    
    # 移动图标文件到任务目录（如果有）
    icon_in_task = None
    if quick_generate:
        icon_path = quick_icon_path
        dst_icon = task_input_dir / "logo.png"
        if icon_path and icon_path.exists():
            shutil.copy2(str(icon_path), str(dst_icon))
        else:
            _write_quick_generate_placeholder_icon(dst_icon)
        _sync_task_asset_snapshot(task_id, task_input_dir, "logo.png")
        icon_in_task = "logo.png"
    elif task_data.icon_filename:
        src_icon = BACKEND_UPLOAD_DIR / task_data.icon_filename
        if src_icon.exists():
            _store_task_asset(task_id, task_input_dir, "logo.png", src_icon, move=True)
            icon_in_task = "logo.png"
    


    # 处理用户上传的签名密钥（如果有）
    keystore_in_task = None
    if quick_generate and quickSharedKeystorePath and quickSharedKeystorePath.exists():
        dst_keystore = task_keystore_dir / "release.keystore"
        shutil.copy2(str(quickSharedKeystorePath), str(dst_keystore))
        keystore_in_task = "release.keystore"
    elif (not quick_generate) and task_data.keystore_filename:
        src_keystore = BACKEND_UPLOAD_DIR / task_data.keystore_filename
        if not src_keystore.exists():
            raise HTTPException(status_code=400, detail="签名文件不存在，请重新上传")
        dst_keystore = task_keystore_dir / "release.keystore"
        shutil.move(str(src_keystore), str(dst_keystore))
        keystore_in_task = "release.keystore"
    # 复用之前任务的图标（如果没有新上传）
    if not icon_in_task and reuse_from:
        reuse_task = tasks_db.get(reuse_from)
        if reuse_task and reuse_task.icon_filename:
            src_icon = _resolve_task_asset_path(reuse_from, "logo.png")
            if src_icon.exists():
                _store_task_asset(task_id, task_input_dir, "logo.png", src_icon, move=False)
                icon_in_task = "logo.png"
    
    # 复用之前任务的签名密钥
    if reuse_from and not keystore_in_task:
        src_keystore = TASKS_DIR / reuse_from / "keystore" / "release.keystore"
        if src_keystore.exists():
            dst_keystore = task_keystore_dir / "release.keystore"
            shutil.copy2(str(src_keystore), str(dst_keystore))

    risk_scan_zip_path = task_input_dir / "project.zip"
    risk_scan_html_path = task_input_dir / "index.html"
    risk_scan = _scan_task_risk_inputs(
        client_id=client_id,
        app_name=effective_config.app_name,
        package_name=effective_config.package_name,
        declared_use_case=declared_use_case,
        web_url=web_url,
        zip_path=risk_scan_zip_path if risk_scan_zip_path.exists() else None,
        html_path=risk_scan_html_path if risk_scan_html_path.exists() else None,
    )
    risk_level = str(risk_scan.get("risk_level") or "normal").strip().lower()
    allowlisted_for_review = _is_risk_review_allowlisted(client_id)
    review_required = _requires_risk_review(client_id, risk_scan)
    review_status = (
        RISK_REVIEW_STATUS_PENDING
        if review_required
        else (RISK_REVIEW_STATUS_APPROVED if risk_level == "high" else RISK_REVIEW_STATUS_NOT_REQUIRED)
    )
    review_requested_at = now if review_required else None
    review_decision_at = now if (risk_level == "high" and not review_required) else None
    review_decision_by = "allowlist" if (risk_level == "high" and allowlisted_for_review and not review_required) else None
    review_note = "风险命中但已在放行名单内" if (risk_level == "high" and allowlisted_for_review and not review_required) else None
    pending_message = "命中高风险规则，等待管理人员审核放行" if review_required else "等待构建中"

    task = BuildTask(
        id=task_id,
        client_id=client_id,
        compliance_ack=bool(task_data.compliance_ack),
        declared_use_case=declared_use_case,
        quick_generate=quick_generate,
        mode=mode,
        web_url=web_url,
        filename="project.zip" if mode in {"convert", "desktop"} else None,
        html_filename="index.html" if mode == "html" else None,
        icon_filename=icon_in_task,
        keystore_filename=keystore_in_task,
        config=effective_config,
        status=BuildStatus.PENDING,
        created_at=now,
        updated_at=now,
        progress=0,
        message=pending_message,
        failure_diagnosis=create_idle_diagnosis(),
        reuse_keystore_from=reuse_from,
        cdn_localize_enabled=cdn_localize_enabled,
        cdn_localize_urls=cdn_localize_urls,
        cdn_localize_select_all=cdn_localize_select_all,
        cdn_localize_preprocessed=cdn_localize_preprocessed,
        risk_level=risk_level,
        risk_scan=risk_scan,
        review_required=review_required,
        review_status=review_status,
        review_requested_at=review_requested_at,
        review_decision_at=review_decision_at,
        review_decision_by=review_decision_by,
        review_note=review_note,
    )

    for line in cdn_localize_log_lines:
        _append_task_log(task, line)

    tasks_db[task_id] = task
    try:
        persist_tasks_db(force=True)
    except Exception:
        pass
    try:
        config_data = task.config.model_dump() if hasattr(task.config, "model_dump") else task.config.dict()
    except Exception:
        config_data = {}
    config_data["build_type"] = task.mode
    config_data["task_mode"] = task.mode
    if task.mode == "web" and task.web_url:
        config_data["web_url"] = task.web_url
    config_data.update(_build_task_risk_sync_meta(task))
    persisted_zip_path = get_persisted_task_asset_path(task_id, "project.zip")
    persisted_html_path = get_persisted_task_asset_path(task_id, "index.html")
    zip_path = persisted_zip_path if persisted_zip_path.exists() else _resolve_task_asset_path(task_id, "project.zip")
    html_path = persisted_html_path if persisted_html_path.exists() else _resolve_task_asset_path(task_id, "index.html")
    icon_path = _resolve_task_asset_path(task_id, "logo.png")
    zip_info = {
        "build_type": task.mode,
        "risk_level": task.risk_level,
        "review_required": bool(task.review_required),
        "review_status": str(task.review_status or RISK_REVIEW_STATUS_NOT_REQUIRED),
        "risk_hit_count": int(task.risk_scan.get("hit_count") or 0) if isinstance(task.risk_scan, dict) else 0,
    }
    if zip_path.exists():
        zip_info.update({"name": zip_path.name, "size": zip_path.stat().st_size})
    upload_task_assets(
        task_id,
        task.client_id or "",
        task.updated_at.isoformat(),
        zip_info,
        config_data,
        zip_path=str(zip_path) if zip_path.exists() else None,
        html_path=str(html_path) if html_path.exists() else None,
        icon_path=str(icon_path) if icon_path.exists() else None,
        keystore_path=None,
        keystore_info={},
    )
    flush_task_assets_queue()
    return task


@app.get("/api/tasks", response_model=List[BuildTaskListItemResponse], response_model_exclude_none=True)
async def list_tasks(client_id: str = None):
    """获取任务列表，按client_id筛选"""
    client_id = _require_client_id(client_id)
    current_user_id = _get_user_id_by_client_id(client_id)
    if current_user_id:
        allowed_client_ids = _get_user_client_ids(current_user_id)
        task_list = [task for task in tasks_db.values() if _normalize_client_id(task.client_id) in allowed_client_ids]
    else:
        task_list = [task for task in tasks_db.values() if task.client_id == client_id]
    task_list.sort(key=lambda task: (task.updated_at, task.created_at, task.id), reverse=True)
    for task in task_list:
        try:
            _schedule_task_failure_diagnosis(task.id, task, force=False)
        except Exception:
            pass
    return task_list


@app.get("/api/tasks/{task_id}", response_model=BuildTaskResponse)
async def get_task(task_id: str, client_id: str = None):
    """获取任务详情"""
    if task_id not in tasks_db:
        raise HTTPException(status_code=404, detail="任务不存在")
    client_id = _require_client_id(client_id)
    task = tasks_db[task_id]
    _assert_task_owner(task, client_id)
    try:
        _schedule_task_failure_diagnosis(task.id, task, force=False)
    except Exception:
        pass
    return task


@app.get("/api/risk-reviews/pending", response_model=List[BuildTaskListItemResponse], response_model_exclude_none=True)
async def list_pending_risk_reviews(request: Request, client_id: str | None = None, limit: int = 200):
    """获取待审核的高风险任务（管理端调用）。"""
    _require_risk_review_admin_access(request)
    normalized_client_id = _normalize_client_id(client_id)
    safe_limit = max(1, min(int(limit or 200), 500))
    items = []
    for task in tasks_db.values():
        if not bool(getattr(task, "review_required", False)):
            continue
        review_status = str(getattr(task, "review_status", "") or "").strip().lower()
        if review_status != RISK_REVIEW_STATUS_PENDING:
            continue
        if normalized_client_id and _normalize_client_id(getattr(task, "client_id", "")) != normalized_client_id:
            continue
        items.append(task)
    items.sort(key=lambda item: (item.updated_at, item.created_at, item.id), reverse=True)
    return items[:safe_limit]


@app.post("/api/risk-reviews/{task_id}/approve", response_model=BuildTaskResponse)
async def approve_risk_review_task(task_id: str, request: Request, payload: dict | None = Body(default=None)):
    """放行高风险任务（管理端调用）。"""
    reviewer = _require_risk_review_admin_access(request)
    if task_id not in tasks_db:
        raise HTTPException(status_code=404, detail="任务不存在")
    task = tasks_db[task_id]
    review_payload = payload if isinstance(payload, dict) else {}
    review_note = str(review_payload.get("note") or "").strip()
    review_operator = str(review_payload.get("reviewer") or "").strip() or reviewer
    now = datetime.now()
    task.review_required = True if str(getattr(task, "risk_level", "") or "").strip().lower() == "high" else bool(task.review_required)
    task.review_status = RISK_REVIEW_STATUS_APPROVED
    if not task.review_requested_at:
        task.review_requested_at = now
    task.review_decision_at = now
    task.review_decision_by = review_operator
    task.review_note = review_note or "管理员审核通过"
    if task.status == BuildStatus.PENDING:
        task.message = "风险审核已通过，可启动构建"
    task.updated_at = now
    try:
        persist_tasks_db(force=True)
    except Exception:
        pass
    try:
        _sync_task_risk_review_to_admin(task_id, task)
    except Exception:
        pass
    return task


@app.post("/api/risk-reviews/{task_id}/reject", response_model=BuildTaskResponse)
async def reject_risk_review_task(task_id: str, request: Request, payload: dict | None = Body(default=None)):
    """驳回高风险任务（管理端调用）。"""
    reviewer = _require_risk_review_admin_access(request)
    if task_id not in tasks_db:
        raise HTTPException(status_code=404, detail="任务不存在")
    task = tasks_db[task_id]
    review_payload = payload if isinstance(payload, dict) else {}
    review_note = str(review_payload.get("note") or "").strip()
    review_operator = str(review_payload.get("reviewer") or "").strip() or reviewer
    now = datetime.now()
    task.review_required = True
    task.review_status = RISK_REVIEW_STATUS_REJECTED
    if not task.review_requested_at:
        task.review_requested_at = now
    task.review_decision_at = now
    task.review_decision_by = review_operator
    task.review_note = review_note or "管理员审核驳回"
    if task.status == BuildStatus.PENDING:
        task.message = "风险审核未通过，任务已冻结"
    task.updated_at = now
    try:
        persist_tasks_db(force=True)
    except Exception:
        pass
    try:
        _sync_task_risk_review_to_admin(task_id, task)
    except Exception:
        pass
    return task


@app.delete("/api/tasks/{task_id}")
async def delete_task(task_id: str, client_id: str = None):
    """删除任务"""
    if task_id not in tasks_db:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    task = tasks_db[task_id]
    client_id = _require_client_id(client_id)
    _assert_task_owner(task, client_id)
    
    del tasks_db[task_id]
    try:
        persist_tasks_db(force=True)
    except Exception:
        pass

    def _cleanup_task_files(task_id: str) -> None:
        try:
            cleanup_task_generated_artifacts(
                task_id,
                getattr(task, "mode", "convert"),
                output_filename=getattr(task, "output_filename", None),
                remove_backend_output=True,
            )
        except Exception:
            pass
        try:
            task_dir = TASKS_DIR / task_id
            if task_dir.exists():
                shutil.rmtree(task_dir)
        except Exception:
            pass
        try:
            delete_task_asset_dir(task_id)
        except Exception:
            pass
        try:
            log_file = LOGS_DIR / f"{task_id}.log"
            if log_file.exists():
                log_file.unlink()
        except Exception:
            pass

    threading.Thread(target=_cleanup_task_files, args=(task_id,), daemon=True).start()
    return {"message": "任务已删除"}


@app.post("/api/tasks/cancel-running")
async def cancel_running_tasks(payload: dict):
    client_id = _require_client_id(payload.get("client_id"))
    runner = get_task_runner()
    current_user_id = _get_user_id_by_client_id(client_id)
    if current_user_id:
        target_client_ids = _get_user_client_ids(current_user_id) or {client_id}
    else:
        target_client_ids = {client_id}
    canceled_set: set[str] = set()
    for current_client_id in target_client_ids:
        canceled_items = runner.cancel_running_tasks(current_client_id)
        for task_id in canceled_items:
            canceled_set.add(str(task_id))
    return {"canceled": sorted(canceled_set)}


@app.post("/api/tasks/{task_id}/start", response_model=BuildTaskResponse)
async def start_task(task_id: str, client_id: str = None):
    """开始构建任务"""
    if task_id not in tasks_db:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    task = tasks_db[task_id]
    client_id = _require_client_id(client_id)
    _assert_task_owner(task, client_id)
    
    if task.status != BuildStatus.PENDING:
        raise HTTPException(status_code=400, detail="任务状态不允许启动")
    if not _is_task_review_approved(task):
        review_status = str(getattr(task, "review_status", "") or "").strip().lower()
        if review_status == RISK_REVIEW_STATUS_REJECTED:
            raise HTTPException(status_code=403, detail="task was rejected by admin risk review")
        raise HTTPException(status_code=403, detail="task is pending admin risk review")

    if env_setup.is_required():
        status = env_setup.get_status()
        if task.mode == "desktop":
            node_ready = bool(str(status.get("paths", {}).get("node", "")).strip())
            if not node_ready:
                raise HTTPException(status_code=503, detail="Node.js environment is not ready for desktop mode")
        elif not status["ready"]:
            detail = status.get("error") or "Build environment is not ready"
            raise HTTPException(status_code=503, detail=detail)
    
    # 更新任务状态
    task.status = BuildStatus.PROCESSING
    task.progress = 5
    task.message = "正在启动构建..."
    task.failure_diagnosis = create_idle_diagnosis()
    task.updated_at = datetime.now()

    try:
        config_data = task.config.model_dump() if hasattr(task.config, 'model_dump') else task.config.dict()
    except Exception:
        config_data = {}
    config_data["build_type"] = task.mode
    config_data["task_mode"] = task.mode
    if task.mode == "web" and task.web_url:
        config_data["web_url"] = task.web_url
    config_data.update(_build_task_risk_sync_meta(task))
    task_input_dir = TASKS_DIR / task_id / "input"
    ensure_task_input_assets(task_id, task_input_dir)
    persisted_zip_path = get_persisted_task_asset_path(task_id, "project.zip")
    persisted_html_path = get_persisted_task_asset_path(task_id, "index.html")
    zip_path = persisted_zip_path if persisted_zip_path.exists() else _resolve_task_asset_path(task_id, "project.zip")
    html_path = persisted_html_path if persisted_html_path.exists() else _resolve_task_asset_path(task_id, "index.html")
    icon_path = _resolve_task_asset_path(task_id, "logo.png")
    zip_info = {
        "build_type": task.mode,
        "risk_level": task.risk_level,
        "review_required": bool(task.review_required),
        "review_status": str(task.review_status or RISK_REVIEW_STATUS_NOT_REQUIRED),
        "risk_hit_count": int(task.risk_scan.get("hit_count") or 0) if isinstance(task.risk_scan, dict) else 0,
    }
    if zip_path.exists():
        zip_info.update({"name": zip_path.name, "size": zip_path.stat().st_size})
    report_task_start(task_id, task.client_id or '', task.updated_at.isoformat(), zip_info, config_data)
    upload_task_assets(
        task_id,
        task.client_id or "",
        task.updated_at.isoformat(),
        zip_info,
        config_data,
        zip_path=str(zip_path) if zip_path.exists() else None,
        html_path=str(html_path) if html_path.exists() else None,
        icon_path=str(icon_path) if icon_path.exists() else None,
        keystore_path=None,
        keystore_info={},
    )
    flush_task_assets_queue()

    
    # 启动后台构建任务
    try:
        runner = get_task_runner()
        runner.start_build(task_id)
    except Exception as e:
        task.status = BuildStatus.FAILED
        task.message = f"启动构建失败: {str(e)}"
        task.failure_diagnosis = create_failed_diagnosis(str(e), analyzed_log_lines=0)
        task.updated_at = datetime.now()
    try:
        persist_tasks_db(force=True)
    except Exception:
        pass
    try:
        _sync_task_risk_review_to_admin(task_id, task)
    except Exception:
        pass

    return task


@app.post("/api/tasks/{task_id}/cancel", response_model=BuildTaskResponse)
async def cancel_task(task_id: str, payload: dict = Body(...)):
    """取消指定任务"""
    if task_id not in tasks_db:
        raise HTTPException(status_code=404, detail="任务不存在")
    task = tasks_db[task_id]
    client_id = _require_client_id(payload.get("client_id"))
    _assert_task_owner(task, client_id)
    runner = get_task_runner()
    ok = runner.cancel_task(task_id, _normalize_client_id(task.client_id))
    if not ok:
        raise HTTPException(status_code=400, detail="任务无法取消")
    try:
        persist_tasks_db(force=True)
    except Exception:
        pass
    return task


@app.get("/api/icon/{task_id}")
async def get_icon(task_id: str, client_id: str = None):
    """获取任务的图标文件"""
    if task_id not in tasks_db:
        raise HTTPException(status_code=404, detail="任务不存在")
    client_id = _require_client_id(client_id)
    task = tasks_db[task_id]
    _assert_task_owner(task, client_id)
    # 先从任务目录查找
    task_icon = _resolve_task_asset_path(task_id, "logo.png")
    if task_icon.exists():
        return FileResponse(
            path=str(task_icon),
            filename="logo.png",
            media_type="image/png"
        )
    
    # 兼容：从uploads目录查找（旧格式）
    upload_icon = BACKEND_UPLOAD_DIR / f"{task_id}_logo.png"
    if upload_icon.exists():
        return FileResponse(
            path=str(upload_icon),
            filename="logo.png",
            media_type="image/png"
        )
    
    raise HTTPException(status_code=404, detail="图标文件不存在")


@app.get("/api/download/{task_id}")
async def download_file(task_id: str, client_id: str = None):
    """下载构建结果"""
    if task_id not in tasks_db:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    task = tasks_db[task_id]
    client_id = _require_client_id(client_id)
    _assert_task_owner(task, client_id)
    
    if task.status != BuildStatus.SUCCESS:
        raise HTTPException(status_code=400, detail="任务未完成或构建失败")
    
    if not task.output_filename:
        if _should_cleanup_desktop_output_on_download(task):
            raise HTTPException(status_code=410, detail=_get_desktop_output_unavailable_detail(task))
        if should_auto_clean_build_outputs():
            raise HTTPException(status_code=410, detail="构建产物已按服务器策略自动清理")
        raise HTTPException(status_code=404, detail="未找到构建输出文件")
    
    output_filename = str(task.output_filename)
    file_path = BACKEND_OUTPUT_DIR / output_filename
    
    if not file_path.exists():
        if _should_cleanup_desktop_output_on_download(task):
            consumed_output = _consume_desktop_output(task, "page_exit")
            if consumed_output:
                cleanup_task_generated_artifacts(
                    task.id,
                    getattr(task, "mode", "desktop"),
                    output_filename=consumed_output,
                    remove_backend_output=True,
                )
            raise HTTPException(status_code=410, detail=_get_desktop_output_unavailable_detail(task))
        if should_auto_clean_build_outputs():
            raise HTTPException(status_code=410, detail="构建产物已按服务器策略自动清理")
        raise HTTPException(status_code=404, detail="构建文件不存在")

    # 根据文件类型设置正确的 Content-Type
    suffix = file_path.suffix.lower()
    if suffix == ".apk":
        media_type = "application/vnd.android.package-archive"
    elif suffix == ".exe":
        media_type = "application/vnd.microsoft.portable-executable"
    else:
        media_type = "application/octet-stream"

    background_task = None
    if _should_cleanup_desktop_output_on_download(task):
        consumed_output = _consume_desktop_output(task, "download")
        if consumed_output:
            output_filename = consumed_output
            background_task = BackgroundTask(
                cleanup_task_generated_artifacts,
                task.id,
                getattr(task, "mode", "desktop"),
                output_filename=consumed_output,
                remove_backend_output=True,
            )

    return FileResponse(
        path=str(file_path),
        filename=output_filename,
        media_type=media_type,
        background=background_task,
    )


@app.post("/api/tasks/desktop-output/release")
async def release_desktop_outputs(client_id: str = None):
    client_id = _require_client_id(client_id)
    current_user_id = _get_user_id_by_client_id(client_id)
    if current_user_id:
        allowed_client_ids = _get_user_client_ids(current_user_id) or {client_id}
    else:
        allowed_client_ids = {client_id}

    released = 0
    for task in list(tasks_db.values()):
        if _normalize_client_id(getattr(task, "client_id", "")) not in allowed_client_ids:
            continue
        if str(getattr(task, "mode", "") or "").strip().lower() != "desktop":
            continue
        if getattr(task, "status", None) != BuildStatus.SUCCESS:
            continue
        output_name = _consume_desktop_output(task, "page_exit")
        if not output_name:
            continue
        cleanup_task_generated_artifacts(
            task.id,
            getattr(task, "mode", "desktop"),
            output_filename=output_name,
            remove_backend_output=True,
        )
        released += 1

    return {"enabled": True, "released": released}


@app.get("/api/keystore/{task_id}")
async def download_keystore(task_id: str, client_id: str = None):
    """下载签名密钥(keystore)"""
    if task_id not in tasks_db:
        raise HTTPException(status_code=404, detail="任务不存在")

    task = tasks_db[task_id]
    client_id = _require_client_id(client_id)
    _assert_task_owner(task, client_id)

    if task.status != BuildStatus.SUCCESS:
        raise HTTPException(status_code=400, detail="任务未完成或构建失败")

    keystore_path = TASKS_DIR / task_id / "keystore" / "release.keystore"
    if not keystore_path.exists():
        raise HTTPException(status_code=404, detail="签名密钥不存在")

    app_name = _safe_filename(getattr(task.config, "app_name", "") or "app")
    filename = f"{app_name}-release.keystore"

    return FileResponse(
        path=str(keystore_path),
        filename=filename,
        media_type="application/octet-stream",
    )


@app.post("/api/tasks/{task_id}/retry", response_model=BuildTaskResponse)
async def retry_task(task_id: str, client_id: str = None):
    """重试失败的构建任务"""
    if task_id not in tasks_db:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    task = tasks_db[task_id]
    client_id = _require_client_id(client_id)
    _assert_task_owner(task, client_id)
    
    if task.status not in [BuildStatus.FAILED, BuildStatus.SUCCESS]:
        raise HTTPException(status_code=400, detail="只能重试失败或已完成的任务")
    
    # 重置任务状态
    previous_output_filename = task.output_filename
    task.status = BuildStatus.PENDING
    task.progress = 0
    task.message = "任务已重置，等待重新构建"
    task.logs = []
    task.failure_diagnosis = create_idle_diagnosis()
    task.download_url = None
    task.output_filename = None
    task.updated_at = datetime.now()
    try:
        cleanup_task_generated_artifacts(
            task_id,
            getattr(task, "mode", "convert"),
            output_filename=previous_output_filename,
            remove_backend_output=True,
        )
    except Exception:
        pass
    try:
        persist_tasks_db(force=True)
    except Exception:
        pass
    try:
        _sync_task_risk_review_to_admin(task_id, task)
    except Exception:
        pass

    return task


@app.put("/api/tasks/{task_id}", response_model=BuildTaskResponse)
async def update_task(task_id: str, update_data: UpdateTaskRequest):
    """更新已完成的任务（用于发布新版本）"""
    if task_id not in tasks_db:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    task = tasks_db[task_id]
    client_id = _require_client_id(update_data.client_id)
    _assert_task_owner(task, client_id)
    
    if task.status != BuildStatus.SUCCESS:
        raise HTTPException(status_code=400, detail="只能更新已成功的任务")
    
    # 验证版本号必须递增
    if update_data.version_code <= task.config.version_code:
        raise HTTPException(status_code=400, detail=f"版本号必须大于 {task.config.version_code}")
    
    # 获取任务目录
    task_dir = TASKS_DIR / task_id
    task_input_dir = task_dir / "input"
    task_output_dir = task_dir / "output"
    task_input_dir.mkdir(parents=True, exist_ok=True)
    task_output_dir.mkdir(parents=True, exist_ok=True)
    previous_output_filename = task.output_filename
    
    # 清理output目录
    if task_output_dir.exists():
        for f in task_output_dir.iterdir():
            if f.is_file():
                f.unlink()
    
    # 如果有新的ZIP文件，替换旧的（convert 模式）
    if update_data.filename:
        src_zip = BACKEND_UPLOAD_DIR / update_data.filename
        if src_zip.exists():
            dst_zip = _store_task_asset(task_id, task_input_dir, "project.zip", src_zip, move=True)
            if task.mode == "html":
                index_entry = _pick_zip_index_entry(dst_zip)
                if not index_entry:
                    raise HTTPException(status_code=400, detail="ZIP中未找到 index.html")
                dst_html = task_input_dir / "index.html"
                if dst_html.exists():
                    dst_html.unlink()
                dst_assets_dir = task_input_dir / "html_assets"
                if dst_assets_dir.exists():
                    shutil.rmtree(dst_assets_dir, ignore_errors=True)
                _extract_html_assets_from_zip(dst_zip, index_entry, dst_assets_dir)
                shutil.copy2(str(dst_assets_dir / "index.html"), str(dst_html))
                task.html_filename = "index.html"

    # HTML 模式：替换 HTML 资源
    if task.mode == "html":
        if update_data.html_filename:
            src_html = BACKEND_UPLOAD_DIR / update_data.html_filename
            if src_html.exists():
                _persist_task_source_copy(task_id, "index.html", src_html)
                dst_html = task_input_dir / "index.html"
                if dst_html.exists():
                    dst_html.unlink()
                dst_assets_dir = task_input_dir / "html_assets"
                if dst_assets_dir.exists():
                    shutil.rmtree(dst_assets_dir, ignore_errors=True)
                shutil.move(str(src_html), str(dst_html))
                task.html_filename = "index.html"
    
    # 如果有新的图标，替换旧的
    if update_data.icon_filename:
        src_icon = BACKEND_UPLOAD_DIR / update_data.icon_filename
        if src_icon.exists():
            _store_task_asset(task_id, task_input_dir, "logo.png", src_icon, move=True)
            task.icon_filename = "logo.png"
    
    # 更新版本信息
    task.config.version_name = update_data.version_name
    task.config.version_code = update_data.version_code

    # 更新输出格式（可选）
    if update_data.output_format is not None:
        output_format = update_data.output_format.strip().lower()
        if output_format not in {"apk", "aab"}:
            raise HTTPException(status_code=400, detail="output_format 只支持 apk 或 aab")
        task.config.output_format = output_format

    style_updates = {}
    if update_data.orientation is not None:
        style_updates["orientation"] = update_data.orientation
    if update_data.double_click_exit is not None:
        style_updates["double_click_exit"] = update_data.double_click_exit
    if update_data.status_bar_hidden is not None:
        style_updates["status_bar_hidden"] = update_data.status_bar_hidden
    if update_data.status_bar_style is not None:
        style_updates["status_bar_style"] = update_data.status_bar_style
    if update_data.status_bar_color is not None:
        style_updates["status_bar_color"] = update_data.status_bar_color
    if update_data.webview_user_agent is not None:
        style_updates["webview_user_agent"] = update_data.webview_user_agent
    if update_data.download_mode is not None:
        style_updates["download_mode"] = update_data.download_mode
    if update_data.web_fill_mode is not None:
        style_updates["web_fill_mode"] = update_data.web_fill_mode
    if update_data.desktop_installer_mode is not None:
        style_updates["desktop_installer_mode"] = update_data.desktop_installer_mode
    if update_data.desktop_runtime is not None:
        style_updates["desktop_runtime"] = update_data.desktop_runtime
    if update_data.desktop_port is not None:
        style_updates["desktop_port"] = update_data.desktop_port
    if update_data.permissions is not None:
        style_updates["permissions"] = update_data.permissions
    if style_updates:
        try:
            config_data = task.config.model_dump() if hasattr(task.config, "model_dump") else task.config.dict()
            config_data.update(style_updates)
            task.config = AppConfig(**config_data)
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    cdn_localize_log_lines: list[str] = []
    if task.mode in {"convert", "html"}:
        if update_data.cdn_localize_enabled is not None:
            task.cdn_localize_enabled = bool(update_data.cdn_localize_enabled)
        if update_data.cdn_localize_select_all is not None:
            task.cdn_localize_select_all = bool(update_data.cdn_localize_select_all)
        if update_data.cdn_localize_urls is not None:
            normalized_urls = _normalize_cdn_localize_urls(update_data.cdn_localize_urls)
            if not bool(getattr(task, "cdn_localize_select_all", False)):
                task.cdn_localize_urls = normalized_urls
            if update_data.cdn_localize_enabled is None and normalized_urls:
                task.cdn_localize_enabled = True
        if not task.cdn_localize_enabled:
            task.cdn_localize_urls = []
            task.cdn_localize_select_all = False
        elif bool(getattr(task, "cdn_localize_select_all", False)):
            task.cdn_localize_urls = []
        if task.mode == "convert":
            _detach_working_task_asset(task_id, task_input_dir, "project.zip")
        elif task.mode == "html":
            _detach_working_task_asset(task_id, task_input_dir, "index.html")
        preprocess_result = _preprocess_task_cdn_localization(
            task_mode=task.mode,
            task_input_dir=task_input_dir,
            enabled=bool(task.cdn_localize_enabled),
            selected_urls=task.cdn_localize_urls,
        )
        task.cdn_localize_preprocessed = bool(preprocess_result.get("preprocessed"))
        cdn_localize_log_lines = [str(item) for item in preprocess_result.get("log_lines", []) if str(item).strip()]
    else:
        task.cdn_localize_enabled = False
        task.cdn_localize_urls = []
        task.cdn_localize_select_all = False
        task.cdn_localize_preprocessed = False

    if RISK_REVIEW_ENABLED:
        risk_scan_zip_path = task_input_dir / "project.zip"
        risk_scan_html_path = task_input_dir / "index.html"
        risk_scan = _scan_task_risk_inputs(
            client_id=client_id,
            app_name=getattr(task.config, "app_name", ""),
            package_name=getattr(task.config, "package_name", ""),
            declared_use_case=getattr(task, "declared_use_case", ""),
            web_url=getattr(task, "web_url", None),
            zip_path=risk_scan_zip_path if risk_scan_zip_path.exists() else None,
            html_path=risk_scan_html_path if risk_scan_html_path.exists() else None,
        )
        risk_level = str(risk_scan.get("risk_level") or "normal").strip().lower()
        allowlisted_for_review = _is_risk_review_allowlisted(client_id)
        review_required = _requires_risk_review(client_id, risk_scan)
        task.risk_level = risk_level
        task.risk_scan = risk_scan
        task.review_required = review_required
        if review_required:
            task.review_status = RISK_REVIEW_STATUS_PENDING
            task.review_requested_at = datetime.now()
            task.review_decision_at = None
            task.review_decision_by = None
            task.review_note = None
        elif risk_level == "high":
            task.review_status = RISK_REVIEW_STATUS_APPROVED
            if not task.review_requested_at:
                task.review_requested_at = datetime.now()
            task.review_decision_at = datetime.now()
            task.review_decision_by = "allowlist" if allowlisted_for_review else "system"
            task.review_note = "风险命中但已在放行名单内" if allowlisted_for_review else ""
        else:
            task.review_status = RISK_REVIEW_STATUS_NOT_REQUIRED
            task.review_requested_at = None
            task.review_decision_at = None
            task.review_decision_by = None
            task.review_note = None
    
    # 重置任务状态
    task.status = BuildStatus.PENDING
    task.progress = 0
    task.message = (
        "命中高风险规则，等待管理人员审核放行"
        if bool(getattr(task, "review_required", False))
        else f"版本更新至 {update_data.version_name}，等待构建"
    )
    task.logs = []
    task.failure_diagnosis = create_idle_diagnosis()
    for line in cdn_localize_log_lines:
        _append_task_log(task, line)
    task.download_url = None
    task.output_filename = None
    task.updated_at = datetime.now()
    try:
        cleanup_task_generated_artifacts(
            task_id,
            getattr(task, "mode", "convert"),
            output_filename=previous_output_filename,
            remove_backend_output=True,
        )
    except Exception:
        pass
    try:
        persist_tasks_db(force=True)
    except Exception:
        pass
    try:
        _sync_task_risk_review_to_admin(task_id, task)
    except Exception:
        pass

    return task


@app.get("/api/tasks/{task_id}/logs")
async def get_task_logs(task_id: str, lines: int = 100, client_id: str = None):
    """获取任务日志"""
    if task_id not in tasks_db:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    task = tasks_db[task_id]
    client_id = _require_client_id(client_id)
    _assert_task_owner(task, client_id)
    
    # 优先从内存中获取日志
    if hasattr(task, 'logs') and task.logs:
        logs = task.logs[-lines:] if len(task.logs) > lines else task.logs
        return {"logs": logs, "total": len(task.logs)}
    
    # 如果内存中没有，尝试从日志文件读取
    log_file = LOGS_DIR / f"{task_id}.log"
    if log_file.exists():
        with open(log_file, "r", encoding="utf-8") as f:
            all_logs = f.readlines()
            logs = [line.strip() for line in all_logs[-lines:]]
            return {"logs": logs, "total": len(all_logs)}
    
    return {"logs": [], "total": 0}


@app.get("/api/tasks/{task_id}/diagnosis")
async def get_task_diagnosis(
    task_id: str,
    client_id: str = None,
    refresh: bool = False,
    lang: str = "zh-CN",
):
    """获取构建失败智能诊断结果。"""
    if task_id not in tasks_db:
        raise HTTPException(status_code=404, detail="任务不存在")

    task = tasks_db[task_id]
    client_id = _require_client_id(client_id)
    _assert_task_owner(task, client_id)

    diagnosis = getattr(task, "failure_diagnosis", {})
    if not isinstance(diagnosis, dict):
        diagnosis = create_idle_diagnosis(language=lang)
        task.failure_diagnosis = diagnosis

    if task.status == BuildStatus.FAILED:
        requested_language = normalize_diag_language(lang)
        diagnosis_language = normalize_diag_language(diagnosis.get("language"))
        language_changed = diagnosis_language != requested_language
        should_force = bool(refresh)
        should_schedule = should_force or not diagnosis
        if should_schedule:
            _schedule_task_failure_diagnosis(
                task_id,
                task,
                force=should_force,
                language=requested_language,
            )
        elif language_changed and str(diagnosis.get("status", "")).strip().lower() == "succeeded":
            _schedule_task_failure_diagnosis(
                task_id,
                task,
                force=True,
                language=requested_language,
            )
        elif str(diagnosis.get("status", "")).strip().lower() not in {"running", "succeeded"}:
            _schedule_task_failure_diagnosis(
                task_id,
                task,
                force=False,
                language=requested_language,
            )

    return {
        "task_id": task_id,
        "task_status": task.status,
        "diagnosis": task.failure_diagnosis if isinstance(task.failure_diagnosis, dict) else create_idle_diagnosis(language=lang),
    }


@app.post("/api/tasks/{task_id}/diagnosis")
async def rerun_task_diagnosis(task_id: str, payload: dict = Body(...)):
    """手动重新触发构建失败智能诊断。"""
    if task_id not in tasks_db:
        raise HTTPException(status_code=404, detail="任务不存在")

    task = tasks_db[task_id]
    client_id = _require_client_id(payload.get("client_id"))
    _assert_task_owner(task, client_id)

    if task.status != BuildStatus.FAILED:
        raise HTTPException(status_code=400, detail="只有失败任务可以重新诊断")

    requested_language = normalize_diag_language(payload.get("lang"))
    _schedule_task_failure_diagnosis(task_id, task, force=True, language=requested_language)
    return {
        "task_id": task_id,
        "task_status": task.status,
        "diagnosis": task.failure_diagnosis if isinstance(task.failure_diagnosis, dict) else create_idle_diagnosis(language=requested_language),
    }


@app.get("/api/queue/status")
async def get_queue_status():
    """获取构建队列状态"""
    try:
        runner = get_task_runner()
        return runner.get_queue_status()
    except RuntimeError:
        return {
            "queue_size": 0,
            "running_count": 0,
            "running_tasks": [],
            "max_concurrent": 1
        }


@app.get("/api/env/status")
async def get_env_status():
    return env_setup.get_status()

@app.get("/env/status")
async def get_env_status_alt():
    return env_setup.get_status()


@app.get("/api/env/config")
async def get_env_config():
    return env_setup.get_config()


@app.get("/env/config")
async def get_env_config_alt():
    return env_setup.get_config()


@app.post("/api/env/config")
async def set_env_config(payload: dict = Body(...)):
    toolchain_root = str(payload.get("toolchain_root", "")).strip()
    migrate = bool(payload.get("migrate", False))
    npm_registry = str(payload.get("npm_registry", "")).strip()
    npm_proxy = str(payload.get("npm_proxy", "")).strip()
    npm_https_proxy = str(payload.get("npm_https_proxy", "")).strip()
    data_root = str(payload.get("data_root", "")).strip()
    node_path = str(payload.get("node_path", "")).strip()
    jdk_path = str(payload.get("jdk_path", "")).strip()
    android_path = str(payload.get("android_path", "")).strip()
    python_path = str(payload.get("python_path", "")).strip()
    try:
        return env_setup.set_config(
            toolchain_root,
            migrate=migrate,
            npm_registry=npm_registry,
            npm_proxy=npm_proxy,
            npm_https_proxy=npm_https_proxy,
            data_root=data_root,
            node_path=node_path,
            jdk_path=jdk_path,
            android_path=android_path,
            python_path=python_path,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/env/config")
async def set_env_config_alt(payload: dict = Body(...)):
    toolchain_root = str(payload.get("toolchain_root", "")).strip()
    migrate = bool(payload.get("migrate", False))
    npm_registry = str(payload.get("npm_registry", "")).strip()
    npm_proxy = str(payload.get("npm_proxy", "")).strip()
    npm_https_proxy = str(payload.get("npm_https_proxy", "")).strip()
    data_root = str(payload.get("data_root", "")).strip()
    node_path = str(payload.get("node_path", "")).strip()
    jdk_path = str(payload.get("jdk_path", "")).strip()
    android_path = str(payload.get("android_path", "")).strip()
    python_path = str(payload.get("python_path", "")).strip()
    try:
        return env_setup.set_config(
            toolchain_root,
            migrate=migrate,
            npm_registry=npm_registry,
            npm_proxy=npm_proxy,
            npm_https_proxy=npm_https_proxy,
            data_root=data_root,
            node_path=node_path,
            jdk_path=jdk_path,
            android_path=android_path,
            python_path=python_path,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.api_route("/api/env/prepare", methods=["GET", "POST"])
async def prepare_env(force: bool = False, payload: dict | None = Body(default=None)):
    if payload and isinstance(payload, dict) and "force" in payload:
        force = bool(payload.get("force"))
    return env_setup.prepare_env(force=force)


@app.api_route("/env/prepare", methods=["GET", "POST"])
async def prepare_env_alt(force: bool = False, payload: dict | None = Body(default=None)):
    if payload and isinstance(payload, dict) and "force" in payload:
        force = bool(payload.get("force"))
    return env_setup.prepare_env(force=force)


@app.get("/api/app/version")
async def get_app_version():
    return {"version": os.getenv("CONVERTAPK_APP_VERSION", "0.0.0")}


@app.get("/api/system/info")
async def system_info():
    return get_system_info()


@app.get("/api/github/repo-stats")
async def get_github_repo_stats():
    return _fetch_github_repo_stats()


def _probe_url(url: str, timeout: float = 5.0) -> tuple[bool, int | None, str]:
    try:
        request = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return True, response.getcode(), url
    except Exception:
        try:
            request = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return True, response.getcode(), url
        except Exception as exc:
            return False, None, str(exc)


@app.post("/api/url-probe")
async def url_probe(payload: dict = Body(...), client_id: str | None = None):
    probe_client_id = _normalize_client_id(client_id or payload.get("client_id"))
    if not _is_web_link_mode_enabled(probe_client_id):
        raise HTTPException(status_code=403, detail="web mode is disabled by admin")
    url = str(payload.get("url") or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="url required")
    if not (url.startswith("http://") or url.startswith("https://")):
        raise HTTPException(status_code=400, detail="url must include http/https")
    ok, status, detail = _probe_url(url)
    return {"ok": ok, "status": status, "detail": detail}


@app.get("/api/adminhub/announcements")
async def adminhub_announcements():
    return fetch_announcements() or []


@app.get("/api/adminhub/features")
async def adminhub_features(client_id: str | None = None):
    return _load_client_feature_flags(client_id=client_id)


@app.get("/api/adminhub/update-check")
async def adminhub_update_check(version: str = None):
    current_version = version or os.getenv("CONVERTAPK_APP_VERSION", "0.0.0")
    return check_update(current_version)


@app.post("/api/adminhub/feedback")
async def adminhub_feedback(
    client_id: str = Form(...),
    content: str = Form(...),
    device_info: str = Form(...),
    images: List[UploadFile] = File(default_factory=list),
):
    try:
        device_info_json = json.loads(device_info)
    except Exception:
        raise HTTPException(status_code=400, detail="device_info invalid")
    image_items = []
    for image in images:
        data = await image.read()
        image_items.append({
            "field": "images",
            "filename": image.filename or "image.png",
            "content_type": image.content_type or "application/octet-stream",
            "data": data,
        })
    ok = submit_feedback(client_id, content, device_info_json, image_items)
    if not ok:
        raise HTTPException(status_code=502, detail="feedback upload failed")
    return {"ok": True}


@app.on_event("startup")
async def startup_event():
    """应用启动时初始化"""
    init_task_runner(tasks_db, on_state_change=_onTasksStateChange)
    env_setup.start_background_check()
    print("[OK] 构建任务运行器已初始化（最大并发数: 1）")


@app.get("/{path:path}", include_in_schema=False)
async def frontend_fallback(path: str):
    if path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Not Found")
    frontend_dist = resolve_frontend_dist()
    if not frontend_dist:
        raise HTTPException(status_code=404, detail="Not Found")
    candidate = frontend_dist / path
    if candidate.exists() and candidate.is_file():
        return FileResponse(str(candidate))
    return FileResponse(str(frontend_dist / "index.html"))


if __name__ == "__main__":
    import uvicorn
    print("[APK Builder] APK转换服务启动中...")
    print("[API] 地址: http://localhost:8000")
    print("[Docs] 文档: http://localhost:8000/docs")
    port = int(os.getenv("CONVERTAPK_PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
