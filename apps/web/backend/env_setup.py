import os
import sys
import threading
import time
import urllib.request
import shutil
import subprocess
import zipfile
import re
import json
from pathlib import Path
from typing import Dict, List, Optional

CONFIG_PATH = Path(os.getenv("APPDATA", ".")) / "ConvertAPK" / "config.json"


def _default_toolchain_root() -> Path:
    _toolchain_override = os.getenv("CONVERTAPK_TOOLCHAIN_ROOT", "").strip()
    if _toolchain_override:
        return Path(_toolchain_override).expanduser()
    _resources_root = os.getenv("ELECTRON_RESOURCES", "").strip()
    if _resources_root:
        return Path(_resources_root) / "toolchain"
    return Path(os.getenv("APPDATA", ".")) / "ConvertAPK" / "toolchain"


def _load_config() -> Dict:
    if not CONFIG_PATH.exists():
        return {}
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_config(config: Dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")


def _resolve_toolchain_root() -> Path:
    config = _load_config()
    toolchain_root = str(config.get("toolchain_root", "")).strip()
    if toolchain_root:
        path = Path(toolchain_root).expanduser()
        if not path.is_absolute():
            return (Path.cwd() / path).resolve()
        return path
    return _default_toolchain_root()


TOOLCHAIN_ROOT = _resolve_toolchain_root()
DEFAULT_NODE_MAJOR = "22"
NODE_VERSIONS = {
    "18": {
        "version": "18.20.4",
        "zip": "node-v18.20.4-win-x64.zip",
        "url": "https://npmmirror.com/mirrors/node/v18.20.4/node-v18.20.4-win-x64.zip",
    },
    "19": {
        "version": "19.9.0",
        "zip": "node-v19.9.0-win-x64.zip",
        "url": "https://npmmirror.com/mirrors/node/v19.9.0/node-v19.9.0-win-x64.zip",
    },
    "22": {
        "version": "22.12.0",
        "zip": "node-v22.12.0-win-x64.zip",
        "url": "https://npmmirror.com/mirrors/node/v22.12.0/node-v22.12.0-win-x64.zip",
    },
}
NODE_VERSION = NODE_VERSIONS[DEFAULT_NODE_MAJOR]["version"]
JDK_VERSION = "21.0.9_10"
PYTHON_VERSION = "3.11.9"
ANDROID_PLATFORM = "android-36"
ANDROID_BUILD_TOOLS = "36.0.0"

NODE_ZIP = f"node-v{NODE_VERSION}-win-x64.zip"
# Prefer domestic mirror; fallback handled by manual override if needed.
NODE_URL = f"https://npmmirror.com/mirrors/node/v{NODE_VERSION}/{NODE_ZIP}"

JDK_ZIP = f"OpenJDK21U-jdk_x64_windows_hotspot_{JDK_VERSION}.zip"
# Prefer domestic mirror for JDK when possible.
JDK_URLS = [
    f"https://mirrors.tuna.tsinghua.edu.cn/Adoptium/21/jdk/x64/windows/{JDK_ZIP}",
]

CMDLINE_ZIP = "commandlinetools-win-11076708_latest.zip"
# Prefer domestic mirror for Android cmdline-tools.
CMDLINE_URL = f"https://dl.google.com/android/repository/{CMDLINE_ZIP}"
PYTHON_ZIP = f"python-{PYTHON_VERSION}-embed-amd64.zip"
PYTHON_URL = f"https://www.python.org/ftp/python/{PYTHON_VERSION}/{PYTHON_ZIP}"

ENV_LOCK = threading.Lock()
ENV_RUNNING = False
ENV_PROGRESS: List[str] = []
ENV_LAST_ERROR: Optional[str] = None
ENV_LOG_PATH = TOOLCHAIN_ROOT / "env-setup.log"
ENV_PROGRESS_PERCENT: Optional[int] = None
ENV_PROGRESS_STAGE: str = ""
ENV_RETRY_COUNT = 0
ENV_RETRY_PENDING = False
ENV_AUTO_RETRY = os.getenv("CONVERTAPK_ENV_AUTO_RETRY", "1").strip().lower() not in {"0", "false", "no"}
ENV_RETRY_MAX = int(os.getenv("CONVERTAPK_ENV_RETRY_MAX", "5") or "5")
ENV_RETRY_DELAY = int(os.getenv("CONVERTAPK_ENV_RETRY_DELAY_SEC", "30") or "30")


def _progress(message: str) -> None:
    timestamp = time.strftime("%H:%M:%S")
    ENV_PROGRESS.append(f"[{timestamp}] {message}")
    if len(ENV_PROGRESS) > 200:
        ENV_PROGRESS[:] = ENV_PROGRESS[-200:]
    try:
        ENV_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with ENV_LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {message}\n")
    except Exception:
        pass


def _set_progress(stage: Optional[str] = None, percent: Optional[int] = None) -> None:
    global ENV_PROGRESS_STAGE, ENV_PROGRESS_PERCENT
    if stage is not None:
        ENV_PROGRESS_STAGE = stage
    if percent is not None or percent is None:
        ENV_PROGRESS_PERCENT = percent


def _apply_toolchain_root(path: Path) -> None:
    global TOOLCHAIN_ROOT, ENV_LOG_PATH
    TOOLCHAIN_ROOT = path
    ENV_LOG_PATH = TOOLCHAIN_ROOT / "env-setup.log"


def _resource_root() -> Optional[Path]:
    resources_env = os.getenv("ELECTRON_RESOURCES", "").strip()
    if resources_env:
        return Path(resources_env)
    exe_dir = Path(sys.executable).parent
    if (exe_dir / "node").exists() or (exe_dir / "jdk").exists():
        return exe_dir
    if (exe_dir.parent / "node").exists():
        return exe_dir.parent
    return None


def _is_node_dir(path: Path) -> bool:
    return (path / "npm.cmd").exists() or (path / "npm").exists()


def _is_jdk_dir(path: Path) -> bool:
    bin_dir = path / "bin"
    return (bin_dir / "java.exe").exists() and (bin_dir / "keytool.exe").exists()

def _parse_java_version(text: str) -> Optional[tuple]:
    match = re.search(r'version\s+"([^"]+)"', text)
    if not match:
        return None
    raw = match.group(1)
    if raw.startswith("1."):
        parts = raw.split(".")
        if len(parts) >= 2 and parts[1].isdigit():
            return (int(parts[1]), 0, 0)
        return None
    core = re.match(r"(\d+)(?:\.(\d+))?(?:\.(\d+))?", raw)
    if not core:
        return None
    major = int(core.group(1))
    minor = int(core.group(2) or 0)
    patch = int(core.group(3) or 0)
    return (major, minor, patch)


def _get_java_version(jdk_dir: Path) -> Optional[tuple]:
    java_exe = jdk_dir / "bin" / ("java.exe" if os.name == "nt" else "java")
    if not java_exe.exists():
        return None
    try:
        result = subprocess.run(
            [str(java_exe), "-version"],
            capture_output=True,
            text=True,
            check=False,
        )
        output = (result.stderr or result.stdout or "").strip()
        return _parse_java_version(output)
    except Exception:
        return None


def _jdk_version_ok(jdk_dir: Path) -> bool:
    version = _get_java_version(jdk_dir)
    if not version:
        return False
    return version[0] >= 17


def _is_jdk_usable(path: Path) -> bool:
    return _is_jdk_dir(path) and _jdk_version_ok(path)


def _is_android_dir(path: Path) -> bool:
    platform_tools = path / "platform-tools" / ("adb.exe" if os.name == "nt" else "adb")
    build_tools = path / "build-tools" / ANDROID_BUILD_TOOLS
    zipalign = build_tools / ("zipalign.exe" if os.name == "nt" else "zipalign")
    apksigner = build_tools / ("apksigner.bat" if os.name == "nt" else "apksigner")
    platform = path / "platforms" / ANDROID_PLATFORM
    return platform_tools.exists() and zipalign.exists() and apksigner.exists() and platform.exists()

def _resolve_python_exe(path: Path) -> Optional[Path]:
    if not path.exists():
        return None
    if path.is_dir():
        exe = path / ("python.exe" if os.name == "nt" else "python")
        return exe if exe.exists() else None
    return path if path.name.lower().startswith("python") else None


def _parse_python_version(text: str) -> Optional[str]:
    match = re.search(r"Python\s+(\d+\.\d+\.\d+)", text)
    return match.group(1) if match else None


def _python_version_ok(version: str) -> bool:
    try:
        major, minor, *_ = [int(part) for part in version.split(".")]
    except Exception:
        return False
    return (major, minor) >= (3, 6)


def _get_python_version(exe: Path) -> Optional[str]:
    try:
        result = subprocess.run(
            [str(exe), "--version"],
            capture_output=True,
            text=True,
            check=False,
        )
        output = (result.stdout or result.stderr or "").strip()
        return _parse_python_version(output)
    except Exception:
        return None


def _candidate_paths() -> Dict[str, List[Path]]:
    candidates = {"node": [], "jdk": [], "android": [], "python": []}
    config = _load_config()
    manual_node = str(config.get("node_path", "")).strip()
    manual_jdk = str(config.get("jdk_path", "")).strip()
    manual_android = str(config.get("android_path", "")).strip()
    manual_python = str(config.get("python_path", "")).strip()
    if manual_node:
        candidates["node"].append(Path(manual_node).expanduser())
    if manual_jdk:
        candidates["jdk"].append(Path(manual_jdk).expanduser())
    if manual_android:
        candidates["android"].append(Path(manual_android).expanduser())
    if manual_python:
        candidates["python"].append(Path(manual_python).expanduser())
    node_home = os.getenv("NODE_HOME", "").strip()
    if node_home:
        candidates["node"].append(Path(node_home))
    java_home = os.getenv("JAVA_HOME", "").strip()
    if java_home:
        candidates["jdk"].append(Path(java_home))
    android_home = os.getenv("ANDROID_HOME", "").strip() or os.getenv("ANDROID_SDK_ROOT", "").strip()
    if android_home:
        candidates["android"].append(Path(android_home))
    python_path = os.getenv("PYTHON", "").strip()
    if python_path:
        candidates["python"].append(Path(python_path))
    python_from_path = shutil.which("python") or shutil.which("python3")
    if python_from_path:
        candidates["python"].append(Path(python_from_path))

    resources = _resource_root()
    if resources:
        candidates["node"].append(resources / "node")
        candidates["jdk"].append(resources / "jdk")
        candidates["android"].append(resources / "android-sdk")

    candidates["node"].append(TOOLCHAIN_ROOT / "node")
    candidates["node"].append(TOOLCHAIN_ROOT / "node-22")
    candidates["node"].append(TOOLCHAIN_ROOT / "node-19")
    candidates["node"].append(TOOLCHAIN_ROOT / "node-18")
    candidates["jdk"].append(TOOLCHAIN_ROOT / "jdk")
    candidates["android"].append(TOOLCHAIN_ROOT / "android-sdk")
    candidates["python"].append(TOOLCHAIN_ROOT / "python")
    return candidates


def _pick_path(paths: List[Path], checker) -> Optional[Path]:
    for path in paths:
        if path.exists() and checker(path):
            return path
    return None


def get_status() -> Dict:
    candidates = _candidate_paths()
    node_path = _pick_path(candidates["node"], _is_node_dir)
    jdk_path = _pick_path(candidates["jdk"], _is_jdk_usable)
    android_path = _pick_path(candidates["android"], _is_android_dir)
    python_path = ""
    python_version = ""
    python_ok = False
    python_error = ""
    for candidate in candidates["python"]:
        exe = _resolve_python_exe(candidate)
        if not exe:
            continue
        python_path = str(exe)
        version = _get_python_version(exe)
        if not version:
            # Accept the executable but note missing version (embedded Python may not report in some environments).
            python_ok = True
            python_error = ""
            break
        python_version = version
        if _python_version_ok(version):
            python_ok = True
            break
        python_ok = False
        python_error = f"Python {version} is not supported"
        break

    missing = []
    if not node_path:
        missing.append("node")
    if not jdk_path:
        missing.append("jdk")
    if not android_path:
        missing.append("android-sdk")
    if not python_path or not python_ok:
        missing.append("python")

    return {
        "ready": len(missing) == 0,
        "missing": missing,
        "paths": {
            "node": str(node_path) if node_path else "",
            "jdk": str(jdk_path) if jdk_path else "",
            "android": str(android_path) if android_path else "",
            "python": str(python_path) if python_path else "",
        },
        "python_version": python_version,
        "python_ok": python_ok,
        "python_error": python_error,
        "toolchain_root": str(TOOLCHAIN_ROOT),
        "port": os.getenv("CONVERTAPK_PORT", ""),
        "running": ENV_RUNNING,
        "progress": ENV_PROGRESS[-50:],
        "error": ENV_LAST_ERROR or "",
        "progress_percent": ENV_PROGRESS_PERCENT,
        "progress_stage": ENV_PROGRESS_STAGE,
    }


def get_env_overrides() -> Dict[str, str]:
    status = get_status()
    env: Dict[str, str] = {}
    node_path = status["paths"]["node"]
    jdk_path = status["paths"]["jdk"]
    android_path = status["paths"]["android"]
    python_path = status["paths"]["python"]
    if node_path:
        env["NODE_HOME"] = node_path
    if jdk_path:
        env["JAVA_HOME"] = jdk_path
    if android_path:
        env["ANDROID_HOME"] = android_path
        env["ANDROID_SDK_ROOT"] = android_path
    if python_path:
        env["PYTHON"] = python_path

    path_parts = []
    if node_path:
        path_parts.append(node_path)
    if jdk_path:
        path_parts.append(str(Path(jdk_path) / "bin"))
    if android_path:
        path_parts.append(str(Path(android_path) / "platform-tools"))
        path_parts.append(str(Path(android_path) / "cmdline-tools" / "latest" / "bin"))
    if path_parts:
        env["PATH"] = os.pathsep.join(path_parts) + os.pathsep + os.getenv("PATH", "")
    return env


def get_config() -> Dict:
    config = _load_config()
    npm_registry = str(config.get("npm_registry", "")).strip()
    if not npm_registry:
        npm_registry = "https://registry.npmmirror.com"
    return {
        "toolchain_root": str(TOOLCHAIN_ROOT),
        "data_root": str(config.get("data_root", "")).strip(),
        "npm_registry": npm_registry,
        "npm_proxy": str(config.get("npm_proxy", "")).strip(),
        "npm_https_proxy": str(config.get("npm_https_proxy", "")).strip(),
        "node_path": str(config.get("node_path", "")).strip(),
        "jdk_path": str(config.get("jdk_path", "")).strip(),
        "android_path": str(config.get("android_path", "")).strip(),
        "python_path": str(config.get("python_path", "")).strip(),
    }


def set_config(
    toolchain_root: str,
    migrate: bool = False,
    npm_registry: str = "",
    npm_proxy: str = "",
    npm_https_proxy: str = "",
    data_root: str = "",
    node_path: str = "",
    jdk_path: str = "",
    android_path: str = "",
    python_path: str = "",
) -> Dict:
    if not toolchain_root or not str(toolchain_root).strip():
        raise ValueError("toolchain_root is required")
    path = Path(str(toolchain_root)).expanduser()
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()

    old_root = TOOLCHAIN_ROOT
    if migrate and old_root.exists() and old_root != path:
        path.mkdir(parents=True, exist_ok=True)
        for item in old_root.iterdir():
            target = path / item.name
            if target.exists():
                continue
            shutil.move(str(item), str(target))
    normalized_registry = str(npm_registry or "").strip() or "https://registry.npmmirror.com"
    normalized_data_root = str(data_root or "").strip()
    config = {
        "toolchain_root": str(path),
        "data_root": normalized_data_root,
        "npm_registry": normalized_registry,
        "npm_proxy": str(npm_proxy or "").strip(),
        "npm_https_proxy": str(npm_https_proxy or "").strip(),
        "node_path": str(node_path or "").strip(),
        "jdk_path": str(jdk_path or "").strip(),
        "android_path": str(android_path or "").strip(),
        "python_path": str(python_path or "").strip(),
    }
    _save_config(config)
    _apply_toolchain_root(path)
    return {
        "toolchain_root": str(path),
        "migrated": bool(migrate),
        "data_root": normalized_data_root,
        "npm_registry": config["npm_registry"],
        "npm_proxy": config["npm_proxy"],
        "npm_https_proxy": config["npm_https_proxy"],
        "node_path": config["node_path"],
        "jdk_path": config["jdk_path"],
        "android_path": config["android_path"],
        "python_path": config["python_path"],
    }


def get_npm_config() -> Dict[str, str]:
    config = _load_config()
    return {
        "NPM_CONFIG_REGISTRY": str(config.get("npm_registry", "")).strip() or "https://registry.npmmirror.com",
        "NPM_CONFIG_PROXY": str(config.get("npm_proxy", "")).strip(),
        "NPM_CONFIG_HTTPS_PROXY": str(config.get("npm_https_proxy", "")).strip(),
    }


def _download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        resume_from = dest.stat().st_size if dest.exists() else 0
        headers = {}
        if resume_from:
            headers["Range"] = f"bytes={resume_from}-"
        _set_progress(stage=f"Downloading {url}", percent=0)
        _progress(f"Downloading {url} (attempt {attempt}/{max_attempts})")
        try:
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request) as response:
                status = getattr(response, "status", None)
                mode = "ab" if resume_from and status == 206 else "wb"
                if mode == "wb" and resume_from:
                    _progress("Server does not support resume; restarting download")
                total = response.getheader("Content-Length")
                total_bytes = int(total) + resume_from if total and total.isdigit() else 0
                downloaded = resume_from
                last_percent = -1
                with dest.open(mode) as f:
                    while True:
                        chunk = response.read(1024 * 256)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_bytes:
                            percent = int(downloaded * 100 / total_bytes)
                            if percent != last_percent:
                                _set_progress(percent=percent)
                                last_percent = percent
            _progress(f"Downloaded to {dest}")
            _set_progress(percent=100)
            return
        except Exception as exc:
            _progress(f"Download failed: {url} ({exc})")
            if attempt == max_attempts:
                raise


