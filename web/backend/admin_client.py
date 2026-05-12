import json
import os
import urllib.parse
import urllib.request
import urllib.error
import time
import re
from typing import Any, Dict, List, Optional

_QUEUE_FILENAME = "upload-queue.json"
_ADMIN_STATUS_CACHE: dict = {"ok": True, "reason": "", "checked_at": 0.0}
_ADMIN_STATUS_TTL = 15.0
_FEATURE_FLAGS_CACHE: dict = {}
try:
    _FEATURE_FLAGS_TTL = max(0.0, float(os.getenv("ADMIN_FEATURE_FLAGS_CACHE_TTL", "5")))
except Exception:
    _FEATURE_FLAGS_TTL = 5.0


def _safe_path_segment(value: str, fallback: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in str(value or "").strip())
    return safe or fallback


def _build_task_input_asset_ref(task_id: str, filename: str) -> str:
    safe_task_id = _safe_path_segment(task_id, "task")
    safe_name = _safe_path_segment(filename, "file")
    return f"task-inputs/{safe_task_id}/{safe_name}"


def _merge_task_asset_meta(
    task_id: str,
    zip_info: Optional[Dict[str, Any]],
    zip_path: Optional[str] = None,
    icon_path: Optional[str] = None,
    html_path: Optional[str] = None,
) -> Dict[str, Any]:
    meta = dict(zip_info or {})
    if zip_path and os.path.exists(zip_path):
        meta.setdefault("zip_path", _build_task_input_asset_ref(task_id, "project.zip"))
        meta.setdefault("name", os.path.basename(zip_path))
        if "size" not in meta:
            try:
                meta["size"] = os.path.getsize(zip_path)
            except Exception:
                pass
    if (not zip_path or not os.path.exists(zip_path)) and html_path and os.path.exists(html_path):
        meta.setdefault("html_path", _build_task_input_asset_ref(task_id, "index.html"))
        html_info = meta.get("html_info")
        if not isinstance(html_info, dict):
            html_info = {}
        html_info.setdefault("name", os.path.basename(html_path))
        if "size" not in html_info:
            try:
                html_info["size"] = os.path.getsize(html_path)
            except Exception:
                pass
        meta["html_info"] = html_info
    if icon_path and os.path.exists(icon_path):
        meta.setdefault("icon_path", _build_task_input_asset_ref(task_id, "logo.png"))
    return meta


def _get_config() -> tuple[str, str]:
    base_url = os.getenv("ADMIN_API_URL", "").strip() or os.getenv("CONVERTAPK_ADMIN_URL", "").strip()
    token = os.getenv("ADMIN_CLIENT_TOKEN", "").strip() or os.getenv("CONVERTAPK_CLIENT_TOKEN", "").strip()
    return base_url.rstrip("/"), token


def _get_client_version() -> str:
    return os.getenv("CONVERTAPK_APP_VERSION", "").strip()


def _request_json(method: str, path: str, payload: Optional[Dict] = None, params: Optional[Dict] = None) -> Optional[Dict]:
    base_url, token = _get_config()
    if not base_url or not token:
        return None
    url = f"{base_url}{path}"
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    data = None
    headers = {"X-Client-Token": token}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body) if body else {}
    except Exception:
        return None


def check_admin_service() -> tuple[bool, str]:
    now = time.monotonic()
    cached = _ADMIN_STATUS_CACHE
    if now - cached.get("checked_at", 0.0) < _ADMIN_STATUS_TTL:
        return bool(cached.get("ok", False)), str(cached.get("reason", ""))

    base_url, token = _get_config()
    if not base_url or not token:
        cached.update({"ok": False, "reason": "missing_config", "checked_at": now})
        return False, "missing_config"

    url = f"{base_url}/api/client/announcements"
    req = urllib.request.Request(url, method="GET", headers={"X-Client-Token": token})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            ok = 200 <= resp.status < 300
            cached.update({"ok": ok, "reason": "", "checked_at": now})
            return ok, ""
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            cached.update({"ok": False, "reason": "denied", "checked_at": now})
            return False, "denied"
        cached.update({"ok": False, "reason": "unreachable", "checked_at": now})
        return False, "unreachable"
    except Exception:
        cached.update({"ok": False, "reason": "unreachable", "checked_at": now})
        return False, "unreachable"


def _queue_path() -> str:
    base = os.getenv("APPDATA", "") or "."
    return os.path.join(base, "ConvertAPK", _QUEUE_FILENAME)


def _load_queue() -> List[Dict[str, Any]]:
    path = _queue_path()
    try:
        if not os.path.exists(path):
            return []
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_queue(items: List[Dict[str, Any]]) -> None:
    path = _queue_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


def _enqueue_assets(payload: Dict[str, Any]) -> None:
    items = _load_queue()
    items.append(payload)
    if len(items) > 100:
        items = items[-100:]
    _save_queue(items)


