from typing_compat import patch_typing_eval_type

patch_typing_eval_type()

from fastapi import FastAPI, UploadFile, File, HTTPException, Body, Request, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from starlette.background import BackgroundTask
from typing import List
from datetime import datetime
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
import threading
import time
import urllib.request
import urllib.error
import urllib.parse
import zipfile

from models import (
    BuildTask, BuildTaskCreate, BuildTaskListItemResponse, BuildTaskResponse,
    BuildStatus, AppConfig, UpdateTaskRequest
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

app = FastAPI(
    title="APK转换服务",
    description="将Google AI Studio生成的Web App转换为Android APK",
    version="1.0.0"
)

BUILDER_MODE = os.getenv("APK_BUILDER_MODE", "local").strip().lower()
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


def _load_client_feature_flags() -> dict:
    flags = {
        "web_link_to_apk_enabled": False,
        "zip_to_desktop_enabled": False,
    }
    try:
        data = fetch_feature_flags()
    except Exception:
        data = None
    if isinstance(data, dict):
        flags["web_link_to_apk_enabled"] = bool(data.get("web_link_to_apk_enabled"))
        flags["zip_to_desktop_enabled"] = bool(data.get("zip_to_desktop_enabled"))
    return flags


def _is_web_link_mode_enabled() -> bool:
    flags = _load_client_feature_flags()
    return bool(flags.get("web_link_to_apk_enabled"))


def _is_desktop_mode_enabled() -> bool:
    flags = _load_client_feature_flags()
    return bool(flags.get("zip_to_desktop_enabled"))


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
    return bool(
        should_auto_clean_build_outputs()
        and str(getattr(task, "mode", "") or "").strip().lower() == "desktop"
    )


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
    try:
        persist_tasks_db(force=True)
    except Exception:
        pass
    return output_name


def _get_desktop_output_unavailable_detail(task: BuildTask) -> str:
    message = str(getattr(task, "message", "") or "").strip()
    if message and "移除" in message:
        return message
    return "桌面安装包已不可下载"

# 内存存储（MVP版本）
tasks_db = {}
TASKS_STATE_PATH = TASKS_DIR / "tasks.json"
TASKS_STATE_LOCK = threading.Lock()

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


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    """上传ZIP文件"""
    if not file.filename.endswith('.zip'):
        raise HTTPException(status_code=400, detail="只支持ZIP文件")
    
    file_id = str(uuid.uuid4())
    filename = f"{file_id}_{file.filename}"
    file_path = BACKEND_UPLOAD_DIR / filename
    
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件保存失败: {str(e)}")
    
    file_size = file_path.stat().st_size
    
    return {
        "filename": filename,
        "original_name": file.filename,
        "size": file_size,
        "message": "上传成功"
    }


@app.post("/api/upload-html")
async def upload_html(file: UploadFile = File(...)):
    """上传HTML文件"""
    filename_lower = (file.filename or "").lower()
    if not (filename_lower.endswith(".html") or filename_lower.endswith(".htm")):
        raise HTTPException(status_code=400, detail="只支持HTML文件")

    file_id = str(uuid.uuid4())
    filename = f"{file_id}_{file.filename}"
    file_path = BACKEND_UPLOAD_DIR / filename

    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件保存失败: {str(e)}")

    file_size = file_path.stat().st_size

    return {
        "filename": filename,
        "original_name": file.filename,
        "size": file_size,
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

    mode = (task_data.mode or "convert").strip().lower()
    if mode not in {"convert", "web", "html", "desktop"}:
        raise HTTPException(status_code=400, detail="mode must be convert, web, html, or desktop")
    web_url = None
    if mode == "web":
        if not _is_web_link_mode_enabled():
            raise HTTPException(status_code=403, detail="web mode is disabled by admin")
        web_url = str(task_data.web_url or "").strip()
        if not web_url:
            raise HTTPException(status_code=400, detail="web_url is required for web mode")
    if mode == "desktop":
        if not _is_desktop_mode_enabled():
            raise HTTPException(status_code=403, detail="desktop mode is disabled by admin")
        if not LOCAL_MODE:
            raise HTTPException(status_code=503, detail="desktop mode requires local builder mode")
    html_filename = None
    if mode == "html":
        html_filename = str(task_data.html_filename or "").strip()
        if not html_filename:
            raise HTTPException(status_code=400, detail="html_filename is required for html mode")

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
        if reuse_task.client_id != client_id:
            raise HTTPException(status_code=403, detail="无权复用其他任务的签名")
    
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
    
    task = BuildTask(
        id=task_id,
        client_id=client_id,
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
        message="等待构建中",
        reuse_keystore_from=reuse_from,
        cdn_localize_enabled=cdn_localize_enabled,
        cdn_localize_urls=cdn_localize_urls,
        cdn_localize_select_all=cdn_localize_select_all,
        cdn_localize_preprocessed=cdn_localize_preprocessed,
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
    persisted_zip_path = get_persisted_task_asset_path(task_id, "project.zip")
    persisted_html_path = get_persisted_task_asset_path(task_id, "index.html")
    zip_path = persisted_zip_path if persisted_zip_path.exists() else _resolve_task_asset_path(task_id, "project.zip")
    html_path = persisted_html_path if persisted_html_path.exists() else _resolve_task_asset_path(task_id, "index.html")
    icon_path = _resolve_task_asset_path(task_id, "logo.png")
    zip_info = {"build_type": task.mode}
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
    task_list = [task for task in tasks_db.values() if task.client_id == client_id]
    task_list.sort(key=lambda task: (task.updated_at, task.created_at, task.id), reverse=True)
    return task_list


@app.get("/api/tasks/{task_id}", response_model=BuildTaskResponse)
async def get_task(task_id: str, client_id: str = None):
    """获取任务详情"""
    if task_id not in tasks_db:
        raise HTTPException(status_code=404, detail="任务不存在")
    client_id = _require_client_id(client_id)
    task = tasks_db[task_id]
    _assert_task_owner(task, client_id)
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
    canceled = runner.cancel_running_tasks(client_id)
    return {"canceled": canceled}


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
    task.updated_at = datetime.now()

    try:
        config_data = task.config.model_dump() if hasattr(task.config, 'model_dump') else task.config.dict()
    except Exception:
        config_data = {}
    config_data["build_type"] = task.mode
    config_data["task_mode"] = task.mode
    if task.mode == "web" and task.web_url:
        config_data["web_url"] = task.web_url
    task_input_dir = TASKS_DIR / task_id / "input"
    ensure_task_input_assets(task_id, task_input_dir)
    persisted_zip_path = get_persisted_task_asset_path(task_id, "project.zip")
    persisted_html_path = get_persisted_task_asset_path(task_id, "index.html")
    zip_path = persisted_zip_path if persisted_zip_path.exists() else _resolve_task_asset_path(task_id, "project.zip")
    html_path = persisted_html_path if persisted_html_path.exists() else _resolve_task_asset_path(task_id, "index.html")
    icon_path = _resolve_task_asset_path(task_id, "logo.png")
    zip_info = {"build_type": task.mode}
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
        task.updated_at = datetime.now()
    try:
        persist_tasks_db(force=True)
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
    ok = runner.cancel_task(task_id, client_id)
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
    if not should_auto_clean_build_outputs():
        return {"enabled": False, "released": 0}

    released = 0
    for task in list(tasks_db.values()):
        if str(getattr(task, "client_id", "") or "") != client_id:
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
                    raise HTTPException(status_code=400, detail="ZIP涓湭鎵惧埌 index.html")
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
    
    # 重置任务状态
    task.status = BuildStatus.PENDING
    task.progress = 0
    task.message = f"版本更新至 {update_data.version_name}，等待构建"
    task.logs = []
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
async def url_probe(payload: dict = Body(...)):
    if not _is_web_link_mode_enabled():
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
async def adminhub_features():
    return _load_client_feature_flags()


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