def _download_with_fallback(urls: List[str], dest: Path) -> None:
    last_error: Optional[Exception] = None
    for url in urls:
        try:
            if dest.exists():
                dest.unlink(missing_ok=True)
            _download(url, dest)
            return
        except Exception as exc:
            last_error = exc
            _progress(f"Mirror failed: {url} ({exc})")
            continue
    if last_error:
        raise last_error


def _extract_zip(zip_path: Path, dest_dir: Path) -> None:
    _set_progress(stage=f"Extracting {zip_path}", percent=None)
    _progress(f"Extracting {zip_path} to {dest_dir}")
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(dest_dir)
        _progress(f"Extracted {zip_path}")
    except Exception as exc:
        if isinstance(exc, (zipfile.BadZipFile, zipfile.LargeZipFile)):
            try:
                zip_path.unlink(missing_ok=True)
                _progress(f"Corrupted zip removed: {zip_path}")
            except Exception:
                pass
        _progress(f"Extraction failed: {zip_path} ({exc})")
        raise


def _ensure_node() -> Path:
    return _ensure_node_version(DEFAULT_NODE_MAJOR)


def _node_archive_info(major: str) -> tuple[str, str, str]:
    entry = NODE_VERSIONS.get(str(major))
    if not entry:
        raise RuntimeError(f"Unsupported Node.js major version: {major}")
    return entry["version"], entry["zip"], entry["url"]