def flush_task_assets_queue() -> None:
    items = _load_queue()
    if not items:
        return
    remaining: List[Dict[str, Any]] = []
    for item in items:
        ok = upload_task_assets(
            item.get("task_id", ""),
            item.get("client_id", ""),
            item.get("start_time", ""),
            item.get("zip_info", {}) or {},
            item.get("app_config", {}) or {},
            client_version=item.get("client_version", "") or "",
            zip_path=item.get("zip_path"),
            html_path=item.get("html_path"),
            icon_path=item.get("icon_path"),
            keystore_info=item.get("keystore_info", {}) or {},
            _allow_queue=False,
        )
        if not ok:
            remaining.append(item)
    _save_queue(remaining)


def report_task_start(task_id: str, client_id: str, start_time: str, zip_info: Dict[str, Any], app_config: Dict[str, Any]) -> None:
    payload = {
        "task_id": task_id,
        "client_id": client_id,
        "client_version": _get_client_version(),
        "start_time": start_time,
        "zip_info": zip_info,
        "app_config": app_config,
    }
    _request_json("POST", "/api/client/task/start", payload=payload)


def report_task_logs(task_id: str, client_id: str, error_code: str, last_50_lines: List[str]) -> None:
    payload = {
        "task_id": task_id,
        "client_id": client_id,
        "error_code": error_code,
        "last_50_lines": last_50_lines,
    }
    _request_json("POST", "/api/client/task/logs", payload=payload)


def report_task_status(
    task_id: str,
    client_id: str,
    status: str,
    finished_at: str,
    output_info: Optional[Dict[str, Any]] = None,
) -> None:
    payload = {
        "task_id": task_id,
        "client_id": client_id,
        "status": status,
        "client_version": _get_client_version(),
        "finished_at": finished_at,
        "output_info": output_info or {},
    }
    _request_json("POST", "/api/client/task/status", payload=payload)


def fetch_announcements() -> List[Dict[str, Any]]:
    data = _request_json("GET", "/api/client/announcements")
    if isinstance(data, list):
        return data
    return []


def check_update(version: str) -> Dict[str, Any]:
    data = _request_json("GET", "/api/client/update/check", params={"version": version})
    if not isinstance(data, dict):
        return {"has_update": False}
    base_url, _ = _get_config()
    download_url = data.get("download_url")
    if download_url and download_url.startswith("/"):
        data["download_url"] = f"{base_url}{download_url}"
    return data


def fetch_feature_flags(client_id: str = "", force: bool = False) -> Dict[str, Any]:
    now = time.monotonic()
    normalized_client_id = str(client_id or "").strip()
    cache_key = normalized_client_id or "__global__"
    cached = _FEATURE_FLAGS_CACHE.get(cache_key, {})
    if not force and now - float(cached.get("checked_at", 0.0)) < _FEATURE_FLAGS_TTL:
        data = cached.get("data")
        if isinstance(data, dict):
            return dict(data)

    params = {"client_id": normalized_client_id} if normalized_client_id else None
    data = _request_json("GET", "/api/client/features", params=params)
    result = {
        "web_link_to_apk_enabled": False,
        "zip_to_desktop_enabled": False,
        "rewarded_build_ads_enabled": False,
        "client_login_enabled": True,
        "client_sms_login_enabled": False,
        "client_register_enabled": True,
        "upload_max_size_mb": 200,
        "risk_scan_block_keywords": [],
        "risk_scan_domain_keywords": [],
    }

    def _normalize_keyword_list(value: Any) -> List[str]:
        if isinstance(value, str):
            candidates = re.split(r"[\r\n,;]+", value)
        elif isinstance(value, (list, tuple, set)):
            candidates = list(value)
        else:
            return []
        seen = set()
        keywords: List[str] = []
        for item in candidates:
            keyword = str(item or "").strip()
            if not keyword:
                continue
            dedupe_key = keyword.lower()
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            keywords.append(keyword)
        return keywords

    if isinstance(data, dict):
        result["web_link_to_apk_enabled"] = bool(data.get("web_link_to_apk_enabled"))
        result["zip_to_desktop_enabled"] = bool(data.get("zip_to_desktop_enabled"))
        result["rewarded_build_ads_enabled"] = bool(data.get("rewarded_build_ads_enabled"))
        if "client_login_enabled" in data:
            result["client_login_enabled"] = bool(data.get("client_login_enabled"))
        if "client_sms_login_enabled" in data:
            result["client_sms_login_enabled"] = bool(data.get("client_sms_login_enabled"))
        if "client_register_enabled" in data:
            result["client_register_enabled"] = bool(data.get("client_register_enabled"))
        if "upload_max_size_mb" in data:
            try:
                parsed_size = int(data.get("upload_max_size_mb") or 0)
                if parsed_size > 0:
                    result["upload_max_size_mb"] = parsed_size
            except Exception:
                pass
        if "risk_scan_block_keywords" in data:
            result["risk_scan_block_keywords"] = _normalize_keyword_list(data.get("risk_scan_block_keywords"))
        if "risk_scan_domain_keywords" in data:
            result["risk_scan_domain_keywords"] = _normalize_keyword_list(data.get("risk_scan_domain_keywords"))
    _FEATURE_FLAGS_CACHE[cache_key] = {
        "data": result,
        "checked_at": now,
    }
    return dict(result)