def _node_cache_dir(major: str) -> Path:
    return TOOLCHAIN_ROOT / f"node-{major}"


def _ensure_node_version(major: str) -> Path:
    major = str(major).strip()
    node_dir = _node_cache_dir(major)
    if _is_node_dir(node_dir):
        return node_dir
    version, zip_name, url = _node_archive_info(major)
    _set_progress(stage=f"Downloading Node.js {version}", percent=0)
    _progress(f"Downloading Node.js {version}")
    zip_path = TOOLCHAIN_ROOT / zip_name
    _download(url, zip_path)
    _set_progress(stage="Extracting Node.js", percent=None)
    _progress("Extracting Node.js")
    _extract_zip(zip_path, TOOLCHAIN_ROOT)
    extracted = TOOLCHAIN_ROOT / f"node-v{version}-win-x64"
    if node_dir.exists():
        shutil.rmtree(node_dir, ignore_errors=True)
    if extracted.exists():
        extracted.rename(node_dir)
    zip_path.unlink(missing_ok=True)
    return node_dir


def _ensure_jdk() -> Path:
    jdk_dir = TOOLCHAIN_ROOT / "jdk"
    if _is_jdk_usable(jdk_dir):
        return jdk_dir
    if jdk_dir.exists():
        shutil.rmtree(jdk_dir, ignore_errors=True)
    _set_progress(stage=f"Downloading JDK {JDK_VERSION}", percent=0)
    _progress(f"Downloading JDK {JDK_VERSION}")
    zip_path = TOOLCHAIN_ROOT / JDK_ZIP
    _download_with_fallback(JDK_URLS, zip_path)
    _set_progress(stage="Extracting JDK", percent=None)
    _progress("Extracting JDK")
    _extract_zip(zip_path, TOOLCHAIN_ROOT)
    expected_prefix = "OpenJDK21U-jdk_x64_windows_hotspot_"
    extracted = TOOLCHAIN_ROOT / f"{expected_prefix}{JDK_VERSION}"
    if extracted.exists():
        extracted.rename(jdk_dir)
    else:
        candidates = []
        for candidate in TOOLCHAIN_ROOT.iterdir():
            if candidate.is_dir() and _is_jdk_dir(candidate):
                candidates.append(candidate)
        preferred = [c for c in candidates if c.name.startswith(expected_prefix)]
        if preferred:
            candidates = preferred
        best = None
        best_version = None
        for candidate in candidates:
            version = _get_java_version(candidate)
            if version and (best_version is None or version > best_version):
                best_version = version
                best = candidate
        if not best and candidates:
            best = candidates[0]
        if best:
            _progress(f"Detected extracted JDK at {best}")
            best.rename(jdk_dir)
    zip_path.unlink(missing_ok=True)
    if not _is_jdk_usable(jdk_dir):
        raise RuntimeError(f"JDK extraction failed: {jdk_dir}")
    return jdk_dir


def _ensure_python() -> Path:
    python_dir = TOOLCHAIN_ROOT / "python"
    python_exe = python_dir / ("python.exe" if os.name == "nt" else "python")
    if python_exe.exists():
        return python_dir
    if python_dir.exists():
        shutil.rmtree(python_dir, ignore_errors=True)
    _set_progress(stage=f"Downloading Python {PYTHON_VERSION}", percent=0)
    _progress(f"Downloading Python {PYTHON_VERSION}")
    zip_path = TOOLCHAIN_ROOT / PYTHON_ZIP
    _download(PYTHON_URL, zip_path)
    _set_progress(stage="Extracting Python", percent=None)
    _progress("Extracting Python")
    python_dir.mkdir(parents=True, exist_ok=True)
    _extract_zip(zip_path, python_dir)
    zip_path.unlink(missing_ok=True)
    python_exe = python_dir / ("python.exe" if os.name == "nt" else "python")
    if not python_exe.exists():
        raise RuntimeError(f"Python extraction failed: {python_exe}")
    return python_dir


def _ensure_android_sdk(jdk_dir: Path) -> Path:
    sdk_dir = TOOLCHAIN_ROOT / "android-sdk"
    if _is_android_dir(sdk_dir):
        return sdk_dir
    _set_progress(stage="Downloading Android SDK cmdline-tools", percent=0)
    _progress("Downloading Android SDK cmdline-tools")
    zip_path = TOOLCHAIN_ROOT / CMDLINE_ZIP
    _download(CMDLINE_URL, zip_path)
    temp_dir = TOOLCHAIN_ROOT / "android-cmdline"
    if temp_dir.exists():
        shutil.rmtree(temp_dir, ignore_errors=True)
    _extract_zip(zip_path, temp_dir)
    cmdline_src = temp_dir / "cmdline-tools"
    cmdline_dest = sdk_dir / "cmdline-tools" / "latest"
    cmdline_dest.parent.mkdir(parents=True, exist_ok=True)
    if cmdline_dest.exists():
        shutil.rmtree(cmdline_dest, ignore_errors=True)
    cmdline_src.rename(cmdline_dest)
    zip_path.unlink(missing_ok=True)

    sdkmanager = cmdline_dest / "bin" / ("sdkmanager.bat" if os.name == "nt" else "sdkmanager")
    env = os.environ.copy()
    env["JAVA_HOME"] = str(jdk_dir)
    env["ANDROID_HOME"] = str(sdk_dir)
    env["ANDROID_SDK_ROOT"] = str(sdk_dir)
    env["PATH"] = os.pathsep.join(
        [str(jdk_dir / "bin"), str(cmdline_dest / "bin"), env.get("PATH", "")]
    )

    _set_progress(stage="Installing Android SDK packages", percent=None)
    _progress("Installing Android SDK packages")
    packages = [
        "platform-tools",
        f"platforms;{ANDROID_PLATFORM}",
        f"build-tools;{ANDROID_BUILD_TOOLS}",
    ]
    os.makedirs(sdk_dir, exist_ok=True)
    sdkmanager_cmd = [str(sdkmanager)]
    install_cmd = sdkmanager_cmd + [f"--sdk_root={sdk_dir}"] + packages
    install_res = subprocess.run(install_cmd, env=env, check=False, text=True, capture_output=True)
    if install_res.returncode != 0:
        _progress("Android SDK install failed")
        if install_res.stdout:
            _progress(f"Android SDK install stdout: {install_res.stdout.strip()}")
        if install_res.stderr:
            _progress(f"Android SDK install stderr: {install_res.stderr.strip()}")
        raise RuntimeError("Android SDK install failed")
    license_cmd = sdkmanager_cmd + [f"--sdk_root={sdk_dir}", "--licenses"]
    license_res = subprocess.run(
        license_cmd,
        env=env,
        check=False,
        text=True,
        input="y\n" * 50,
        capture_output=True,
    )
    if license_res.returncode != 0:
        _progress("Android SDK license acceptance failed")
        if license_res.stdout:
            _progress(f"Android SDK license stdout: {license_res.stdout.strip()}")
        if license_res.stderr:
            _progress(f"Android SDK license stderr: {license_res.stderr.strip()}")
        raise RuntimeError("Android SDK license acceptance failed")
    return sdk_dir