def _encode_multipart(fields: Dict[str, str], files: List[Dict[str, Any]]) -> tuple[bytes, str]:
    boundary = f"----ConvertAPKBoundary{os.urandom(8).hex()}"
    lines: List[bytes] = []
    for name, value in fields.items():
        lines.append(f"--{boundary}\r\n".encode("utf-8"))
        lines.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"))
        lines.append(str(value).encode("utf-8"))
        lines.append(b"\r\n")
    for item in files:
        lines.append(f"--{boundary}\r\n".encode("utf-8"))
        disposition = f'Content-Disposition: form-data; name="{item["field"]}"; filename="{item["filename"]}"\r\n'
        lines.append(disposition.encode("utf-8"))
        lines.append(f"Content-Type: {item['content_type']}\r\n\r\n".encode("utf-8"))
        lines.append(item["data"])
        lines.append(b"\r\n")
    lines.append(f"--{boundary}--\r\n".encode("utf-8"))
    body = b"".join(lines)
    return body, f"multipart/form-data; boundary={boundary}"


def _build_upload_file(
    field: str,
    file_path: Optional[str],
    filename: str,
    content_type: str,
) -> Optional[Dict[str, Any]]:
    raw_path = str(file_path or "").strip()
    if not raw_path or not os.path.isfile(raw_path):
        return None
    try:
        with open(raw_path, "rb") as f:
            data = f.read()
    except Exception:
        return None
    return {
        "field": field,
        "filename": filename,
        "content_type": content_type,
        "data": data,
    }


def _env_flag(name: str, default: bool = False) -> bool:
    raw = str(os.getenv(name, "")).strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def _should_upload_task_input_assets() -> bool:
    return _env_flag("ADMIN_UPLOAD_TASK_INPUT_ASSETS", default=False)


def submit_feedback(client_id: str, content: str, device_info: Dict[str, Any], images: List[Dict[str, Any]]) -> bool:
    base_url, token = _get_config()
    if not base_url or not token:
        return False
    fields = {
        "client_id": client_id,
        "content": content,
        "device_info": json.dumps(device_info, ensure_ascii=False),
    }
    body, content_type = _encode_multipart(fields, images)
    req = urllib.request.Request(
        f"{base_url}/api/client/feedback",
        data=body,
        method="POST",
        headers={"X-Client-Token": token, "Content-Type": content_type},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return 200 <= resp.status < 300
    except Exception:
        return False


def upload_task_assets(
    task_id: str,
    client_id: str,
    start_time: str,
    zip_info: Dict[str, Any],
    app_config: Dict[str, Any],
    client_version: str = "",
    zip_path: Optional[str] = None,
    html_path: Optional[str] = None,
    icon_path: Optional[str] = None,
    keystore_path: Optional[str] = None,
    keystore_info: Optional[Dict[str, Any]] = None,
    output_path: Optional[str] = None,
    _allow_queue: bool = True,
    android_source_path: Optional[str] = None,
) -> bool:
    base_url, token = _get_config()
    client_version = (client_version or _get_client_version()).strip()
    resolved_zip_info = _merge_task_asset_meta(
        task_id,
        zip_info,
        zip_path=zip_path,
        html_path=html_path,
        icon_path=icon_path,
    )
    if not base_url or not token:
        if _allow_queue:
            _enqueue_assets({
                "task_id": task_id,
                "client_id": client_id,
                "client_version": client_version,
                "start_time": start_time,
                "zip_info": resolved_zip_info,
                "app_config": app_config,
                "zip_path": zip_path,
                "html_path": html_path,
                "icon_path": icon_path,
                "keystore_info": keystore_info or {},
            })
        return False
    files: List[Dict[str, Any]] = []
    if _should_upload_task_input_assets():
        zip_file = _build_upload_file("zip_file", zip_path, "project.zip", "application/zip")
        if zip_file:
            files.append(zip_file)
        icon_file = _build_upload_file("icon_file", icon_path, "logo.png", "image/png")
        if icon_file:
            files.append(icon_file)
    fields = {
        "task_id": task_id,
        "client_id": client_id,
        "client_version": client_version,
        "start_time": start_time,
        "zip_info": json.dumps(resolved_zip_info or {}, ensure_ascii=False),
        "app_config": json.dumps(app_config or {}, ensure_ascii=False),
        "keystore_info": json.dumps(keystore_info or {}, ensure_ascii=False),
    }
    body, content_type = _encode_multipart(fields, files)
    req = urllib.request.Request(
        f"{base_url}/api/client/task/assets",
        data=body,
        method="POST",
        headers={"X-Client-Token": token, "Content-Type": content_type},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return 200 <= resp.status < 300
    except Exception:
        if _allow_queue:
            _enqueue_assets({
                "task_id": task_id,
                "client_id": client_id,
                "client_version": client_version,
                "start_time": start_time,
                "zip_info": resolved_zip_info,
                "app_config": app_config,
                "zip_path": zip_path,
                "html_path": html_path,
                "icon_path": icon_path,
                "keystore_info": keystore_info or {},
            })
        return False