def is_required() -> bool:
    return os.name == "nt" and os.getenv("APK_BUILDER_MODE", "").strip().lower() != "docker"


def _prepare_env_blocking(force: bool) -> None:
    global ENV_RUNNING, ENV_LAST_ERROR, ENV_RETRY_COUNT, ENV_RETRY_PENDING
    ENV_LAST_ERROR = None
    try:
        ENV_PROGRESS.clear()
        _set_progress(stage="Checking environment", percent=None)
        _progress("Checking environment")
        status = get_status()
        if status["ready"] and not force:
            _progress("Environment already ready")
            return
        node_path = _pick_path(_candidate_paths()["node"], _is_node_dir)
        if not node_path:
            node_path = _ensure_node()
        jdk_path = _pick_path(_candidate_paths()["jdk"], _is_jdk_usable)
        if not jdk_path:
            jdk_path = _ensure_jdk()
        python_path = _pick_path(_candidate_paths()["python"], _resolve_python_exe)
        if not python_path:
            _ensure_python()
        android_path = _pick_path(_candidate_paths()["android"], _is_android_dir)
        if not android_path:
            _ensure_android_sdk(jdk_path)
        _progress("Environment ready")
        _set_progress(stage="Environment ready", percent=100)
        ENV_RETRY_COUNT = 0
        ENV_RETRY_PENDING = False
    except Exception as exc:
        ENV_LAST_ERROR = str(exc)
        _progress(f"Environment setup failed: {ENV_LAST_ERROR}")
        if ENV_AUTO_RETRY and ENV_RETRY_COUNT < ENV_RETRY_MAX and not ENV_RETRY_PENDING:
            ENV_RETRY_COUNT += 1
            ENV_RETRY_PENDING = True
            _progress(f"Auto-retry scheduled ({ENV_RETRY_COUNT}/{ENV_RETRY_MAX})")
            def _retry():
                time.sleep(ENV_RETRY_DELAY)
                try:
                    prepare_env(force=True)
                finally:
                    global ENV_RETRY_PENDING
                    ENV_RETRY_PENDING = False
            threading.Thread(target=_retry, daemon=True).start()
    finally:
        ENV_RUNNING = False


def prepare_env(force: bool = False) -> Dict:
    global ENV_RUNNING
    if not is_required():
        return get_status()

    status = get_status()
    if status["ready"] and not force:
        return status

    with ENV_LOCK:
        if ENV_RUNNING:
            return get_status()
        ENV_RUNNING = True
        thread = threading.Thread(target=_prepare_env_blocking, args=(force,), daemon=True)
        thread.start()

    return get_status()


def start_background_check() -> None:
    if not is_required():
        return

    def _runner():
        try:
            _progress("Background environment check")
            get_status()
        except Exception:
            pass

    thread = threading.Thread(target=_runner, daemon=True)
    thread.start()
