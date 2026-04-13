import json
import hashlib
import os
import shutil
import subprocess
import zipfile
import re
import sys
import urllib.request
import urllib.error
from pathlib import Path, PurePosixPath
from typing import Callable, Dict, Optional, Tuple

import env_setup


def _log(on_log: Optional[Callable[[str], None]], message: str) -> None:
    if on_log:
        on_log(message)


def _decode_process_output(raw: bytes) -> str:
    """优先按 UTF-8 解码，失败时回退到 GB18030，减少中文日志乱码。"""
    if not raw:
        return ""
    for encoding in ("utf-8", "gb18030"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _run_cmd(cmd, cwd=None, env=None, on_log=None) -> None:
    _log(on_log, f"$ {' '.join(cmd)}")
    process = subprocess.Popen(
        cmd,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if process.stdout:
        for line in iter(process.stdout.readline, b""):
            if not line:
                break
            decoded = _decode_process_output(line).rstrip("\r\n")
            _log(on_log, decoded)
        process.stdout.close()
    return_code = process.wait()
    if return_code != 0:
        raise RuntimeError(f"command failed: {cmd[0]} (exit {return_code})")


def _run_cmd_capture(cmd, cwd=None, env=None, on_log=None) -> str:
    _log(on_log, f"$ {' '.join(cmd)}")
    process = subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    output = _decode_process_output(process.stdout or b"")
    for line in output.splitlines():
        _log(on_log, line.rstrip())
    if process.returncode != 0:
        raise RuntimeError(f"command failed: {cmd[0]} (exit {process.returncode})")
    return output


def _normalize_sha256_fingerprint(value: str) -> str:
    return re.sub(r"[^0-9A-Fa-f]", "", str(value or "")).upper()


def _extract_sha256_fingerprint(text: str) -> Optional[str]:
    if not text:
        return None
    match = re.search(r"SHA-?256(?:\s+digest)?\s*:\s*([0-9A-Fa-f:]{32,})", text, re.IGNORECASE)
    if not match:
        return None
    normalized = _normalize_sha256_fingerprint(match.group(1))
    return normalized or None


def _get_keystore_certificate_sha256(
    keytool: str,
    keystore_file: Path,
    env: Dict[str, str],
    on_log=None,
) -> str:
    output = _run_cmd_capture([
        keytool,
        "-list",
        "-v",
        "-keystore", str(keystore_file),
        "-alias", env.get("KEY_ALIAS", "key0"),
        "-storepass", env.get("KEYSTORE_PASSWORD", "android"),
        "-keypass", env.get("KEY_PASSWORD", "android"),
    ], env=env, on_log=on_log)
    fingerprint = _extract_sha256_fingerprint(output)
    if not fingerprint:
        raise RuntimeError("未能从 keystore 中解析出 SHA-256 指纹")
    return fingerprint


def _get_apk_certificate_sha256(
    apksigner: str,
    apk_file: Path,
    env: Dict[str, str],
    on_log=None,
) -> str:
    output = _run_cmd_capture([
        str(apksigner),
        "verify",
        "--verbose",
        "--print-certs",
        str(apk_file),
    ], env=env, on_log=on_log)
    fingerprint = _extract_sha256_fingerprint(output)
    if not fingerprint:
        raise RuntimeError("未能从 APK 中解析出 SHA-256 指纹")
    return fingerprint


def _get_jar_certificate_sha256(
    keytool: str,
    artifact_file: Path,
    env: Dict[str, str],
    on_log=None,
) -> str:
    output = _run_cmd_capture([
        keytool,
        "-printcert",
        "-jarfile",
        str(artifact_file),
    ], env=env, on_log=on_log)
    fingerprint = _extract_sha256_fingerprint(output)
    if not fingerprint:
        raise RuntimeError("未能从产物中解析出 SHA-256 指纹")
    return fingerprint


def _verify_signed_artifact_matches_keystore(
    artifact_file: Path,
    artifact_format: str,
    keytool: str,
    env: Dict[str, str],
    on_log=None,
    apksigner: Optional[str] = None,
) -> None:
    keystore_file = Path(env["TASK_KEYSTORE_DIR"]) / "release.keystore"
    keystore_sha256 = _get_keystore_certificate_sha256(keytool, keystore_file, env, on_log=on_log)
    if artifact_format == "aab":
        artifact_sha256 = _get_jar_certificate_sha256(keytool, artifact_file, env, on_log=on_log)
    else:
        if not apksigner:
            raise RuntimeError("缺少 apksigner，无法校验 APK 签名")
        artifact_sha256 = _get_apk_certificate_sha256(apksigner, artifact_file, env, on_log=on_log)
    if artifact_sha256 != keystore_sha256:
        raise RuntimeError(
            f"签名校验失败：产物证书指纹与 keystore 不一致 ({artifact_sha256} != {keystore_sha256})"
        )
    _log(on_log, f"[Sign] 签名指纹校验通过: {artifact_sha256}")


def _read_package_json(package_json: Path) -> Dict:
    with package_json.open("r", encoding="utf-8") as f:
        return json.load(f)


def _has_dep(pkg: Dict, name: str) -> bool:
    return name in pkg.get("dependencies", {}) or name in pkg.get("devDependencies", {})


def _get_dep_version(pkg: Dict, name: str) -> Optional[str]:
    for group in ("dependencies", "devDependencies"):
        group_deps = pkg.get(group, {})
        if name in group_deps:
            return str(group_deps[name])
    return None


def _dep_matches_major(dep_version: Optional[str], force_major: Optional[int]) -> bool:
    if dep_version is None:
        return False
    if force_major is None:
        return True
    major_match = re.search(r"(\d+)", dep_version)
    if not major_match:
        return False
    return int(major_match.group(1)) == force_major


def _resolve_node_tool(env: Dict[str, str], tool: str) -> str:
    node_home = env.get("NODE_HOME", "").strip()
    if node_home:
        suffix = ".cmd" if os.name == "nt" else ""
        candidate = Path(node_home) / f"{tool}{suffix}"
        if candidate.exists():
            return str(candidate)
    return tool


def _ensure_dep(
    pkg: Dict,
    env: Dict[str, str],
    name: str,
    dev: bool,
    on_log=None,
    force_major: Optional[int] = None,
) -> None:
    current_version = _get_dep_version(pkg, name)
    if _dep_matches_major(current_version, force_major):
        return
    npm_cmd = _resolve_node_tool(env, "npm")
    install_cmd = [npm_cmd, "install"]
    if dev:
        install_cmd.append("-D")
    package_name = f"{name}@^{force_major}" if force_major is not None else name
    install_cmd.append(package_name)
    install_cmd.append("--legacy-peer-deps")
    _run_cmd(install_cmd, cwd=pkg["_root"], env=env, on_log=on_log)

def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()

def _npm_marker_path(project_root: Path) -> Path:
    marker_dir = project_root / ".convertapk"
    marker_dir.mkdir(parents=True, exist_ok=True)
    return marker_dir / "npm-install.json"

def _npm_lockfile(project_root: Path) -> Optional[Path]:
    candidates = [
        project_root / "package-lock.json",
        project_root / "package.json",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None

def _should_skip_npm_install(project_root: Path, on_log=None) -> bool:
    node_modules = project_root / "node_modules"
    lockfile = _npm_lockfile(project_root)
    if not node_modules.exists() or not lockfile:
        return False
    marker_path = _npm_marker_path(project_root)
    if not marker_path.exists():
        return False
    try:
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
        current_hash = _hash_file(lockfile)
        if marker.get("lockfile") == lockfile.name and marker.get("hash") == current_hash:
            _log(on_log, "[NPM] node_modules unchanged; skipping npm install")
            return True
    except Exception:
        return False
    return False

def _mark_npm_install(project_root: Path) -> None:
    lockfile = _npm_lockfile(project_root)
    if not lockfile:
        return
    marker_path = _npm_marker_path(project_root)
    marker = {
        "lockfile": lockfile.name,
        "hash": _hash_file(lockfile),
    }
    marker_path.write_text(json.dumps(marker, ensure_ascii=False, indent=2), encoding="utf-8")

_SAFE_AREA_TOP_MARKERS = (
    "var(--convertapk-safe-top",
    "--convertapk-safe-top",
)
_SAFE_AREA_BOTTOM_MARKERS = (
    "safe-area-inset-bottom",
    "--convertapk-safe-bottom",
)
_SAFE_AREA_SCAN_EXTENSIONS = {
    ".html",
    ".htm",
    ".css",
    ".js",
    ".mjs",
    ".cjs",
    ".ts",
    ".tsx",
    ".vue",
}
_SAFE_AREA_SCAN_MAX_BYTES = 2 * 1024 * 1024

def _detect_file_safe_area(file_path: Path) -> Tuple[bool, bool]:
    if file_path.suffix.lower() not in _SAFE_AREA_SCAN_EXTENSIONS:
        return False, False
    try:
        with file_path.open("rb") as handle:
            raw = handle.read(_SAFE_AREA_SCAN_MAX_BYTES)
    except Exception:
        return False, False
    text = raw.decode("utf-8", errors="ignore")
    if not text:
        return False, False
    has_top = any(marker in text for marker in _SAFE_AREA_TOP_MARKERS)
    has_bottom = any(marker in text for marker in _SAFE_AREA_BOTTOM_MARKERS)
    return has_top, has_bottom

def _detect_safe_area_usage(
    project_root: Path,
    android_app_dir: Path,
    on_log: Optional[Callable[[str], None]] = None,
) -> Tuple[bool, bool]:
    candidates = [
        project_root / "index.html",
        project_root / "src",
        project_root / "dist",
        project_root / "build",
        android_app_dir / "src" / "main" / "assets" / "public",
    ]
    seen = set()
    top_detected = False
    bottom_detected = False
    for candidate in candidates:
        if not candidate.exists():
            continue
        files = [candidate] if candidate.is_file() else candidate.rglob("*")
        for file_path in files:
            if not file_path.is_file():
                continue
            if "node_modules" in file_path.parts or ".git" in file_path.parts or ".gradle" in file_path.parts:
                continue
            try:
                key = str(file_path.resolve())
            except Exception:
                key = str(file_path)
            if key in seen:
                continue
            seen.add(key)
            has_top, has_bottom = _detect_file_safe_area(file_path)
            if not has_top and not has_bottom:
                continue
            try:
                display_path = file_path.relative_to(project_root)
            except Exception:
                display_path = file_path
            if has_top and not top_detected:
                top_detected = True
                _log(on_log, f"[Insets] detected safe-area top usage: {display_path}")
            if has_bottom and not bottom_detected:
                bottom_detected = True
                _log(on_log, f"[Insets] detected safe-area bottom usage: {display_path}")
            if top_detected and bottom_detected:
                return True, True
    if not top_detected:
        _log(on_log, "[Insets] safe-area top usage not detected")
    if not bottom_detected:
        _log(on_log, "[Insets] safe-area bottom usage not detected")
    return top_detected, bottom_detected

def _sync_existing_insets_padding_flags(
    source: str,
    is_kotlin: bool,
    use_webview_top_padding: bool,
    use_webview_bottom_padding: bool,
) -> str:
    top_literal = "true" if use_webview_top_padding else "false"
    bottom_literal = "true" if use_webview_bottom_padding else "false"
    if is_kotlin:
        source = re.sub(
            r"(?m)^(\s*)val\s+useWebViewPadding\s*=\s*(?:true|false)\s*$",
            rf"\1val useWebViewTopPadding = {top_literal}\n\1val useWebViewBottomPadding = {bottom_literal}",
            source,
        )
        source = re.sub(
            r"(?m)^(\s*)val\s+useWebViewTopPadding\s*=\s*(?:true|false)\s*$",
            rf"\1val useWebViewTopPadding = {top_literal}",
            source,
        )
        source = re.sub(
            r"(?m)^(\s*)val\s+useWebViewBottomPadding\s*=\s*(?:true|false)\s*$",
            rf"\1val useWebViewBottomPadding = {bottom_literal}",
            source,
        )
        source = source.replace(
            "val shouldApplyTopInset = useWebViewPadding &&",
            "val shouldApplyTopInset = useWebViewTopPadding &&",
        )
        source = source.replace(
            "val bottomInset = if (useWebViewPadding) nav.bottom else 0",
            "val bottomInset = if (useWebViewBottomPadding) nav.bottom else 0",
        )
    else:
        source = re.sub(
            r"(?m)^(\s*)final\s+boolean\s+useWebViewPadding\s*=\s*(?:true|false)\s*;\s*$",
            rf"\1final boolean useWebViewTopPadding = {top_literal};\n\1final boolean useWebViewBottomPadding = {bottom_literal};",
            source,
        )
        source = re.sub(
            r"(?m)^(\s*)final\s+boolean\s+useWebViewTopPadding\s*=\s*(?:true|false)\s*;\s*$",
            rf"\1final boolean useWebViewTopPadding = {top_literal};",
            source,
        )
        source = re.sub(
            r"(?m)^(\s*)final\s+boolean\s+useWebViewBottomPadding\s*=\s*(?:true|false)\s*;\s*$",
            rf"\1final boolean useWebViewBottomPadding = {bottom_literal};",
            source,
        )
        source = source.replace(
            "boolean shouldApplyTopInset = useWebViewPadding &&",
            "boolean shouldApplyTopInset = useWebViewTopPadding &&",
        )
        source = source.replace(
            "int bottomInset = useWebViewPadding ? nav.bottom : 0;",
            "int bottomInset = useWebViewBottomPadding ? nav.bottom : 0;",
        )
    return source

def _strip_navigation_bar_hide_flags(source: str) -> str:
    source = re.sub(
        r"(?m)^\s*controller\.systemBarsBehavior\s*=\s*WindowInsetsControllerCompat\.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE\s*$\n?",
        "",
        source,
    )
    source = re.sub(
        r"(?m)^\s*controller\.setSystemBarsBehavior\(\s*WindowInsetsControllerCompat\.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE\s*\)\s*;\s*$\n?",
        "",
        source,
    )
    source = re.sub(
        r"(?m)^\s*controller\.setSystemBarsBehavior\(\s*android\.view\.WindowInsetsController\.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE\s*\)\s*;\s*$\n?",
        "",
        source,
    )
    source = source.replace(" | View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY", "")
    source = source.replace(" | android.view.View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY", "")
    source = source.replace(" | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION", "")
    source = source.replace(" | android.view.View.SYSTEM_UI_FLAG_HIDE_NAVIGATION", "")
    source = re.sub(
        r"(?m)^(\s*)controller\.hide\(WindowInsetsCompat\.Type\.statusBars\(\)\)\s*(?:\n\1controller\.show\(WindowInsetsCompat\.Type\.navigationBars\(\)\))?\s*$",
        r"\1controller.hide(WindowInsetsCompat.Type.statusBars())\n\1controller.show(WindowInsetsCompat.Type.navigationBars())",
        source,
    )
    source = re.sub(
        r"(?m)^(\s*)controller\.hide\(android\.view\.WindowInsets\.Type\.statusBars\(\)\)\s*;\s*(?:\n\1controller\.show\(android\.view\.WindowInsets\.Type\.navigationBars\(\)\)\s*;)?\s*$",
        r"\1controller.hide(android.view.WindowInsets.Type.statusBars());\n\1controller.show(android.view.WindowInsets.Type.navigationBars());",
        source,
    )
    return source


def _pack_android_source(
    android_project_root: Path,
    task_output_dir: Path,
    app_name: str,
    version_name: str,
    on_log: Optional[Callable[[str], None]] = None,
) -> Optional[Path]:
    if not android_project_root.exists():
        return None
    archive_name = f"{app_name or 'app'}-v{version_name or '1.0.0'}-android-source.zip"
    archive_path = task_output_dir / archive_name
    ignore_prefixes = (
        "app/build/",
        "build/",
        ".gradle/",
        ".git/",
        "node_modules/",
        ".idea/",
    )
    try:
        if archive_path.exists():
            archive_path.unlink()
        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for item in android_project_root.rglob("*"):
                if item.is_dir():
                    continue
                rel = item.relative_to(android_project_root).as_posix()
                if any(rel == prefix[:-1] or rel.startswith(prefix) for prefix in ignore_prefixes):
                    continue
                zf.write(item, rel)
        _log(on_log, f"[Android] 源码包已生成: {archive_path}")
        return archive_path
    except Exception as exc:
        _log(on_log, f"[Android] 源码包生成失败: {exc}")
        return None

def _assets_cache_root() -> Path:
    base = Path(os.getenv("APPDATA", "."))
    return base / "ConvertAPK" / "cache" / "capacitor-assets"

def _resolve_assets_bin(cache_root: Path) -> Optional[Path]:
    assets_pkg = cache_root / "node_modules" / "@capacitor" / "assets" / "package.json"
    if assets_pkg.exists():
        try:
            data = json.loads(assets_pkg.read_text(encoding="utf-8"))
            bin_entry = data.get("bin")
            if isinstance(bin_entry, str):
                candidate = cache_root / "node_modules" / bin_entry
                if candidate.exists():
                    return candidate
            if isinstance(bin_entry, dict):
                for value in bin_entry.values():
                    candidate = cache_root / "node_modules" / value
                    if candidate.exists():
                        return candidate
        except Exception:
            pass
    suffix = ".cmd" if os.name == "nt" else ""
    fallback = cache_root / "node_modules" / ".bin" / f"capacitor-assets{suffix}"
    if fallback.exists():
        return fallback
    return None

def _ensure_assets_cache(env: Dict[str, str], on_log=None) -> Optional[Tuple[Path, Path]]:
    cache_root = _assets_cache_root()
    cache_root.mkdir(parents=True, exist_ok=True)
    package_json = cache_root / "package.json"
    if not package_json.exists():
        package_json.write_text(
            json.dumps({"name": "convertapk-assets-cache", "private": True}, indent=2),
            encoding="utf-8",
        )
    assets_bin = _resolve_assets_bin(cache_root)
    if assets_bin:
        return assets_bin, cache_root
    npm_cmd = _resolve_node_tool(env, "npm")
    assets_package = os.getenv("CONVERTAPK_CAPACITOR_ASSETS_PACKAGE", "@capacitor/assets@3.0.5").strip() or "@capacitor/assets@3.0.5"
    _run_cmd([npm_cmd, "install", "-D", assets_package, "--legacy-peer-deps"], cwd=cache_root, env=env, on_log=on_log)
    assets_bin = _resolve_assets_bin(cache_root)
    if assets_bin:
        return assets_bin, cache_root
    return None

def _run_assets_generate(project_root: Path, env: Dict[str, str], npx_cmd: str, on_log=None) -> None:
    cached = _ensure_assets_cache(env, on_log=on_log)
    if cached:
        assets_bin, cache_root = cached
        assets_env = env.copy()
        assets_env["NODE_PATH"] = str(cache_root / "node_modules")
        assets_env["PATH"] = f"{assets_bin.parent}{os.pathsep}{assets_env.get('PATH', '')}"
        _run_cmd([str(assets_bin), "generate", "--android"], cwd=project_root, env=assets_env, on_log=on_log)
        return
    _run_cmd([npx_cmd, "@capacitor/assets", "generate", "--android"], cwd=project_root, env=env, on_log=on_log)


def _find_android_home() -> Path:
    android_home = os.getenv("ANDROID_HOME", "").strip() or os.getenv("ANDROID_SDK_ROOT", "").strip()
    if not android_home:
        status = env_setup.get_status()
        android_home = str(status.get("paths", {}).get("android", "")).strip()
    if not android_home:
        raise RuntimeError("ANDROID_HOME/ANDROID_SDK_ROOT not set")
    return Path(android_home)


def _version_key(text: str) -> tuple:
    parts = []
    for part in text.split("."):
        try:
            parts.append(int(part))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def _find_build_tool(android_home: Path, tool_name: str) -> Path:
    build_tools_dir = android_home / "build-tools"
    if not build_tools_dir.exists():
        raise RuntimeError("未找到 Android build-tools 目录")
    versions = sorted(
        [p for p in build_tools_dir.iterdir() if p.is_dir()],
        key=lambda p: _version_key(p.name)
    )
    for version_dir in reversed(versions):
        candidate = version_dir / tool_name
        if candidate.exists():
            return candidate
    raise RuntimeError(f"未找到 {tool_name} (Android build-tools)")


def _patch_gradle_wrapper(android_project_root: Path, on_log=None) -> None:
    wrapper_props = android_project_root / "gradle" / "wrapper" / "gradle-wrapper.properties"
    if not wrapper_props.exists():
        return
    text = wrapper_props.read_text(encoding="utf-8")
    default_url = "https://mirrors.cloud.tencent.com/gradle/gradle-8.14.3-all.zip"
    override_url = os.getenv("CONVERTAPK_GRADLE_DISTRIBUTION_URL", "").strip()
    target_url = override_url or default_url
    updated = False
    safe_url = target_url.replace(":", "\\:").replace("/", "\\/")
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.strip().startswith("distributionUrl="):
            key = line.split("=", 1)[0]
            lines[i] = f"{key}={safe_url}"
            updated = True
            break
    if not updated and "services.gradle.org/distributions/" in text:
        text = re.sub(
            r"https?://services\\.gradle\\.org/distributions/gradle-[^\\s]+",
            target_url,
            text
        )
        updated = True
        lines = text.splitlines()
    if updated:
        wrapper_props.write_text("\n".join(lines) + "\n", encoding="utf-8")
        _log(on_log, f"[Gradle] Using distribution mirror: {target_url}")


def _is_valid_gradle_wrapper_jar(jar_path: Path) -> bool:
    if not jar_path.exists() or jar_path.stat().st_size <= 0:
        return False
    try:
        with zipfile.ZipFile(jar_path, "r") as archive:
            return "org/gradle/wrapper/GradleWrapperMain.class" in archive.namelist()
    except Exception:
        return False


def _resolve_template_gradle_wrapper_jar() -> Optional[Path]:
    templates_root = _resolve_templates_root()
    candidates = [
        templates_root / "Tubbim" / "gradle" / "wrapper" / "gradle-wrapper.jar",
        templates_root / "HTML2APK" / "gradle" / "wrapper" / "gradle-wrapper.jar",
    ]
    for candidate in candidates:
        if _is_valid_gradle_wrapper_jar(candidate):
            return candidate
    return None


def _extract_gradle_version_from_wrapper_props(wrapper_props: Path) -> str:
    default_version = "8.14.3"
    if not wrapper_props.exists():
        return default_version
    try:
        text = wrapper_props.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return default_version
    match = re.search(r"gradle-([0-9]+(?:\.[0-9]+)+)-", text)
    if match:
        return match.group(1)
    return default_version


def _repair_gradle_wrapper_jar(android_project_root: Path, on_log=None) -> None:
    wrapper_props = android_project_root / "gradle" / "wrapper" / "gradle-wrapper.properties"
    wrapper_jar = android_project_root / "gradle" / "wrapper" / "gradle-wrapper.jar"
    if _is_valid_gradle_wrapper_jar(wrapper_jar):
        return

    _log(on_log, "[Gradle] 检测到 gradle-wrapper.jar 缺失或损坏，尝试自动修复...")
    wrapper_jar.parent.mkdir(parents=True, exist_ok=True)

    template_jar = _resolve_template_gradle_wrapper_jar()
    if template_jar:
        try:
            shutil.copy2(template_jar, wrapper_jar)
            if _is_valid_gradle_wrapper_jar(wrapper_jar):
                _log(on_log, f"[Gradle] 已通过模板修复 gradle-wrapper.jar: {template_jar}")
                return
        except Exception:
            pass

    gradle_version = _extract_gradle_version_from_wrapper_props(wrapper_props)
    download_urls = [
        f"https://raw.githubusercontent.com/gradle/gradle/v{gradle_version}/gradle/wrapper/gradle-wrapper.jar",
        "https://raw.githubusercontent.com/gradle/gradle/v8.14.3/gradle/wrapper/gradle-wrapper.jar",
    ]
    temp_file = wrapper_jar.with_suffix(".jar.tmp")
    for url in download_urls:
        _log(on_log, f"[Gradle] 尝试下载 gradle-wrapper.jar: {url}")
        try:
            with urllib.request.urlopen(url, timeout=20) as response:
                data = response.read()
            temp_file.write_bytes(data)
            if _is_valid_gradle_wrapper_jar(temp_file):
                temp_file.replace(wrapper_jar)
                _log(on_log, "[Gradle] 已下载并修复 gradle-wrapper.jar")
                return
        except (urllib.error.URLError, TimeoutError, OSError):
            pass
        finally:
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except Exception:
                    pass

    raise RuntimeError("gradle-wrapper.jar 已损坏且自动修复失败")


def _write_gradle_init(task_dir: Path, on_log=None) -> Path:
    init_script = task_dir / "gradle-init.gradle"
    mirror_public = os.getenv("CONVERTAPK_GRADLE_MAVEN_PUBLIC", "https://maven.aliyun.com/repository/public").strip()
    mirror_google = os.getenv("CONVERTAPK_GRADLE_MAVEN_GOOGLE", "https://maven.aliyun.com/repository/google").strip()
    mirror_plugin = os.getenv("CONVERTAPK_GRADLE_MAVEN_PLUGIN", "https://maven.aliyun.com/repository/gradle-plugin").strip()
    script = f"""gradle.settingsEvaluated {{ settings ->
    try {{
        settings.pluginManagement {{
            repositories {{
                maven {{ url '{mirror_plugin}' }}
                mavenCentral()
                google()
            }}
        }}
    }} catch (Exception ignored) {{}}
    try {{
        def drm = settings.dependencyResolutionManagement
        if (drm != null) {{
            try {{
                drm.repositoriesMode.set(org.gradle.api.initialization.resolve.RepositoriesMode.PREFER_SETTINGS)
            }} catch (Exception ignored) {{}}
            drm.repositories {{
                maven {{ url '{mirror_public}' }}
                maven {{ url '{mirror_google}' }}
                maven {{ url '{mirror_plugin}' }}
                mavenCentral()
                google()
            }}
        }}
    }} catch (Exception ignored) {{}}
}}
"""
    init_script.write_text(script, encoding="utf-8")
    _log(on_log, f"[Gradle] Using Maven mirrors: {mirror_public}, {mirror_google}, {mirror_plugin}")
    return init_script

def _ensure_gradle_properties(android_project_root: Path, on_log=None) -> None:
    gradle_props = android_project_root / "gradle.properties"
    text = ""
    if gradle_props.exists():
        text = gradle_props.read_text(encoding="utf-8")
    lines = text.splitlines()
    desired = {
        "org.gradle.parallel": "true",
        "org.gradle.caching": "true",
    }
    updated = False
    existing = {line.split("=", 1)[0].strip(): line for line in lines if "=" in line}
    for key, value in desired.items():
        entry = f"{key}={value}"
        if key not in existing:
            lines.append(entry)
            updated = True
        elif existing[key].strip() != entry:
            lines = [entry if line.startswith(f"{key}=") else line for line in lines]
            updated = True
    if updated:
        gradle_props.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
        _log(on_log, "[Gradle] Enabled build cache and parallel execution")


def _find_java_tool(env: Dict[str, str], tool: str) -> Optional[str]:
    java_home = env.get("JAVA_HOME", "").strip()
    if java_home:
        candidate = Path(java_home) / "bin" / (f"{tool}.exe" if os.name == "nt" else tool)
        if candidate.exists():
            return str(candidate)
    return shutil.which(tool, path=env.get("PATH", ""))

def _resolve_templates_root() -> Path:
    resources_root = os.getenv("ELECTRON_RESOURCES", "").strip()
    if resources_root:
        return Path(resources_root) / "templates"
    if getattr(sys, "_MEIPASS", ""):
        return Path(sys._MEIPASS) / "templates"
    return Path(__file__).resolve().parents[2] / "templates"


def _extract_zip_safely(archive_path: Path, dst_dir: Path) -> None:
    with zipfile.ZipFile(archive_path, "r") as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            raw_name = str(info.filename or "").replace("\\", "/").strip()
            if not raw_name:
                continue
            normalized = PurePosixPath(raw_name.lstrip("/"))
            parts = [part for part in normalized.parts if part and part != "."]
            if not parts or any(part == ".." for part in parts):
                continue
            target_path = dst_dir.joinpath(*parts)
            target_path.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info, "r") as source, target_path.open("wb") as output:
                shutil.copyfileobj(source, output)


_text_encoding_extensions = {
    ".html", ".htm", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx",
    ".css", ".scss", ".less", ".json", ".md", ".txt", ".vue",
    ".xml", ".yml", ".yaml", ".java", ".kt", ".properties",
}


def _normalize_text_file_to_utf8(path: Path) -> bool:
    """将常见中文本编码（GB18030/GBK）归一化为 UTF-8。"""
    try:
        raw = path.read_bytes()
    except Exception:
        return False
    if not raw or b"\x00" in raw:
        return False
    try:
        raw.decode("utf-8")
        return False
    except UnicodeDecodeError:
        pass
    for encoding in ("gb18030", "gbk"):
        try:
            text = raw.decode(encoding)
            path.write_text(text, encoding="utf-8")
            return True
        except UnicodeDecodeError:
            continue
        except Exception:
            return False
    return False


def _normalize_project_text_encodings(project_root: Path, on_log=None) -> int:
    """扫描项目文本文件并尝试转换到 UTF-8，减少中文乱码。"""
    converted = 0
    for file_path in project_root.rglob("*"):
        if not file_path.is_file():
            continue
        suffix = file_path.suffix.lower()
        if suffix not in _text_encoding_extensions:
            continue
        # 跳过超大文本，避免影响构建性能。
        try:
            if file_path.stat().st_size > 5 * 1024 * 1024:
                continue
        except Exception:
            continue
        if _normalize_text_file_to_utf8(file_path):
            converted += 1
    if converted:
        _log(on_log, f"[Encoding] 已将 {converted} 个文本文件转换为 UTF-8")
    return converted


def _pick_index_html(root_dir: Path) -> Path:
    candidates: list[tuple[int, int, Path]] = []
    for file_path in root_dir.rglob("index.html"):
        if not file_path.is_file():
            continue
        lower_parts = {part.lower() for part in file_path.parts}
        if {"node_modules", ".git", "__macosx", "android"} & lower_parts:
            continue
        relative_path = file_path.relative_to(root_dir)
        display_path = str(relative_path).replace("\\", "/")
        candidates.append((len(relative_path.parts), len(display_path), file_path))
    if not candidates:
        raise RuntimeError("ZIP 中未找到 index.html")
    candidates.sort(key=lambda item: (item[0], item[1], str(item[2])))
    return candidates[0][2]


def _find_web_build_dir(project_root: Path) -> Path:
    for dirname in ("dist", "build", "out"):
        candidate = project_root / dirname
        if candidate.exists() and (candidate / "index.html").exists():
            return candidate
    raise RuntimeError("未找到 Web 构建产物目录（dist/build/out）")


_WEB_ASSET_TEXT_EXTENSIONS = {
    ".html",
    ".htm",
    ".js",
    ".mjs",
    ".cjs",
    ".css",
    ".json",
    ".map",
    ".txt",
    ".xml",
    ".svg",
    ".webmanifest",
}
_WEB_ASSET_TEXT_SCAN_MAX_BYTES = 20 * 1024 * 1024


def _web_asset_rank(web_dir: Path, file_path: Path) -> Tuple[int, int, int, str]:
    relative_path = file_path.relative_to(web_dir)
    normalized = str(relative_path).replace("\\", "/")
    parts = relative_path.parts
    first_part = parts[0].lower() if parts else ""
    return (1 if first_part == "assets" else 0, len(parts), len(normalized), normalized)


def _iter_web_text_files(web_dir: Path):
    for file_path in web_dir.rglob("*"):
        if not file_path.is_file():
            continue
        if file_path.suffix.lower() not in _WEB_ASSET_TEXT_EXTENSIONS:
            continue
        try:
            file_size = int(file_path.stat().st_size or 0)
        except Exception:
            continue
        if file_size <= 0 or file_size > _WEB_ASSET_TEXT_SCAN_MAX_BYTES:
            continue
        yield file_path


def _read_utf8_text(path: Path) -> Optional[str]:
    try:
        raw = path.read_bytes()
    except Exception:
        return None
    if not raw or b"\x00" in raw:
        return None
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _build_asset_reference_pairs(source_relative: str, target_relative: str) -> Dict[str, str]:
    source = str(source_relative or "").replace("\\", "/").lstrip("/")
    target = str(target_relative or "").replace("\\", "/").lstrip("/")
    if not source or not target:
        return {}
    pairs = {}
    variants = (
        (f"/{source}", f"/{target}"),
        (f"./{source}", f"./{target}"),
        (source, target),
    )
    for from_ref, to_ref in variants:
        if from_ref != to_ref:
            pairs[from_ref] = to_ref
    return pairs


def _replace_text_batch(content: str, replacements: list[Tuple[str, str]]) -> Tuple[str, int]:
    replaced_count = 0
    updated = content
    for source, target in replacements:
        if source == target:
            continue
        current_count = updated.count(source)
        if current_count <= 0:
            continue
        updated = updated.replace(source, target)
        replaced_count += current_count
    return updated, replaced_count


def _dedupe_web_build_assets(web_dir: Path, on_log=None) -> None:
    if not web_dir.exists():
        return
    file_groups: Dict[Tuple[int, str], list[Path]] = {}
    for file_path in web_dir.rglob("*"):
        if not file_path.is_file():
            continue
        try:
            file_size = int(file_path.stat().st_size or 0)
        except Exception:
            continue
        if file_size <= 0:
            continue
        digest = hashlib.sha256()
        try:
            with file_path.open("rb") as handle:
                while True:
                    chunk = handle.read(1024 * 1024)
                    if not chunk:
                        break
                    digest.update(chunk)
        except Exception:
            continue
        key = (file_size, digest.hexdigest())
        file_groups.setdefault(key, []).append(file_path)

    dedupe_jobs = []
    all_old_refs: set[str] = set()
    for _, candidates in file_groups.items():
        if len(candidates) < 2:
            continue
        ordered = sorted(candidates, key=lambda item: _web_asset_rank(web_dir, item))
        canonical = ordered[0]
        canonical_relative = str(canonical.relative_to(web_dir)).replace("\\", "/")
        for duplicate in ordered[1:]:
            duplicate_relative = str(duplicate.relative_to(web_dir)).replace("\\", "/")
            if duplicate_relative == canonical_relative:
                continue
            reference_pairs = _build_asset_reference_pairs(duplicate_relative, canonical_relative)
            dedupe_jobs.append(
                {
                    "duplicate_path": duplicate,
                    "reference_pairs": reference_pairs,
                }
            )
            all_old_refs.update(reference_pairs.keys())

    if not dedupe_jobs:
        return

    replacement_map: Dict[str, str] = {}
    for job in dedupe_jobs:
        for source, target in job["reference_pairs"].items():
            replacement_map[source] = target
    replacements = sorted(replacement_map.items(), key=lambda item: len(item[0]), reverse=True)

    replaced_files = 0
    replaced_refs = 0
    if replacements:
        for text_file in _iter_web_text_files(web_dir):
            content = _read_utf8_text(text_file)
            if content is None:
                continue
            updated, current_replaced = _replace_text_batch(content, replacements)
            if current_replaced <= 0:
                continue
            text_file.write_text(updated, encoding="utf-8")
            replaced_files += 1
            replaced_refs += current_replaced

    remaining_refs: set[str] = set()
    if all_old_refs:
        needles = sorted(all_old_refs, key=len, reverse=True)
        for text_file in _iter_web_text_files(web_dir):
            content = _read_utf8_text(text_file)
            if content is None:
                continue
            for needle in needles:
                if needle in content:
                    remaining_refs.add(needle)
            if len(remaining_refs) == len(all_old_refs):
                break

    removed_files = 0
    removed_bytes = 0
    skipped_files = 0
    for job in dedupe_jobs:
        duplicate_path = job["duplicate_path"]
        reference_pairs = job["reference_pairs"]
        if any(old_ref in remaining_refs for old_ref in reference_pairs.keys()):
            skipped_files += 1
            continue
        try:
            removed_bytes += int(duplicate_path.stat().st_size or 0)
            duplicate_path.unlink()
            removed_files += 1
        except Exception:
            skipped_files += 1
            continue

    if removed_files > 0:
        saved_mb = removed_bytes / (1024 * 1024)
        _log(
            on_log,
            f"[Web] 静态资源去重完成：删除 {removed_files} 个重复文件，约节省 {saved_mb:.2f} MB，替换引用 {replaced_refs} 处",
        )
    if skipped_files > 0:
        _log(on_log, f"[Web] 有 {skipped_files} 个重复文件仍存在引用，已跳过删除以确保兼容")
    if replaced_files > 0 and removed_files <= 0:
        _log(on_log, f"[Web] 已更新 {replaced_files} 个文件中的资源引用，但未删除重复文件")


def _is_next_project(pkg: Dict) -> bool:
    return _has_dep(pkg, "next")


def _find_next_config_file(project_root: Path) -> Optional[Path]:
    for filename in ("next.config.ts", "next.config.js", "next.config.mjs", "next.config.cjs"):
        candidate = project_root / filename
        if candidate.is_file():
            return candidate
    return None


def _rewrite_next_config_output_export(content: str) -> Tuple[str, str]:
    output_pattern = re.compile(r"(\boutput\s*:\s*)(['\"])([^'\"\r\n]+)\2")
    match = output_pattern.search(content)
    if match:
        current_value = str(match.group(3) or "").strip().lower()
        if current_value == "export":
            return content, "already_export"
        replacement = f"{match.group(1)}{match.group(2)}export{match.group(2)}"
        updated = output_pattern.sub(replacement, content, count=1)
        return updated, "updated"

    inject_patterns = (
        re.compile(r"(const\s+nextConfig(?:\s*:\s*NextConfig)?\s*=\s*\{)"),
        re.compile(r"(module\.exports\s*=\s*\{)"),
        re.compile(r"(export\s+default\s*\{)"),
    )
    for pattern in inject_patterns:
        if pattern.search(content):
            updated = pattern.sub(r"\1\n  output: 'export',", content, count=1)
            return updated, "injected"

    return content, "no_change"


def _ensure_next_config_output_export(project_root: Path, on_log=None) -> None:
    config_path = _find_next_config_file(project_root)
    if not config_path:
        _log(on_log, "[Next.js] 未找到 next.config.*，跳过 output 自动改写")
        return
    try:
        original = config_path.read_text(encoding="utf-8")
    except Exception as exc:
        _log(on_log, f"[Next.js] 读取 {config_path.name} 失败：{str(exc)}")
        return

    rewritten, status = _rewrite_next_config_output_export(original)
    if status in {"updated", "injected"}:
        config_path.write_text(rewritten, encoding="utf-8")
        _log(on_log, f"[Next.js] 已自动改写 {config_path.name} 为 output: 'export'")
        return
    if status == "already_export":
        _log(on_log, f"[Next.js] {config_path.name} 已是 output: 'export'")
        return
    _log(on_log, f"[Next.js] 未能自动改写 {config_path.name}，将继续尝试导出兜底流程")


def _try_export_next_static_site(
    project_root: Path,
    pkg: Dict,
    npm_cmd: str,
    npx_cmd: str,
    env: Dict[str, str],
    on_log=None,
) -> None:
    scripts = pkg.get("scripts")
    if isinstance(scripts, dict):
        export_script = str(scripts.get("export", "")).strip()
        if export_script:
            _log(on_log, "[Next.js] 检测到 export 脚本，尝试执行 npm run export")
            _run_cmd([npm_cmd, "run", "export"], cwd=project_root, env=env, on_log=on_log)
            return
    _log(on_log, "[Next.js] 未检测到 export 脚本，尝试执行 npx next export")
    _run_cmd([npx_cmd, "next", "export"], cwd=project_root, env=env, on_log=on_log)


def _raise_next_static_export_error() -> None:
    raise RuntimeError(
        "检测到 Next.js 项目，但未生成静态产物目录（out/dist/build）。"
        "convert 模式仅支持静态导出，请在 next.config.* 中设置 output: 'export'，并确保构建后存在 out/index.html。"
    )


def _resolve_default_desktop_icon_ico() -> Optional[Path]:
    candidate = Path(__file__).resolve().parents[2] / "desktop" / "build" / "icon.ico"
    if candidate.exists():
        return candidate
    return None


def _shrink_desktop_web_assets(app_dir: Path, on_log=None) -> None:
    if not app_dir.exists():
        return
    removed_files = 0
    removed_bytes = 0
    removable_suffixes = (".map", ".license.txt", ".licenses.txt")
    for candidate in app_dir.rglob("*"):
        if not candidate.is_file():
            continue
        lower_name = candidate.name.lower()
        if not lower_name.endswith(removable_suffixes):
            continue
        try:
            removed_bytes += candidate.stat().st_size
            candidate.unlink()
            removed_files += 1
        except Exception:
            continue
    if removed_files > 0:
        saved_mb = removed_bytes / (1024 * 1024)
        _log(on_log, f"[Desktop] 清理调试/许可证附加文件: {removed_files} 个，约节省 {saved_mb:.2f} MB")


def _normalize_desktop_installer_mode(value: Optional[str]) -> str:
    raw = str(value or "portable").strip().lower()
    if raw == "portable":
        return "portable"
    return "portable"


def _normalize_desktop_port(value) -> int:
    try:
        port = int(str(value).strip())
    except Exception:
        return 0
    if 1024 <= port <= 65535:
        return port
    return 0


def _sanitize_windows_artifact_base_name(value: str, fallback: str = "DesktopApp") -> str:
    raw = str(value or "").strip()
    if not raw:
        return fallback
    safe = re.sub(r'[<>:"/\\|?*\x00-\x1F]+', "-", raw)
    safe = re.sub(r"\s+", " ", safe).strip().rstrip(" .")
    if not safe or safe in {".", ".."}:
        return fallback
    reserved_names = {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        "COM1",
        "COM2",
        "COM3",
        "COM4",
        "COM5",
        "COM6",
        "COM7",
        "COM8",
        "COM9",
        "LPT1",
        "LPT2",
        "LPT3",
        "LPT4",
        "LPT5",
        "LPT6",
        "LPT7",
        "LPT8",
        "LPT9",
    }
    if safe.upper() in reserved_names:
        safe = f"{safe}-app"
    return safe or fallback


def _write_desktop_wrapper_project(
    wrapper_root: Path,
    app_name: str,
    package_name: str,
    version_name: str,
    desktop_installer_mode: str,
    desktop_port: int,
    source_app_dir: Path,
    logo_path: Optional[Path],
    on_log=None,
) -> str:
    if wrapper_root.exists():
        shutil.rmtree(wrapper_root, ignore_errors=True)
    wrapper_root.mkdir(parents=True, exist_ok=True)

    app_dir = wrapper_root / "app"
    shutil.copytree(source_app_dir, app_dir)
    _shrink_desktop_web_assets(app_dir, on_log=on_log)

    build_dir = wrapper_root / "build"
    build_dir.mkdir(parents=True, exist_ok=True)
    has_custom_logo = bool(logo_path and logo_path.exists())
    if has_custom_logo:
        shutil.copy2(logo_path, build_dir / "icon.png")
        if str(logo_path.suffix).lower() == ".ico":
            shutil.copy2(logo_path, build_dir / "icon.ico")
    default_ico = _resolve_default_desktop_icon_ico()
    if (not has_custom_logo) and default_ico and default_ico.exists():
        shutil.copy2(default_ico, build_dir / "icon.ico")

    safe_npm_name = re.sub(r"[^a-z0-9-]+", "-", str(package_name or "desktop-app").strip().lower()).strip("-")
    if not safe_npm_name:
        safe_npm_name = "desktop-app"
    safe_artifact_name = _sanitize_windows_artifact_base_name(str(app_name or "DesktopApp"), fallback="DesktopApp")
    desktop_target = _normalize_desktop_installer_mode(desktop_installer_mode)
    build_config = {
        "appId": str(package_name or "com.example.desktop"),
        "productName": str(app_name or "DesktopApp"),
        "directories": {"output": "dist"},
        "files": [
            "main.js",
            "preload.js",
            "app/**/*",
            "build/**/*",
        ],
        "asar": True,
        "compression": "maximum",
        "electronLanguages": ["en-US", "zh-CN"],
        "artifactName": f"{safe_artifact_name}.${{ext}}",
        "win": {"target": [{"target": desktop_target, "arch": ["x64"]}]},
    }
    if (build_dir / "icon.ico").exists() or (build_dir / "icon.png").exists():
        build_config["icon"] = "build/icon.ico"
        build_config["win"]["icon"] = "build/icon.ico"

    package_json = {
        "name": safe_npm_name,
        "version": str(version_name or "1.0.0"),
        "description": f"{app_name or 'DesktopApp'} desktop build",
        "main": "main.js",
        "private": True,
        "scripts": {
            "prepare-icon": "node scripts/prepare-icon.js",
            "dist": f"npm run prepare-icon && electron-builder --win {desktop_target} --publish never",
        },
        "devDependencies": {
            "electron": "^30.4.0",
            "electron-builder": "^24.13.3",
            "png-to-ico": "^2.1.8",
        },
        "build": build_config,
    }

    window_title = json.dumps(str(app_name or "DesktopApp"), ensure_ascii=False)
    desktop_port_literal = str(int(desktop_port)) if isinstance(desktop_port, int) and desktop_port > 0 else "0"
    main_js = """const { app, BrowserWindow, shell } = require("electron");
const path = require("path");
const fs = require("fs");
const http = require("http");

const LOCAL_HOST = "127.0.0.1";
const PREFERRED_PORT = __DESKTOP_PORT__;
const appRootDir = path.join(__dirname, "app");
let staticServer = null;
let localOrigin = "";

function getMimeType(filePath) {
  const ext = path.extname(filePath).toLowerCase();
  const mimeMap = {
    ".html": "text/html; charset=utf-8",
    ".htm": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
    ".webp": "image/webp",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
    ".ttf": "font/ttf",
    ".otf": "font/otf",
    ".map": "application/json; charset=utf-8",
    ".txt": "text/plain; charset=utf-8",
    ".wasm": "application/wasm",
  };
  return mimeMap[ext] || "application/octet-stream";
}

function resolveRequestFile(rootDir, requestUrl) {
  let pathname = "/";
  try {
    const parsed = new URL(requestUrl || "/", "http://127.0.0.1");
    pathname = decodeURIComponent(parsed.pathname || "/");
  } catch {
    pathname = "/";
  }
  if (!pathname || pathname === "/") {
    pathname = "/index.html";
  }
  const normalized = path.posix.normalize(pathname);
  const relativePath = normalized.startsWith("/") ? normalized.slice(1) : normalized;
  const safeRelativePath = relativePath.replace(/^\\.\\.(\\/|\\\\|$)+/g, "");
  const candidate = path.resolve(rootDir, safeRelativePath);
  const safeRoot = path.resolve(rootDir);
  if (!candidate.startsWith(safeRoot)) {
    return null;
  }
  if (fs.existsSync(candidate) && fs.statSync(candidate).isFile()) {
    return candidate;
  }
  const fallback = path.join(rootDir, "index.html");
  if (fs.existsSync(fallback) && fs.statSync(fallback).isFile()) {
    return fallback;
  }
  return null;
}

function startStaticServer(rootDir, preferredPort) {
  return new Promise((resolve, reject) => {
    const server = http.createServer((req, res) => {
      const filePath = resolveRequestFile(rootDir, req.url || "/");
      if (!filePath) {
        res.statusCode = 404;
        res.end("Not Found");
        return;
      }
      res.setHeader("Content-Type", getMimeType(filePath));
      const stream = fs.createReadStream(filePath);
      stream.on("error", () => {
        if (!res.headersSent) {
          res.statusCode = 500;
        }
        res.end("Internal Server Error");
      });
      stream.pipe(res);
    });
    const finishListen = () => {
      const address = server.address();
      if (!address || typeof address !== "object") {
        reject(new Error("local static server listen failed"));
        return;
      }
      resolve({
        server,
        origin: `http://${LOCAL_HOST}:${address.port}`,
      });
    };
    const tryListen = (port, fallbackToRandom) => {
      const handleError = (error) => {
        server.off("listening", handleListening);
        if (fallbackToRandom && error && error.code === "EADDRINUSE") {
          console.warn(`[Desktop] preferred port ${port} in use, fallback to random`);
          tryListen(0, false);
          return;
        }
        reject(error);
      };
      const handleListening = () => {
        server.off("error", handleError);
        finishListen();
      };
      server.once("error", handleError);
      server.once("listening", handleListening);
      server.listen(port, LOCAL_HOST);
    };
    const normalizedPreferredPort = Number.isInteger(preferredPort) && preferredPort >= 1024 && preferredPort <= 65535
      ? preferredPort
      : 0;
    tryListen(normalizedPreferredPort, normalizedPreferredPort > 0);
  });
}

function isSameLocalOrigin(url) {
  return Boolean(localOrigin) && String(url || "").startsWith(localOrigin);
}

function createWindow(entryUrl) {
  const iconPath = path.join(__dirname, "build", "icon.png");
  const win = new BrowserWindow({
    title: __WINDOW_TITLE__,
    width: 1280,
    height: 800,
    minWidth: 960,
    minHeight: 640,
    frame: true,
    resizable: true,
    minimizable: true,
    maximizable: true,
    closable: true,
    fullscreenable: true,
    autoHideMenuBar: true,
    backgroundColor: "#111827",
    show: false,
    icon: iconPath,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      sandbox: false,
    },
  });

  win.once("ready-to-show", () => win.show());
  win.webContents.setWindowOpenHandler(({ url }) => {
    if (isSameLocalOrigin(url)) {
      return { action: "allow" };
    }
    shell.openExternal(url);
    return { action: "deny" };
  });
  win.webContents.on("will-navigate", (event, url) => {
    if (isSameLocalOrigin(url)) {
      return;
    }
    event.preventDefault();
    if (String(url || "").startsWith("http://") || String(url || "").startsWith("https://")) {
      shell.openExternal(url);
    }
  });
  if (entryUrl) {
    win.loadURL(entryUrl);
  } else {
    win.loadFile(path.join(__dirname, "app", "index.html"));
  }
}

async function bootstrap() {
  let entryUrl = null;
  try {
    const started = await startStaticServer(appRootDir, PREFERRED_PORT);
    staticServer = started.server;
    localOrigin = started.origin;
    entryUrl = localOrigin;
  } catch (error) {
    console.error(`[Desktop] static server start failed: ${error}`);
  }
  createWindow(entryUrl);
}

app.whenReady().then(() => {
  bootstrap();
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow(localOrigin || null);
    }
  });
});

app.on("before-quit", () => {
  if (staticServer) {
    try {
      staticServer.close();
    } catch {}
    staticServer = null;
  }
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});
"""
    main_js = main_js.replace("__WINDOW_TITLE__", window_title)
    main_js = main_js.replace("__DESKTOP_PORT__", desktop_port_literal)
    preload_js = """const { contextBridge } = require("electron");

contextBridge.exposeInMainWorld("desktopApp", {
  platform: process.platform,
});
"""
    prepare_icon_js = """const fs = require("fs");
const path = require("path");
const pngToIco = require("png-to-ico");

async function main() {
  const buildDir = path.join(__dirname, "..", "build");
  const pngPath = path.join(buildDir, "icon.png");
  const icoPath = path.join(buildDir, "icon.ico");
  if (fs.existsSync(pngPath)) {
    try {
      const buffer = await pngToIco(pngPath);
      fs.writeFileSync(icoPath, buffer);
      console.log(`[Desktop] generated icon.ico from ${pngPath}`);
      return;
    } catch (error) {
      if (fs.existsSync(icoPath)) {
        console.warn(`[Desktop] icon conversion failed, keep existing icon.ico: ${error}`);
        return;
      }
      throw error;
    }
  }
  if (!fs.existsSync(icoPath)) {
    throw new Error("missing icon.png and icon.ico");
  }
}

main().catch((error) => {
  console.error(`[Desktop] prepare icon failed: ${error}`);
  process.exit(1);
});
"""
    scripts_dir = wrapper_root / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)

    (wrapper_root / "package.json").write_text(
        json.dumps(package_json, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (wrapper_root / "main.js").write_text(main_js, encoding="utf-8")
    (wrapper_root / "preload.js").write_text(preload_js, encoding="utf-8")
    (scripts_dir / "prepare-icon.js").write_text(prepare_icon_js, encoding="utf-8")
    _log(on_log, f"[Desktop] Electron wrapper prepared: {wrapper_root}")
    return desktop_target

def _offlineize_html_assets(entry_html: Path, env: Dict[str, str], on_log=None) -> None:
    if not entry_html.exists():
        return
    preprocessed = str(env.get("CDN_LOCALIZE_PREPROCESSED", "false")).strip().lower() == "true"
    if preprocessed:
        _log(on_log, "[HTML] CDN localize preprocessed, skip build-time offlineize")
        return
    enabled = str(env.get("CDN_LOCALIZE_ENABLED", "true")).strip().lower() == "true"
    if not enabled:
        _log(on_log, "[HTML] CDN localize disabled, skip offlineize")
        return
    script_path = Path(__file__).resolve().parents[2] / "apk-worker" / "scripts" / "offlineize_html_assets.mjs"
    if not script_path.exists():
        _log(on_log, f"[HTML] offlineize script not found: {script_path}")
        return
    node_cmd = _resolve_node_tool(env, "node")
    cmd = [node_cmd, str(script_path), str(entry_html)]
    allow_urls: list[str] = []
    raw_allow_json = str(env.get("CDN_LOCALIZE_URLS_JSON", "") or "").strip()
    if raw_allow_json:
        try:
            parsed_allow = json.loads(raw_allow_json)
            if isinstance(parsed_allow, list):
                seen_urls: set[str] = set()
                for item in parsed_allow:
                    url = str(item or "").strip()
                    if not url or url in seen_urls:
                        continue
                    seen_urls.add(url)
                    allow_urls.append(url)
        except Exception as exc:
            _log(on_log, f"[HTML] invalid CDN_LOCALIZE_URLS_JSON, fallback to all links: {exc}")
    for allow_url in allow_urls:
        cmd.extend(["--allow-url", allow_url])
    if allow_urls:
        _log(on_log, f"[HTML] offlineize only selected links: {len(allow_urls)}")
    try:
        _run_cmd(cmd, cwd=entry_html.parent, env=env, on_log=on_log)
    except Exception as exc:
        _log(on_log, f"[HTML] offlineize failed, keep original links: {exc}")

def _normalize_screen_orientation(raw: str) -> str:
    value = (raw or "").strip().lower()
    if value == "portrait":
        return "portrait"
    if value == "landscape":
        return "landscape"
    return ""

def _patch_android_manifest(
    manifest_path: Path,
    screen_orientation: str,
    permissions: list[str],
    on_log=None
) -> None:
    if not manifest_path.exists():
        return
    text = manifest_path.read_text(encoding="utf-8")
    orientation_value = _normalize_screen_orientation(screen_orientation)

    def _apply_orientation_to_tag(tag_text: str) -> str:
        if "android:screenOrientation" in tag_text:
            if not orientation_value:
                return re.sub(r'\s+android:screenOrientation=\"[^\"]*\"', "", tag_text)
            return re.sub(
                r'android:screenOrientation=\"[^\"]*\"',
                f'android:screenOrientation="{orientation_value}"',
                tag_text,
            )
        if not orientation_value:
            return tag_text
        return f'{tag_text} android:screenOrientation="{orientation_value}"'

    def _update_activity_block(block: str) -> str:
        tag_match = re.search(r"(<activity\b[^>]*)(>)", block)
        if not tag_match:
            return block
        updated_tag = _apply_orientation_to_tag(tag_match.group(1))
        return block.replace(tag_match.group(0), f"{updated_tag}{tag_match.group(2)}", 1)

    updated = text
    activity_blocks = list(re.finditer(r"<activity\b[^>]*>.*?</activity>", text, flags=re.DOTALL))
    updated_any = False
    for block_match in activity_blocks:
        block = block_match.group(0)
        if "android.intent.action.MAIN" in block and "android.intent.category.LAUNCHER" in block:
            updated_block = _update_activity_block(block)
            if updated_block != block:
                updated = updated.replace(block, updated_block, 1)
                updated_any = True
            break

    if not updated_any:
        activity_pattern = re.compile(r"(<activity\b[^>]*android:name=\"[^\"]*MainActivity\"[^>]*)(>)")
        def _apply_orientation(match: re.Match) -> str:
            activity_block = _apply_orientation_to_tag(match.group(1))
            return f"{activity_block}{match.group(2)}"
        updated = activity_pattern.sub(_apply_orientation, updated, count=1)
        if updated != text:
            updated_any = True

    if updated_any:
        text = updated
        if orientation_value:
            _log(on_log, f"[Android] screenOrientation => {orientation_value}")
        else:
            _log(on_log, "[Android] screenOrientation cleared (follow system)")

    if permissions:
        existing = set(re.findall(r'uses-permission[^>]+android:name=\"([^\"]+)\"', text))
        missing = [p for p in permissions if p and p not in existing]
        if missing:
            insert_block = "\n".join([f'    <uses-permission android:name="{p}" />' for p in missing])
            if "<application" in text:
                text = text.replace("<application", insert_block + "\n\n    <application", 1)
            else:
                text = text + "\n" + insert_block + "\n"
            _log(on_log, f"[Android] added permissions: {', '.join(missing)}")

    manifest_path.write_text(text, encoding="utf-8")

def _patch_android_build_config(build_gradle: Path, env: Dict[str, str], on_log=None) -> None:
    if not build_gradle.exists():
        return
    text = build_gradle.read_text(encoding="utf-8")
    is_kts = build_gradle.name.endswith(".kts")

    status_bar_hidden = "true" if str(env.get("STATUS_BAR_HIDDEN", "false")).lower() == "true" else "false"
    status_bar_color = str(env.get("STATUS_BAR_COLOR", "#FFFFFF")).strip().lower()
    task_mode = str(env.get("TASK_MODE", "convert")).strip().lower()
    if (
        task_mode == "convert"
        and status_bar_hidden != "true"
        and status_bar_color in {"transparent", "@android:color/transparent"}
    ):
        status_bar_color = "#ffffff"
    status_bar_background = "white" if status_bar_color in {"#ffffff", "white", "#ffffffff"} else "transparent"
    status_bar_style = str(env.get("STATUS_BAR_STYLE", "light")).strip().lower()
    light_status_bar_icons = "true" if status_bar_style == "dark" else "false"
    double_click_exit = "true" if str(env.get("DOUBLE_CLICK_EXIT", "true")).lower() == "true" else "false"
    screen_orientation = str(env.get("SCREEN_ORIENTATION", "auto")).strip().lower()
    if screen_orientation not in {"portrait", "landscape", "auto"}:
        screen_orientation = "auto"
    download_mode = str(env.get("DOWNLOAD_MODE", "picker")).strip().lower()
    if download_mode not in {"silent", "picker"}:
        if download_mode in {"explorer", "file_manager", "resource_manager"}:
            download_mode = "picker"
        else:
            download_mode = "picker"
    web_fill_mode = str(env.get("WEB_FILL_MODE", "contain")).strip().lower()
    if web_fill_mode not in {"contain", "cover"}:
        web_fill_mode = "contain"

    def _insert_after_default_config(line: str) -> None:
        nonlocal text
        text = re.sub(
            r'(defaultConfig\s*\{)',
            lambda m: m.group(1) + "\n        " + line,
            text,
            count=1,
        )

    if is_kts:
        def _ensure_kts(field_name: str, value: str) -> None:
            nonlocal text
            pattern = re.compile(
                rf'buildConfigField\(\s*"[^\"]+"\s*,\s*"{field_name}"\s*,\s*"(?:\\.|[^"])*"\s*\)'
            )
            line = f'buildConfigField("{"boolean" if value in {"true", "false"} else "String"}", "{field_name}", "{value}")'
            if pattern.search(text):
                text = pattern.sub(line, text)
            else:
                _insert_after_default_config(line)

        _ensure_kts("HIDE_STATUS_BAR", status_bar_hidden)
        _ensure_kts("STATUS_BAR_BACKGROUND", f'\\"{status_bar_background}\\"')
        _ensure_kts("LIGHT_STATUS_BAR_ICONS", light_status_bar_icons)
        _ensure_kts("DOUBLE_CLICK_EXIT", double_click_exit)
        _ensure_kts("SCREEN_ORIENTATION", f'\\"{screen_orientation}\\"')
        _ensure_kts("DOWNLOAD_MODE", f'\\"{download_mode}\\"')
        _ensure_kts("WEB_FILL_MODE", f'\\"{web_fill_mode}\\"')

        if "buildFeatures" not in text:
            text = re.sub(
                r'(android\s*\{)',
                lambda m: m.group(1) + "\n    buildFeatures {\n        buildConfig = true\n    }\n",
                text,
                count=1,
            )
    else:
        def _ensure_groovy(field_name: str, value: str) -> None:
            nonlocal text
            pattern = re.compile(
                rf'buildConfigField\s+\"[^\"]+\"\s*,\s*\"{field_name}\"\s*,\s*\"(?:\\.|[^\"])*\"'
            )
            field_type = "boolean" if value in {"true", "false"} else "String"
            line = f'buildConfigField "{field_type}", "{field_name}", "{value}"'
            if pattern.search(text):
                text = pattern.sub(line, text)
            else:
                _insert_after_default_config(line)

        _ensure_groovy("HIDE_STATUS_BAR", status_bar_hidden)
        _ensure_groovy("STATUS_BAR_BACKGROUND", f'\\"{status_bar_background}\\"')
        _ensure_groovy("LIGHT_STATUS_BAR_ICONS", light_status_bar_icons)
        _ensure_groovy("DOUBLE_CLICK_EXIT", double_click_exit)
        _ensure_groovy("SCREEN_ORIENTATION", f'\\"{screen_orientation}\\"')
        _ensure_groovy("DOWNLOAD_MODE", f'\\"{download_mode}\\"')
        _ensure_groovy("WEB_FILL_MODE", f'\\"{web_fill_mode}\\"')

        if "buildFeatures" not in text:
            text = re.sub(
                r'(android\s*\{)',
                lambda m: m.group(1) + "\n    buildFeatures {\n        buildConfig true\n    }\n",
                text,
                count=1,
            )

    build_gradle.write_text(text, encoding="utf-8")
    _log(on_log, f"[Android] Updated BuildConfig in {build_gradle.name}")

def _patch_capacitor_main_activity(
    main_activity: Path,
    package_name: str,
    use_webview_top_padding: bool = True,
    use_webview_bottom_padding: bool = True,
    on_log=None,
) -> None:
    if not main_activity.exists():
        return
    text = main_activity.read_text(encoding="utf-8")
    source_before = text
    if "BridgeActivity" not in text:
        return
    top_padding_literal = "true" if use_webview_top_padding else "false"
    bottom_padding_literal = "true" if use_webview_bottom_padding else "false"
    is_kotlin = main_activity.suffix.lower() == ".kt"
    text = _strip_navigation_bar_hide_flags(text)
    if "DOUBLE_CLICK_EXIT" in text or "OnBackPressedCallback" in text:
        synced = _sync_existing_insets_padding_flags(
            text,
            is_kotlin=is_kotlin,
            use_webview_top_padding=use_webview_top_padding,
            use_webview_bottom_padding=use_webview_bottom_padding,
        )
        if synced != source_before:
            main_activity.write_text(synced, encoding="utf-8")
            _log(on_log, f"[Android] synced MainActivity insets flags: {main_activity}")
        return
    if is_kotlin:
        updated = f"""package {package_name}

import android.graphics.Color
import android.os.Bundle
import android.view.View
import android.view.WindowManager
import android.widget.Toast
import androidx.activity.OnBackPressedCallback
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowInsetsControllerCompat
import androidx.core.view.ViewCompat
import com.getcapacitor.BridgeActivity

class MainActivity : BridgeActivity() {{
    private var lastBackPressAt: Long = 0L

    override fun onCreate(savedInstanceState: Bundle?) {{
        super.onCreate(savedInstanceState)
        applySystemBars()
        applyWebViewInsets()
        onBackPressedDispatcher.addCallback(
            this,
            object : OnBackPressedCallback(true) {{
                override fun handleOnBackPressed() {{
                    val webView = bridge?.webView
                    if (webView != null && webView.canGoBack()) {{
                        webView.goBack()
                        return
                    }}
                    if (!BuildConfig.DOUBLE_CLICK_EXIT) {{
                        finish()
                        return
                    }}
                    val now = System.currentTimeMillis()
                    if (now - lastBackPressAt <= 2000) {{
                        finish()
                    }} else {{
                        lastBackPressAt = now
                        Toast.makeText(this@MainActivity, "再按一次退出应用", Toast.LENGTH_SHORT).show()
                    }}
                }}
            }}
        )
    }}

    private fun readStatusBarHeightPx(): Int {{
        val resId = resources.getIdentifier("status_bar_height", "dimen", "android")
        return if (resId > 0) resources.getDimensionPixelSize(resId) else 0
    }}

    private fun applyWebViewInsets() {{
        val webView = bridge?.webView ?: return
        webView.clipToPadding = true
        val useWebViewTopPadding = {top_padding_literal}
        val useWebViewBottomPadding = {bottom_padding_literal}
        val drawBehindStatusBar = BuildConfig.STATUS_BAR_BACKGROUND.trim().lowercase() == "transparent"
        val root = window.decorView
        ViewCompat.setOnApplyWindowInsetsListener(root) {{ _, insets ->
            val nav = insets.getInsets(WindowInsetsCompat.Type.navigationBars())
            val status = insets.getInsets(WindowInsetsCompat.Type.statusBars())
            val statusStable = insets.getInsetsIgnoringVisibility(WindowInsetsCompat.Type.statusBars())
            val cutout = insets.getInsets(WindowInsetsCompat.Type.displayCutout())
            val fallbackStatusBarHeight = if (BuildConfig.HIDE_STATUS_BAR) readStatusBarHeightPx() else 0
            val topSystemInset = maxOf(status.top, statusStable.top, cutout.top, fallbackStatusBarHeight)
            val shouldApplyTopInset = useWebViewTopPadding && (drawBehindStatusBar || BuildConfig.HIDE_STATUS_BAR)
            val topInset = if (shouldApplyTopInset) topSystemInset else 0
            val bottomInset = if (useWebViewBottomPadding) nav.bottom else 0
            webView.setPadding(nav.left, topInset, nav.right, bottomInset)
            webView.post {{
                val script = "(function(){{var t=" + topInset + ";var b=" + bottomInset +
                    ";var root=document.documentElement;" +
                    "if(root){{root.style.setProperty('--convertapk-safe-top', t+'px');root.style.setProperty('--convertapk-safe-bottom', b+'px');}}" +
                    "if(document.body){{document.body.style.setProperty('--convertapk-safe-top', t+'px');document.body.style.setProperty('--convertapk-safe-bottom', b+'px');}}" +
                    "}})();"
                webView.evaluateJavascript(script, null)
            }}
            insets
        }}
        ViewCompat.requestApplyInsets(root)
    }}

    override fun onWindowFocusChanged(hasFocus: Boolean) {{
        super.onWindowFocusChanged(hasFocus)
        if (hasFocus) {{
            applySystemBars()
        }}
    }}

    private fun applySystemBars() {{
        val statusBarBackground = BuildConfig.STATUS_BAR_BACKGROUND.trim().lowercase()
        val drawBehind = statusBarBackground == "transparent"
        WindowCompat.setDecorFitsSystemWindows(window, !drawBehind)
        @Suppress("DEPRECATION")
        window.statusBarColor = if (drawBehind) Color.TRANSPARENT else Color.WHITE
        val controller = WindowInsetsControllerCompat(window, window.decorView)
        controller.isAppearanceLightStatusBars = BuildConfig.LIGHT_STATUS_BAR_ICONS
        if (BuildConfig.HIDE_STATUS_BAR) {{
            window.addFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN)
            window.clearFlags(WindowManager.LayoutParams.FLAG_FORCE_NOT_FULLSCREEN)
            @Suppress("DEPRECATION")
            window.decorView.systemUiVisibility =
                View.SYSTEM_UI_FLAG_FULLSCREEN or
                View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN or
                View.SYSTEM_UI_FLAG_LAYOUT_STABLE
            controller.hide(WindowInsetsCompat.Type.statusBars())
            controller.show(WindowInsetsCompat.Type.navigationBars())
        }} else {{
            window.clearFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN)
            window.addFlags(WindowManager.LayoutParams.FLAG_FORCE_NOT_FULLSCREEN)
            @Suppress("DEPRECATION")
            window.decorView.systemUiVisibility =
                if (BuildConfig.LIGHT_STATUS_BAR_ICONS) {{
                    View.SYSTEM_UI_FLAG_VISIBLE or View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR
                }} else {{
                    View.SYSTEM_UI_FLAG_VISIBLE
                }}
            controller.show(WindowInsetsCompat.Type.statusBars())
        }}
    }}
}}
"""
    else:
        updated = f"""package {package_name};

import android.graphics.Color;
import android.os.Bundle;
import android.view.View;
import android.view.WindowManager;
import android.widget.Toast;
import androidx.activity.OnBackPressedCallback;
import androidx.core.view.WindowCompat;
import androidx.core.view.WindowInsetsCompat;
import androidx.core.view.WindowInsetsControllerCompat;
import androidx.core.view.ViewCompat;
import androidx.core.graphics.Insets;
import com.getcapacitor.BridgeActivity;
import android.webkit.WebView;

public class MainActivity extends BridgeActivity {{
    private long lastBackPressAt = 0L;

    @Override
    protected void onCreate(Bundle savedInstanceState) {{
        super.onCreate(savedInstanceState);
        applySystemBars();
        applyWebViewInsets();
        getOnBackPressedDispatcher().addCallback(
            this,
            new OnBackPressedCallback(true) {{
                @Override
                public void handleOnBackPressed() {{
                    WebView webView = getBridge() != null ? getBridge().getWebView() : null;
                    if (webView != null && webView.canGoBack()) {{
                        webView.goBack();
                        return;
                    }}
                    if (!BuildConfig.DOUBLE_CLICK_EXIT) {{
                        finish();
                        return;
                    }}
                    long now = System.currentTimeMillis();
                    if (now - lastBackPressAt <= 2000) {{
                        finish();
                    }} else {{
                        lastBackPressAt = now;
                        Toast.makeText(MainActivity.this, "再按一次退出应用", Toast.LENGTH_SHORT).show();
                    }}
                }}
            }}
        );
    }}

    private int readStatusBarHeightPx() {{
        int resId = getResources().getIdentifier("status_bar_height", "dimen", "android");
        return resId > 0 ? getResources().getDimensionPixelSize(resId) : 0;
    }}

    private void applyWebViewInsets() {{
        WebView webView = getBridge() != null ? getBridge().getWebView() : null;
        if (webView == null) {{
            return;
        }}
        webView.setClipToPadding(true);
        final boolean useWebViewTopPadding = {top_padding_literal};
        final boolean useWebViewBottomPadding = {bottom_padding_literal};
        final boolean drawBehindStatusBar = "transparent".equalsIgnoreCase(BuildConfig.STATUS_BAR_BACKGROUND.trim());
        View decor = getWindow().getDecorView();
        ViewCompat.setOnApplyWindowInsetsListener(decor, (v, insets) -> {{
            Insets nav = insets.getInsets(WindowInsetsCompat.Type.navigationBars());
            Insets status = insets.getInsets(WindowInsetsCompat.Type.statusBars());
            Insets statusStable = insets.getInsetsIgnoringVisibility(WindowInsetsCompat.Type.statusBars());
            Insets cutout = insets.getInsets(WindowInsetsCompat.Type.displayCutout());
            int fallbackStatusBarHeight = BuildConfig.HIDE_STATUS_BAR ? readStatusBarHeightPx() : 0;
            int topSystemInset = Math.max(Math.max(status.top, statusStable.top), Math.max(cutout.top, fallbackStatusBarHeight));
            boolean shouldApplyTopInset = useWebViewTopPadding && (drawBehindStatusBar || BuildConfig.HIDE_STATUS_BAR);
            int topInset = shouldApplyTopInset ? topSystemInset : 0;
            int bottomInset = useWebViewBottomPadding ? nav.bottom : 0;
            webView.setPadding(nav.left, topInset, nav.right, bottomInset);
            webView.post(() -> webView.evaluateJavascript(
                "(function(){{var t=" + topInset + ";var b=" + bottomInset + ";" +
                "var root=document.documentElement;" +
                "if(root){{root.style.setProperty('--convertapk-safe-top', t+'px');root.style.setProperty('--convertapk-safe-bottom', b+'px');}}" +
                "if(document.body){{document.body.style.setProperty('--convertapk-safe-top', t+'px');document.body.style.setProperty('--convertapk-safe-bottom', b+'px');}}" +
                "}})();",
                null
            ));
            return insets;
        }});
        ViewCompat.requestApplyInsets(decor);
    }}

    @Override
    public void onWindowFocusChanged(boolean hasFocus) {{
        super.onWindowFocusChanged(hasFocus);
        if (hasFocus) {{
            applySystemBars();
        }}
    }}

    private void applySystemBars() {{
        String statusBarBackground = BuildConfig.STATUS_BAR_BACKGROUND.trim().toLowerCase();
        boolean drawBehind = "transparent".equals(statusBarBackground);
        WindowCompat.setDecorFitsSystemWindows(getWindow(), !drawBehind);
        getWindow().setStatusBarColor(drawBehind ? Color.TRANSPARENT : Color.WHITE);
        WindowInsetsControllerCompat controller = new WindowInsetsControllerCompat(getWindow(), getWindow().getDecorView());
        controller.setAppearanceLightStatusBars(BuildConfig.LIGHT_STATUS_BAR_ICONS);
        if (BuildConfig.HIDE_STATUS_BAR) {{
            getWindow().addFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN);
            getWindow().clearFlags(WindowManager.LayoutParams.FLAG_FORCE_NOT_FULLSCREEN);
            getWindow().getDecorView().setSystemUiVisibility(
                View.SYSTEM_UI_FLAG_FULLSCREEN |
                View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN |
                View.SYSTEM_UI_FLAG_LAYOUT_STABLE
            );
            controller.hide(WindowInsetsCompat.Type.statusBars());
            controller.show(WindowInsetsCompat.Type.navigationBars());
        }} else {{
            getWindow().clearFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN);
            getWindow().addFlags(WindowManager.LayoutParams.FLAG_FORCE_NOT_FULLSCREEN);
            int visibility = View.SYSTEM_UI_FLAG_VISIBLE;
            if (BuildConfig.LIGHT_STATUS_BAR_ICONS) {{
                visibility |= View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR;
            }}
            getWindow().getDecorView().setSystemUiVisibility(visibility);
            controller.show(WindowInsetsCompat.Type.statusBars());
        }}
    }}
}}
"""
    main_activity.write_text(updated, encoding="utf-8")
    _log(on_log, f"[Android] patched MainActivity: {main_activity}")

def _reset_main_activity_if_convertapk_injected(
    main_activity: Path,
    package_name: str,
    on_log=None,
) -> None:
    if not main_activity.exists():
        return
    text = main_activity.read_text(encoding="utf-8")
    if "ConvertAPK:" not in text:
        return
    resolved_package = str(package_name or "").strip()
    if not resolved_package:
        package_match = re.search(r"(?m)^\s*package\s+([A-Za-z0-9_.]+)", text)
        if package_match:
            resolved_package = package_match.group(1)
    if not resolved_package:
        resolved_package = "com.example.app"
    if main_activity.suffix.lower() == ".kt":
        minimal = (
            f"package {resolved_package}\n\n"
            "import com.getcapacitor.BridgeActivity\n\n"
            "class MainActivity : BridgeActivity()\n"
        )
    else:
        minimal = (
            f"package {resolved_package};\n\n"
            "import com.getcapacitor.BridgeActivity;\n\n"
            "public class MainActivity extends BridgeActivity {}\n"
        )
    main_activity.write_text(minimal, encoding="utf-8")
    _log(on_log, f"[MainActivity] reset injected MainActivity to minimal BridgeActivity: {main_activity}")

def _ensure_import_line(source: str, import_line: str) -> str:
    if import_line in source:
        return source
    lines = source.splitlines()
    insert_at = None
    for idx, line in enumerate(lines):
        if line.startswith("import "):
            insert_at = idx + 1
    if insert_at is None:
        for idx, line in enumerate(lines):
            if line.startswith("package "):
                insert_at = idx + 1
                break
    if insert_at is None:
        insert_at = 0
    lines.insert(insert_at, import_line)
    result = "\n".join(lines)
    if source.endswith("\n"):
        result += "\n"
    return result

def _insert_after_main_activity_class_open(source: str, insert: str, is_kotlin: bool = False) -> str:
    match = re.search(r"class\s+MainActivity\b[^{]*\{", source)
    if match:
        idx = match.end()
        return source[:idx] + "\n" + insert + source[idx:]
    if is_kotlin:
        decl_match = re.search(r"class\s+MainActivity\b[^\n]*", source)
        if decl_match:
            raw_decl = decl_match.group(0)
            decl = raw_decl.rstrip()
            if "{" not in decl:
                replacement = f"{decl} {{\n{insert}}}\n"
                return source[: decl_match.start()] + replacement + source[decl_match.end() :]
    return source


def _inject_minimal_snippet_into_on_create(source: str, is_kotlin: bool, snippet: str) -> str:
    if not snippet or not snippet.strip():
        return source
    if snippet.strip() in source:
        return source
    if is_kotlin:
        with_super = re.compile(
            r"(override\s+fun\s+onCreate\s*\([^)]*\)\s*\{[\s\S]*?super\.onCreate\s*\(\s*savedInstanceState\s*\)\s*)",
            re.M,
        )
        if with_super.search(source):
            return with_super.sub(lambda m: m.group(1) + "\n" + snippet, source, count=1)
        method_start = re.compile(r"(override\s+fun\s+onCreate\s*\([^)]*\)\s*\{)", re.M)
        if method_start.search(source):
            return method_start.sub(lambda m: m.group(1) + "\n" + snippet, source, count=1)
        class_close = source.rfind("}")
        if class_close != -1:
            create_method = (
                "    override fun onCreate(savedInstanceState: Bundle?) {\n"
                "        super.onCreate(savedInstanceState)\n"
                f"{snippet}"
                "    }\n\n"
            )
            return source[:class_close] + "\n" + create_method + source[class_close:]
        return source
    with_super = re.compile(
        r"((?:@Override\s+)?protected\s+void\s+onCreate\s*\([^)]*\)\s*\{[\s\S]*?super\.onCreate\s*\(\s*savedInstanceState\s*\)\s*;\s*)",
        re.M,
    )
    if with_super.search(source):
        return with_super.sub(lambda m: m.group(1) + "\n" + snippet, source, count=1)
    method_start = re.compile(r"((?:@Override\s+)?protected\s+void\s+onCreate\s*\([^)]*\)\s*\{)", re.M)
    if method_start.search(source):
        return method_start.sub(lambda m: m.group(1) + "\n" + snippet, source, count=1)
    class_close = source.rfind("}")
    if class_close != -1:
        create_method = (
            "    @Override\n"
            "    protected void onCreate(Bundle savedInstanceState) {\n"
            "        super.onCreate(savedInstanceState);\n"
            f"{snippet}"
            "    }\n\n"
        )
        return source[:class_close] + "\n" + create_method + source[class_close:]
    return source

def _remove_minimal_double_click_exit(source: str) -> str:
    source = re.sub(
        r"(?ms)\n?\s*// ConvertAPK: double-click-exit state \(minimal\)\n\s*(?:private var|private long)\s+convertApkLastBackPressedAt[^\n]*\n?",
        "\n",
        source,
    )
    source = re.sub(
        r"(?ms)\n?\s*// ConvertAPK: double-click-exit start \(minimal\)\n.*?\n\s*// ConvertAPK: double-click-exit end \(minimal\)\n?",
        "\n",
        source,
    )
    return source

def _remove_minimal_status_bar_hidden(source: str) -> str:
    source = re.sub(
        r"(?ms)\n?\s*// ConvertAPK: status-bar-hidden start \(minimal\)\n.*?\n\s*// ConvertAPK: status-bar-hidden end \(minimal\)\n?",
        "\n",
        source,
    )
    return source

def _sync_minimal_status_bar_hidden(
    main_activity: Path,
    enable: bool,
    on_log=None,
) -> None:
    if not main_activity.exists():
        return
    text = main_activity.read_text(encoding="utf-8")
    if "BridgeActivity" not in text:
        return
    is_kotlin = main_activity.suffix.lower() == ".kt"
    original = text
    text = _remove_minimal_status_bar_hidden(text)
    if enable:
        if is_kotlin:
            text = _insert_after_main_activity_class_open(text, "", is_kotlin=True)
            text = _ensure_import_line(text, "import android.os.Build")
            text = _ensure_import_line(text, "import android.os.Bundle")
            text = _ensure_import_line(text, "import android.view.View")
            text = _ensure_import_line(text, "import android.view.WindowInsets")
            text = _ensure_import_line(text, "import android.view.WindowManager")
            method_block = (
                "    // ConvertAPK: status-bar-hidden start (minimal)\n"
                "    override fun onCreate(savedInstanceState: Bundle?) {\n"
                "        super.onCreate(savedInstanceState)\n"
                "        normalizeConvertApkWebViewInsets()\n"
                "        applyConvertApkStatusBarHidden()\n"
                "    }\n\n"
                "    override fun onWindowFocusChanged(hasFocus: Boolean) {\n"
                "        super.onWindowFocusChanged(hasFocus)\n"
                "        if (hasFocus) {\n"
                "            normalizeConvertApkWebViewInsets()\n"
                "            applyConvertApkStatusBarHidden()\n"
                "        }\n"
                "    }\n\n"
                "    private fun normalizeConvertApkWebViewInsets() {\n"
                "        val convertApkWebView = bridge?.webView ?: return\n"
                "        convertApkWebView.setPadding(0, 0, 0, 0)\n"
                "        convertApkWebView.clipToPadding = false\n"
                "        val parentView = convertApkWebView.parent as? View\n"
                "        if (parentView != null) {\n"
                "            parentView.setPadding(0, 0, 0, 0)\n"
                "            parentView.fitsSystemWindows = false\n"
                "        }\n"
                "    }\n\n"
                "    private fun applyConvertApkStatusBarHidden() {\n"
                "        @Suppress(\"DEPRECATION\")\n"
                "        window.addFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN)\n"
                "        @Suppress(\"DEPRECATION\")\n"
                "        window.clearFlags(WindowManager.LayoutParams.FLAG_FORCE_NOT_FULLSCREEN)\n"
                "        @Suppress(\"DEPRECATION\")\n"
                "        window.statusBarColor = android.graphics.Color.TRANSPARENT\n"
                "        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {\n"
                "            window.setDecorFitsSystemWindows(false)\n"
                "            val controller = window.insetsController\n"
                "            if (controller != null) {\n"
                "                controller.hide(WindowInsets.Type.statusBars())\n"
                "                controller.show(WindowInsets.Type.navigationBars())\n"
                "            }\n"
                "        } else {\n"
                "            @Suppress(\"DEPRECATION\")\n"
                "            window.addFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN)\n"
                "            @Suppress(\"DEPRECATION\")\n"
                "            window.decorView.systemUiVisibility =\n"
                "                View.SYSTEM_UI_FLAG_FULLSCREEN or\n"
                "                View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN or\n"
                "                View.SYSTEM_UI_FLAG_LAYOUT_STABLE\n"
                "        }\n"
                "    }\n"
                "    // ConvertAPK: status-bar-hidden end (minimal)\n"
            )
        else:
            text = _ensure_import_line(text, "import android.os.Build;")
            text = _ensure_import_line(text, "import android.os.Bundle;")
            text = _ensure_import_line(text, "import android.view.View;")
            text = _ensure_import_line(text, "import android.view.WindowInsets;")
            text = _ensure_import_line(text, "import android.view.WindowManager;")
            method_block = (
                "    // ConvertAPK: status-bar-hidden start (minimal)\n"
                "    @Override\n"
                "    protected void onCreate(Bundle savedInstanceState) {\n"
                "        super.onCreate(savedInstanceState);\n"
                "        normalizeConvertApkWebViewInsets();\n"
                "        applyConvertApkStatusBarHidden();\n"
                "    }\n\n"
                "    @Override\n"
                "    public void onWindowFocusChanged(boolean hasFocus) {\n"
                "        super.onWindowFocusChanged(hasFocus);\n"
                "        if (hasFocus) {\n"
                "            normalizeConvertApkWebViewInsets();\n"
                "            applyConvertApkStatusBarHidden();\n"
                "        }\n"
                "    }\n\n"
                "    private void normalizeConvertApkWebViewInsets() {\n"
                "        android.webkit.WebView convertApkWebView = getBridge() != null ? getBridge().getWebView() : null;\n"
                "        if (convertApkWebView == null) {\n"
                "            return;\n"
                "        }\n"
                "        convertApkWebView.setPadding(0, 0, 0, 0);\n"
                "        convertApkWebView.setClipToPadding(false);\n"
                "        android.view.ViewParent parent = convertApkWebView.getParent();\n"
                "        if (parent instanceof View) {\n"
                "            View parentView = (View) parent;\n"
                "            parentView.setPadding(0, 0, 0, 0);\n"
                "            parentView.setFitsSystemWindows(false);\n"
                "        }\n"
                "    }\n\n"
                "    private void applyConvertApkStatusBarHidden() {\n"
                "        getWindow().addFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN);\n"
                "        getWindow().clearFlags(WindowManager.LayoutParams.FLAG_FORCE_NOT_FULLSCREEN);\n"
                "        getWindow().setStatusBarColor(android.graphics.Color.TRANSPARENT);\n"
                "        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {\n"
                "            getWindow().setDecorFitsSystemWindows(false);\n"
                "            android.view.WindowInsetsController controller = getWindow().getInsetsController();\n"
                "            if (controller != null) {\n"
                "                controller.hide(WindowInsets.Type.statusBars());\n"
                "                controller.show(WindowInsets.Type.navigationBars());\n"
                "            }\n"
                "        } else {\n"
                "            getWindow().addFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN);\n"
                "            getWindow().getDecorView().setSystemUiVisibility(\n"
                "                View.SYSTEM_UI_FLAG_FULLSCREEN |\n"
                "                View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN |\n"
                "                View.SYSTEM_UI_FLAG_LAYOUT_STABLE\n"
                "            );\n"
                "        }\n"
                "    }\n"
                "    // ConvertAPK: status-bar-hidden end (minimal)\n"
            )
        class_close = text.rfind("}")
        if class_close != -1:
            text = text[:class_close] + "\n" + method_block + "\n" + text[class_close:]
    if text != original:
        main_activity.write_text(text, encoding="utf-8")
        _log(
            on_log,
            f"[MainActivity] {'enabled' if enable else 'disabled'} minimal status-bar-hidden: {main_activity}",
        )

def _sync_minimal_double_click_exit(
    main_activity: Path,
    enable: bool,
    on_log=None,
) -> None:
    if not main_activity.exists():
        return
    text = main_activity.read_text(encoding="utf-8")
    if "BridgeActivity" not in text:
        return
    is_kotlin = main_activity.suffix.lower() == ".kt"
    original = text
    text = _remove_minimal_double_click_exit(text)
    if enable:
        if is_kotlin:
            text = _ensure_import_line(text, "import android.widget.Toast")
            text = _ensure_import_line(text, "import android.os.Bundle")
            text = _ensure_import_line(text, "import androidx.activity.OnBackPressedCallback")
            field_block = (
                "    // ConvertAPK: double-click-exit state (minimal)\n"
                "    private var convertApkLastBackPressedAt: Long = 0L\n"
            )
            on_create_snippet = (
                "        // ConvertAPK: double-click-exit start (minimal)\n"
                "        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {\n"
                "            override fun handleOnBackPressed() {\n"
                "                val webView = bridge?.webView\n"
                "                if (webView != null && webView.canGoBack()) {\n"
                "                    webView.goBack()\n"
                "                    return\n"
                "                }\n"
                "                val now = System.currentTimeMillis()\n"
                "                if (now - convertApkLastBackPressedAt < 2000) {\n"
                "                    finish()\n"
                "                } else {\n"
                "                    convertApkLastBackPressedAt = now\n"
                "                    Toast.makeText(this@MainActivity, \"Press back again to exit\", Toast.LENGTH_SHORT).show()\n"
                "                }\n"
                "            }\n"
                "        })\n"
                "    // ConvertAPK: double-click-exit end (minimal)\n"
            )
        else:
            text = _ensure_import_line(text, "import android.widget.Toast;")
            text = _ensure_import_line(text, "import android.os.Bundle;")
            text = _ensure_import_line(text, "import androidx.activity.OnBackPressedCallback;")
            field_block = (
                "    // ConvertAPK: double-click-exit state (minimal)\n"
                "    private long convertApkLastBackPressedAt = 0L;\n"
            )
            on_create_snippet = (
                "        // ConvertAPK: double-click-exit start (minimal)\n"
                "        getOnBackPressedDispatcher().addCallback(this, new OnBackPressedCallback(true) {\n"
                "            @Override\n"
                "            public void handleOnBackPressed() {\n"
                "                android.webkit.WebView webView = getBridge() != null ? getBridge().getWebView() : null;\n"
                "                if (webView != null && webView.canGoBack()) {\n"
                "                    webView.goBack();\n"
                "                    return;\n"
                "                }\n"
                "                long now = System.currentTimeMillis();\n"
                "                if (now - convertApkLastBackPressedAt < 2000) {\n"
                "                    finish();\n"
                "                } else {\n"
                "                    convertApkLastBackPressedAt = now;\n"
                "                    Toast.makeText(MainActivity.this, \"Press back again to exit\", Toast.LENGTH_SHORT).show();\n"
                "                }\n"
                "            }\n"
                "        });\n"
                "    // ConvertAPK: double-click-exit end (minimal)\n"
            )
        text = _insert_after_main_activity_class_open(text, field_block, is_kotlin=is_kotlin)
        text = _inject_minimal_snippet_into_on_create(text, is_kotlin=is_kotlin, snippet=on_create_snippet)
    if text != original:
        main_activity.write_text(text, encoding="utf-8")
        _log(
            on_log,
            f"[MainActivity] {'enabled' if enable else 'disabled'} minimal double-click-exit: {main_activity}",
        )

def _remove_minimal_download_listener(source: str) -> str:
    source = re.sub(
        r"(?ms)\n?\s*// ConvertAPK: download start \(minimal\)\n.*?\n\s*// ConvertAPK: download end \(minimal\)\n?",
        "\n",
        source,
    )
    return source

def _sync_minimal_download_listener(
    main_activity: Path,
    enable: bool,
    download_mode: str = "picker",
    on_log=None,
) -> None:
    if not main_activity.exists():
        return
    text = main_activity.read_text(encoding="utf-8")
    if "BridgeActivity" not in text:
        return
    is_kotlin = main_activity.suffix.lower() == ".kt"
    normalized_download_mode = "silent" if str(download_mode).strip().lower() == "silent" else "picker"
    original = text
    text = _remove_minimal_download_listener(text)
    if enable:
        if is_kotlin:
            text = _insert_after_main_activity_class_open(text, "", is_kotlin=True)
            text = _ensure_import_line(text, "import android.app.DownloadManager")
            text = _ensure_import_line(text, "import android.content.Intent")
            text = _ensure_import_line(text, "import android.net.Uri")
            text = _ensure_import_line(text, "import android.os.Environment")
            text = _ensure_import_line(text, "import android.webkit.CookieManager")
            text = _ensure_import_line(text, "import android.webkit.URLUtil")
            text = _ensure_import_line(text, "import android.widget.Toast")
            on_create_snippet = (
                "        // ConvertAPK: download start (minimal)\n"
                "        val webView = bridge?.webView\n"
                "        if (webView != null) {\n"
                "            webView.setDownloadListener { url, userAgent, contentDisposition, mimeType, _ ->\n"
                "                try {\n"
                f"                    val downloadMode = \"{normalized_download_mode}\"\n"
                "                    if (downloadMode != \"silent\") {\n"
                "                        try {\n"
                "                            val intent = Intent(Intent.ACTION_VIEW, Uri.parse(url))\n"
                "                            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)\n"
                "                            startActivity(intent)\n"
                "                            return@setDownloadListener\n"
                "                        } catch (_: Exception) {\n"
                "                        }\n"
                "                    }\n"
                "                    val request = DownloadManager.Request(Uri.parse(url))\n"
                "                    if (!mimeType.isNullOrBlank()) {\n"
                "                        request.setMimeType(mimeType)\n"
                "                    }\n"
                "                    if (!userAgent.isNullOrBlank()) {\n"
                "                        request.addRequestHeader(\"User-Agent\", userAgent)\n"
                "                    }\n"
                "                    val cookie = CookieManager.getInstance().getCookie(url)\n"
                "                    if (!cookie.isNullOrBlank()) {\n"
                "                        request.addRequestHeader(\"cookie\", cookie)\n"
                "                    }\n"
                "                    val fileName = URLUtil.guessFileName(url, contentDisposition, mimeType)\n"
                "                    request.setTitle(fileName)\n"
                "                    request.setDescription(url)\n"
                "                    request.setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED)\n"
                "                    request.setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS, fileName)\n"
                "                    val dm = getSystemService(DOWNLOAD_SERVICE) as DownloadManager\n"
                "                    dm.enqueue(request)\n"
                "                } catch (_: Exception) {\n"
                "                    Toast.makeText(this@MainActivity, \"Download failed\", Toast.LENGTH_SHORT).show()\n"
                "                }\n"
                "            }\n"
                "        }\n"
                "    // ConvertAPK: download end (minimal)\n"
            )
        else:
            text = _ensure_import_line(text, "import android.app.DownloadManager;")
            text = _ensure_import_line(text, "import android.content.Intent;")
            text = _ensure_import_line(text, "import android.net.Uri;")
            text = _ensure_import_line(text, "import android.os.Environment;")
            text = _ensure_import_line(text, "import android.webkit.CookieManager;")
            text = _ensure_import_line(text, "import android.webkit.URLUtil;")
            text = _ensure_import_line(text, "import android.widget.Toast;")
            on_create_snippet = (
                "        // ConvertAPK: download start (minimal)\n"
                "        android.webkit.WebView webView = getBridge() != null ? getBridge().getWebView() : null;\n"
                "        if (webView != null) {\n"
                "            webView.setDownloadListener((url, userAgent, contentDisposition, mimeType, _contentLength) -> {\n"
                "                try {\n"
                f"                    String downloadMode = \"{normalized_download_mode}\";\n"
                "                    if (!\"silent\".equals(downloadMode)) {\n"
                "                        try {\n"
                "                            Intent intent = new Intent(Intent.ACTION_VIEW, Uri.parse(url));\n"
                "                            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);\n"
                "                            startActivity(intent);\n"
                "                            return;\n"
                "                        } catch (Exception ignored) {\n"
                "                        }\n"
                "                    }\n"
                "                    DownloadManager.Request request = new DownloadManager.Request(Uri.parse(url));\n"
                "                    if (mimeType != null && !mimeType.isEmpty()) {\n"
                "                        request.setMimeType(mimeType);\n"
                "                    }\n"
                "                    if (userAgent != null && !userAgent.isEmpty()) {\n"
                "                        request.addRequestHeader(\"User-Agent\", userAgent);\n"
                "                    }\n"
                "                    String cookie = CookieManager.getInstance().getCookie(url);\n"
                "                    if (cookie != null && !cookie.isEmpty()) {\n"
                "                        request.addRequestHeader(\"cookie\", cookie);\n"
                "                    }\n"
                "                    String fileName = URLUtil.guessFileName(url, contentDisposition, mimeType);\n"
                "                    request.setTitle(fileName);\n"
                "                    request.setDescription(url);\n"
                "                    request.setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);\n"
                "                    request.setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS, fileName);\n"
                "                    DownloadManager dm = (DownloadManager) getSystemService(DOWNLOAD_SERVICE);\n"
                "                    if (dm != null) {\n"
                "                        dm.enqueue(request);\n"
                "                    }\n"
                "                } catch (Exception ignored) {\n"
                "                    Toast.makeText(MainActivity.this, \"Download failed\", Toast.LENGTH_SHORT).show();\n"
                "                }\n"
                "            });\n"
                "        }\n"
                "    // ConvertAPK: download end (minimal)\n"
            )
        text = _inject_minimal_snippet_into_on_create(text, is_kotlin=is_kotlin, snippet=on_create_snippet)
    if text != original:
        main_activity.write_text(text, encoding="utf-8")
        _log(
            on_log,
            f"[MainActivity] {'enabled' if enable else 'disabled'} minimal download-listener: {main_activity}",
        )

def _replace_template_launcher_icon(project_root: Path, logo_path: Path, on_log=None) -> None:
    if not logo_path.exists():
        return
    res_dir = project_root / "app" / "src" / "main" / "res"
    drawable_dir = res_dir / "drawable"
    if not drawable_dir.exists():
        return
    target_png = drawable_dir / "ic_launcher_foreground.png"
    target_xml = drawable_dir / "ic_launcher_foreground.xml"
    try:
        if target_xml.exists():
            target_xml.unlink()
        shutil.copy2(logo_path, target_png)
        _log(on_log, f"[Android] launcher icon updated: {target_png}")
    except Exception as exc:
        _log(on_log, f"[Android] launcher icon update failed: {exc}")

def run_local_build(
    env: Dict[str, str],
    task_output_dir: Path,
    on_progress: Optional[Callable[[int, str], None]] = None,
    on_log: Optional[Callable[[str], None]] = None
) -> Dict[str, str]:
    task_input_dir = Path(env["TASK_INPUT_DIR"])
    task_keystore_dir = Path(env["TASK_KEYSTORE_DIR"])
    task_dir = task_input_dir.parent
    project_dir = task_dir / "project"
    output_format = (env.get("OUTPUT_FORMAT") or "apk").strip().lower()
    if output_format not in {"apk", "aab"}:
        output_format = "apk"
    task_output_dir.mkdir(parents=True, exist_ok=True)
    task_keystore_dir.mkdir(parents=True, exist_ok=True)

    def progress(value: int, message: str) -> None:
        if on_progress:
            on_progress(value, message)

    process_env = os.environ.copy()
    process_env.update(env)
    process_env.update(env_setup.get_npm_config())
    gradle_opts = process_env.get("GRADLE_OPTS", "")
    gradle_opts += " -Dorg.gradle.wrapper.timeout=600000 -Dorg.gradle.daemon=true"
    gradle_opts += " -Dorg.gradle.internal.http.connectionTimeout=600000"
    gradle_opts += " -Dorg.gradle.internal.http.socketTimeout=600000"
    gradle_opts += " -Dorg.gradle.internal.repository.max.retries=5"
    gradle_opts += " -Dorg.gradle.internal.repository.initial.backoff=2000"
    process_env["GRADLE_OPTS"] = gradle_opts
    java_home = process_env.get("JAVA_HOME", "").strip()
    if not java_home:
        status = env_setup.get_status()
        java_home = str(status.get("paths", {}).get("jdk", "")).strip()
        if java_home:
            process_env["JAVA_HOME"] = java_home
    if java_home:
        java_bin = str(Path(java_home) / "bin")
        process_env["PATH"] = f"{java_bin}{os.pathsep}{process_env.get('PATH', '')}"
    node_home = env.get("NODE_HOME", "").strip()
    if node_home:
        process_env["PATH"] = f"{node_home}{os.pathsep}{process_env.get('PATH', '')}"
    npm_cmd = _resolve_node_tool(process_env, "npm")
    npx_cmd = _resolve_node_tool(process_env, "npx")

    progress(10, "Step 0: 准备工作...")
    _log(on_log, "Step 0: 准备工作...")

    task_mode = (env.get("TASK_MODE") or "convert").strip().lower()
    is_desktop_task = task_mode == "desktop"
    is_web_task = task_mode == "web"
    is_html_task = task_mode == "html"

    if is_desktop_task:
        desktop_installer_mode = _normalize_desktop_installer_mode(env.get("DESKTOP_INSTALLER_MODE"))
        desktop_port = _normalize_desktop_port(env.get("DESKTOP_PORT"))
        progress(25, "Step 1: 解压 ZIP 项目...")
        _log(on_log, "Step 1: 解压 ZIP 项目...")
        _log(on_log, f"[Desktop] 安装器模式: {desktop_installer_mode}")

        zip_files = list(task_input_dir.glob("*.zip"))
        if not zip_files:
            raise RuntimeError(f"目录中未找到 ZIP 文件: {task_input_dir}")
        zip_file = zip_files[0]

        source_dir = task_dir / "desktop-source"
        if source_dir.exists():
            shutil.rmtree(source_dir, ignore_errors=True)
        source_dir.mkdir(parents=True, exist_ok=True)
        _extract_zip_safely(zip_file, source_dir)

        progress(35, "Step 2: 准备前端产物...")
        _log(on_log, "Step 2: 准备前端产物...")
        package_json_candidates = [
            candidate
            for candidate in source_dir.rglob("package.json")
            if candidate.is_file()
            and not {"node_modules", ".git", "__macosx", "android"} & {part.lower() for part in candidate.parts}
        ]
        package_json_candidates.sort(
            key=lambda item: (
                len(item.relative_to(source_dir).parts),
                len(str(item.relative_to(source_dir)).replace("\\", "/")),
            )
        )

        if package_json_candidates:
            package_json = package_json_candidates[0]
            project_root = package_json.parent
            package_info = _read_package_json(package_json)
            package_info["_root"] = project_root
            if not _should_skip_npm_install(project_root, on_log=on_log):
                _run_cmd([npm_cmd, "install", "--legacy-peer-deps"], cwd=project_root, env=process_env, on_log=on_log)
                _mark_npm_install(project_root)
            if "build" in (package_info.get("scripts") or {}):
                _run_cmd([npm_cmd, "run", "build"], cwd=project_root, env=process_env, on_log=on_log)
            web_dir = _find_web_build_dir(project_root)
        else:
            index_file = _pick_index_html(source_dir)
            web_dir = index_file.parent

        progress(55, "Step 3: 生成 Electron 桌面壳...")
        _log(on_log, "Step 3: 生成 Electron 桌面壳...")
        wrapper_root = task_dir / "desktop-app"
        logo_path = task_input_dir / "logo.png"
        effective_desktop_target = _write_desktop_wrapper_project(
            wrapper_root=wrapper_root,
            app_name=str(env.get("APP_NAME") or "DesktopApp"),
            package_name=str(env.get("PACKAGE_NAME") or "com.example.desktop"),
            version_name=str(env.get("VERSION_NAME") or "1.0.0"),
            desktop_installer_mode=desktop_installer_mode,
            desktop_port=desktop_port,
            source_app_dir=web_dir,
            logo_path=logo_path if logo_path.exists() else None,
            on_log=on_log,
        )
        _log(on_log, f"[Desktop] 实际打包目标: {effective_desktop_target}")

        progress(70, "Step 4: 安装 Electron 依赖...")
        _log(on_log, "Step 4: 安装 Electron 依赖...")
        if not _should_skip_npm_install(wrapper_root, on_log=on_log):
            _run_cmd([npm_cmd, "install", "--legacy-peer-deps"], cwd=wrapper_root, env=process_env, on_log=on_log)
            _mark_npm_install(wrapper_root)

        progress(85, "Step 5: 打包桌面应用...")
        _log(on_log, "Step 5: 打包桌面应用...")
        process_env["CSC_IDENTITY_AUTO_DISCOVERY"] = "false"
        _run_cmd(
            [npx_cmd, "electron-builder", "--win", effective_desktop_target, "--publish", "never"],
            cwd=wrapper_root,
            env=process_env,
            on_log=on_log,
        )

        dist_dir = wrapper_root / "dist"
        output_candidates = sorted(
            [item for item in dist_dir.glob("*.exe") if item.is_file()],
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )
        if not output_candidates:
            raise RuntimeError("Electron 打包完成，但未找到 .exe 产物")

        output_file = output_candidates[0]
        target_file = task_output_dir / output_file.name
        if target_file.exists():
            target_file.unlink()
        shutil.copy2(output_file, target_file)
        progress(100, "Electron 桌面应用构建成功")
        _log(on_log, f"[Desktop] 产物已生成: {target_file}")
        return {
            "output_file": str(target_file),
            "output_format": "exe",
        }

    if is_web_task:
        progress(25, "Step 1: 准备 Web 模板...")
        _log(on_log, "Step 1: 准备 Web 模板...")

        template_dir = _resolve_templates_root() / "Tubbim"
        if not template_dir.exists():
            raise RuntimeError(f"未找到 Web 模板目录: {template_dir}")

        if project_dir.exists():
            shutil.rmtree(project_dir)
        shutil.copytree(template_dir, project_dir)
        project_root = project_dir

        web_url = str(env.get("WEB_URL") or "").strip()
        if not web_url:
            raise RuntimeError("WEB_URL 不能为空")

        strings_file = project_root / "app" / "src" / "main" / "res" / "values" / "strings.xml"
        if strings_file.exists():
            strings_text = strings_file.read_text(encoding="utf-8")
            strings_text = re.sub(
                r'(<string\s+name="app_name">)(.*?)(</string>)',
                rf"\1{env.get('APP_NAME', 'MyApp')}\3",
                strings_text,
            )
            strings_file.write_text(strings_text, encoding="utf-8")

        logo = task_input_dir / "logo.png"
        _replace_template_launcher_icon(project_root, logo, on_log=on_log)

        gradle_file = project_root / "app" / "build.gradle.kts"
        if gradle_file.exists():
            gradle_text = gradle_file.read_text(encoding="utf-8")
            package_name = env.get("PACKAGE_NAME", "com.example.app")
            gradle_text = re.sub(
                r'(?m)^\s*applicationId\s*=\s*"[^\"]+"',
                f'        applicationId = "{package_name}"',
                gradle_text,
            )
            gradle_text = re.sub(
                r'(?m)^\s*versionCode\s*=\s*\d+',
                f'        versionCode = {env.get("VERSION_CODE", "1")}',
                gradle_text,
            )
            gradle_text = re.sub(
                r'(?m)^\s*versionName\s*=\s*"[^\"]+"',
                f'        versionName = "{env.get("VERSION_NAME", "1.0.0")}"',
                gradle_text,
            )
            status_bar_hidden = "true" if str(env.get("STATUS_BAR_HIDDEN", "false")).lower() == "true" else "false"
            status_bar_color = str(env.get("STATUS_BAR_COLOR", "#FFFFFF")).strip().lower()
            task_mode = str(env.get("TASK_MODE", "convert")).strip().lower()
            if (
                task_mode == "convert"
                and status_bar_hidden != "true"
                and status_bar_color in {"transparent", "@android:color/transparent"}
            ):
                status_bar_color = "#ffffff"
            status_bar_background = "white" if status_bar_color in {"#ffffff", "white", "#ffffffff"} else "transparent"
            status_bar_style = str(env.get("STATUS_BAR_STYLE", "light")).strip().lower()
            light_status_bar_icons = "true" if status_bar_style == "dark" else "false"
            double_click_exit = "true" if str(env.get("DOUBLE_CLICK_EXIT", "true")).lower() == "true" else "false"
            webview_ua = str(env.get("WEBVIEW_UA", "android")).strip().lower()
            if webview_ua in {"pc", "desktop", "windows"}:
                webview_ua = "pc"
            else:
                webview_ua = "android"
            gradle_text = re.sub(
                r'buildConfigField\(\s*"String"\s*,\s*"WEBVIEW_URL"\s*,\s*"(?:\\.|[^"])*"\s*\)',
                f'buildConfigField("String", "WEBVIEW_URL", "\\"{web_url}\\"")',
                gradle_text,
            )
            gradle_text = re.sub(
                r'buildConfigField\(\s*"String"\s*,\s*"WEBVIEW_UA"\s*,\s*"(?:\\.|[^"])*"\s*\)',
                f'buildConfigField("String", "WEBVIEW_UA", "\\"{webview_ua}\\"")',
                gradle_text,
            )
            gradle_text = re.sub(
                r'buildConfigField\(\s*"boolean"\s*,\s*"HIDE_STATUS_BAR"\s*,\s*"(?:true|false)"\s*\)',
                f'buildConfigField("boolean", "HIDE_STATUS_BAR", "{status_bar_hidden}")',
                gradle_text,
            )
            gradle_text = re.sub(
                r'buildConfigField\(\s*"String"\s*,\s*"STATUS_BAR_BACKGROUND"\s*,\s*"(?:\\.|[^"])*"\s*\)',
                f'buildConfigField("String", "STATUS_BAR_BACKGROUND", "\\"{status_bar_background}\\"")',
                gradle_text,
            )
            gradle_text = re.sub(
                r'buildConfigField\(\s*"boolean"\s*,\s*"LIGHT_STATUS_BAR_ICONS"\s*,\s*"(?:true|false)"\s*\)',
                f'buildConfigField("boolean", "LIGHT_STATUS_BAR_ICONS", "{light_status_bar_icons}")',
                gradle_text,
            )
            gradle_text = re.sub(
                r'buildConfigField\(\s*"boolean"\s*,\s*"DOUBLE_CLICK_EXIT"\s*,\s*"(?:true|false)"\s*\)',
                f'buildConfigField("boolean", "DOUBLE_CLICK_EXIT", "{double_click_exit}")',
                gradle_text,
            )
            gradle_file.write_text(gradle_text, encoding="utf-8")
    elif is_html_task:
        progress(25, "Step 1: 准备 HTML 模板...")
        _log(on_log, "Step 1: 准备 HTML 模板...")

        template_dir = _resolve_templates_root() / "HTML2APK"
        if not template_dir.exists():
            raise RuntimeError(f"未找到 HTML 模板目录: {template_dir}")

        if project_dir.exists():
            shutil.rmtree(project_dir)
        shutil.copytree(template_dir, project_dir)
        project_root = project_dir

        html_source = task_input_dir / "index.html"
        if not html_source.exists():
            raise RuntimeError("HTML 输入缺少文件: index.html")
        html_root = project_root / "html2apkdemo"
        if html_root.exists():
            shutil.rmtree(html_root)
        html_root.mkdir(parents=True, exist_ok=True)
        shutil.copy2(html_source, html_root / "index.html")

        libs_zip = task_input_dir / "libs.zip"
        if libs_zip.exists():
            libs_root = html_root / "libs"
            libs_root.mkdir(parents=True, exist_ok=True)
            temp_libs = task_dir / "_tmp_html_libs"
            if temp_libs.exists():
                shutil.rmtree(temp_libs)
            temp_libs.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(libs_zip, "r") as zf:
                zf.extractall(temp_libs)
            top_dirs = [d for d in temp_libs.iterdir() if d.is_dir()]
            top_files = [f for f in temp_libs.iterdir() if f.is_file()]
            if len(top_dirs) == 1 and len(top_files) == 0:
                for item in top_dirs[0].iterdir():
                    target = libs_root / item.name
                    if item.is_dir():
                        shutil.copytree(item, target, dirs_exist_ok=True)
                    else:
                        shutil.copy2(item, target)
            else:
                for item in temp_libs.iterdir():
                    target = libs_root / item.name
                    if item.is_dir():
                        shutil.copytree(item, target, dirs_exist_ok=True)
                    else:
                        shutil.copy2(item, target)
            shutil.rmtree(temp_libs, ignore_errors=True)

        _offlineize_html_assets(html_root / "index.html", process_env, on_log=on_log)

        strings_file = project_root / "app" / "src" / "main" / "res" / "values" / "strings.xml"
        if strings_file.exists():
            strings_text = strings_file.read_text(encoding="utf-8")
            strings_text = re.sub(
                r'(<string\s+name="app_name">)(.*?)(</string>)',
                rf"\1{env.get('APP_NAME', 'MyApp')}\3",
                strings_text,
            )
            strings_file.write_text(strings_text, encoding="utf-8")

        logo = task_input_dir / "logo.png"
        _replace_template_launcher_icon(project_root, logo, on_log=on_log)

        gradle_file = project_root / "app" / "build.gradle.kts"
        if gradle_file.exists():
            gradle_text = gradle_file.read_text(encoding="utf-8")
            package_name = env.get("PACKAGE_NAME", "com.example.app")
            gradle_text = re.sub(
                r'(?m)^\s*applicationId\s*=\s*"[^\"]+"',
                f'        applicationId = "{package_name}"',
                gradle_text,
            )
            gradle_text = re.sub(
                r'(?m)^\s*versionCode\s*=\s*\d+',
                f'        versionCode = {env.get("VERSION_CODE", "1")}',
                gradle_text,
            )
            gradle_text = re.sub(
                r'(?m)^\s*versionName\s*=\s*"[^\"]+"',
                f'        versionName = "{env.get("VERSION_NAME", "1.0.0")}"',
                gradle_text,
            )
            gradle_file.write_text(gradle_text, encoding="utf-8")
    else:
        zip_files = list(task_input_dir.glob("*.zip"))
        if not zip_files:
            raise RuntimeError(f"在目录中未找到 ZIP 文件: {task_input_dir}")
        zip_file = zip_files[0]

        if project_dir.exists():
            shutil.rmtree(project_dir)
        project_dir.mkdir(parents=True, exist_ok=True)
        if zip_file.suffix.lower() != ".zip":
            raise RuntimeError("上传文件不是 ZIP 格式")
        _extract_zip_safely(zip_file, project_dir)
        _normalize_project_text_encodings(project_dir, on_log=on_log)

        package_json_candidates = [
            candidate
            for candidate in project_dir.rglob("package.json")
            if candidate.is_file()
            and not {"node_modules", ".git", "__macosx", "android"} & {part.lower() for part in candidate.parts}
        ]
        package_json_candidates.sort(
            key=lambda item: (
                len(item.relative_to(project_dir).parts),
                len(str(item.relative_to(project_dir)).replace("\\", "/")),
            )
        )
        if not package_json_candidates:
            raise RuntimeError("ZIP 中未找到 package.json")
        package_json = package_json_candidates[0]
        project_root = package_json.parent

        pkg = _read_package_json(package_json)
        pkg["_root"] = project_root
        if _is_next_project(pkg):
            _ensure_next_config_output_export(project_root, on_log=on_log)

        # 兼容性兜底：如果上传包自带 android 工程，先清理后再由 Capacitor 重新生成，
        # 避免历史工程中的 gradle-wrapper/gradlew 损坏导致构建失败。
        stale_android_dir = project_root / "android"
        if stale_android_dir.exists():
            _log(on_log, "[Android] 检测到上传包包含 android 目录，构建前先清理以避免干扰")
            shutil.rmtree(stale_android_dir, ignore_errors=True)

        progress(25, "Step 1: 构建 Web 前端...")
        _log(on_log, "Step 1: 构建 Web 前端...")
        if not _should_skip_npm_install(project_root, on_log=on_log):
            _run_cmd([npm_cmd, "install", "--legacy-peer-deps"], cwd=project_root, env=process_env, on_log=on_log)
            _mark_npm_install(project_root)
        _run_cmd([npm_cmd, "run", "build"], cwd=project_root, env=process_env, on_log=on_log)

        try:
            web_dir = _find_web_build_dir(project_root)
        except RuntimeError as build_dir_error:
            if not _is_next_project(pkg):
                raise build_dir_error
            _log(on_log, "[Next.js] 构建后未检测到静态产物，尝试执行静态导出")
            try:
                _try_export_next_static_site(
                    project_root=project_root,
                    pkg=pkg,
                    npm_cmd=npm_cmd,
                    npx_cmd=npx_cmd,
                    env=process_env,
                    on_log=on_log,
                )
                web_dir = _find_web_build_dir(project_root)
            except Exception as export_error:
                _log(on_log, f"[Next.js] 静态导出失败：{str(export_error)}")
                _raise_next_static_export_error()

        progress(35, "Step 2: 准备 Capacitor...")
        _log(on_log, "Step 2: 准备 Capacitor...")
        _offlineize_html_assets(web_dir / "index.html", process_env, on_log=on_log)
        _dedupe_web_build_assets(web_dir, on_log=on_log)
        _ensure_dep(pkg, process_env, "@capacitor/core", dev=False, on_log=on_log, force_major=8)
        _ensure_dep(pkg, process_env, "@capacitor/cli", dev=True, on_log=on_log, force_major=8)

        config_data = {
            "appId": str(env.get("PACKAGE_NAME", "com.example.app")),
            "appName": str(env.get("APP_NAME", "MyApp")),
            "webDir": web_dir.name,
            "server": {"androidScheme": "https"},
        }
        config_text = json.dumps(config_data, ensure_ascii=False, indent=2) + "\n"
        (project_root / "capacitor.config.ts").unlink(missing_ok=True)
        (project_root / "capacitor.config.js").unlink(missing_ok=True)
        (project_root / "capacitor.config.json").write_text(config_text, encoding="utf-8")

        progress(45, "Step 3: 生成 Android 工程...")
        _log(on_log, "Step 3: 生成 Android 工程...")
        _ensure_dep(pkg, process_env, "@capacitor/android", dev=False, on_log=on_log, force_major=8)
        if not (project_root / "android").exists():
            _run_cmd([npx_cmd, "cap", "add", "android"], cwd=project_root, env=process_env, on_log=on_log)

        progress(55, "Step 4: 生成应用图标...")
        _log(on_log, "Step 4: 生成应用图标...")
        assets_dir = project_root / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)
        logo = task_input_dir / "logo.png"
        if logo.exists():
            shutil.copy2(logo, assets_dir / "logo.png")
            _run_assets_generate(project_root, process_env, npx_cmd, on_log=on_log)

        progress(60, "Step 5: 同步 Android 配置...")
        _log(on_log, "Step 5: 同步 Android 配置...")
        _run_cmd([npx_cmd, "cap", "sync", "android"], cwd=project_root, env=process_env, on_log=on_log)

    android_project_root = project_root if (is_web_task or is_html_task) else project_root / "android"
    android_app_dir = android_project_root / "app"

    permissions_raw = str(env.get("PERMISSIONS", "")).strip()
    permissions = [p for p in (perm.strip() for perm in permissions_raw.split(",")) if p]
    manifest_path = android_app_dir / "src" / "main" / "AndroidManifest.xml"
    _patch_android_manifest(
        manifest_path,
        env.get("SCREEN_ORIENTATION", "auto"),
        permissions,
        on_log=on_log,
    )
    build_gradle_kts = android_app_dir / "build.gradle.kts"
    build_gradle = android_app_dir / "build.gradle"
    if build_gradle_kts.exists():
        _patch_android_build_config(build_gradle_kts, env, on_log=on_log)
    elif build_gradle.exists():
        _patch_android_build_config(build_gradle, env, on_log=on_log)
    if not is_web_task and not is_html_task:
        package_name = str(env.get("PACKAGE_NAME", "")).strip()
        status_bar_hidden_enabled = str(env.get("STATUS_BAR_HIDDEN", "false")).strip().lower() == "true"
        double_click_exit_enabled = str(env.get("DOUBLE_CLICK_EXIT", "true")).strip().lower() == "true"
        raw_download_mode = str(env.get("DOWNLOAD_MODE", "picker")).strip().lower()
        if raw_download_mode not in {"silent", "picker"}:
            raw_download_mode = "picker"
        minimal_download_listener_enabled = task_mode == "convert"
        main_candidates = list(android_app_dir.rglob("MainActivity.kt")) + list(
            android_app_dir.rglob("MainActivity.java")
        )
        _log(
            on_log,
            "[MainActivity] skip ConvertAPK MainActivity injection; keep original Capacitor MainActivity",
        )
        if main_candidates:
            _reset_main_activity_if_convertapk_injected(
                main_candidates[0],
                package_name,
                on_log=on_log,
            )
            _sync_minimal_status_bar_hidden(
                main_candidates[0],
                enable=status_bar_hidden_enabled,
                on_log=on_log,
            )
            _sync_minimal_double_click_exit(
                main_candidates[0],
                enable=double_click_exit_enabled,
                on_log=on_log,
            )
            _sync_minimal_download_listener(
                main_candidates[0],
                enable=minimal_download_listener_enabled,
                download_mode=raw_download_mode,
                on_log=on_log,
            )

    progress(65, "Step 6: 配置 Android 项目...")
    _log(on_log, "Step 6: 配置 Android 项目...")
    android_home = _find_android_home()
    process_env["ANDROID_HOME"] = str(android_home)
    process_env["ANDROID_SDK_ROOT"] = str(android_home)
    local_props = android_project_root / "local.properties"
    local_props.write_text(f"sdk.dir={android_home.as_posix()}\n", encoding="utf-8")

    if not is_web_task and not is_html_task:
        gradle_file = android_app_dir / "build.gradle"
        if gradle_file.exists():
            gradle_text = gradle_file.read_text(encoding="utf-8")
            gradle_text = gradle_text.replace("versionName \"1.0\"", f"versionName \"{env.get('VERSION_NAME', '1.0.0')}\"")
            gradle_text = gradle_text.replace("versionCode 1", f"versionCode {env.get('VERSION_CODE', '1')}")
            gradle_file.write_text(gradle_text, encoding="utf-8")

    progress(70, "Step 7: 构建 Release 产物...")
    _log(on_log, "Step 7: 构建 Release 产物...")
    gradlew = android_project_root / ("gradlew.bat" if os.name == "nt" else "gradlew")
    if not gradlew.exists():
        raise RuntimeError("未找到 gradlew")
    _patch_gradle_wrapper(android_project_root, on_log=on_log)
    _repair_gradle_wrapper_jar(android_project_root, on_log=on_log)
    _ensure_gradle_properties(android_project_root, on_log=on_log)
    gradle_cmd = [str(gradlew)]
    gradle_cmd.append("bundleRelease" if output_format == "aab" else "assembleRelease")
    gradle_cmd.extend(["--stacktrace", "--info", "--build-cache"])
    init_script = _write_gradle_init(task_dir, on_log=on_log)
    gradle_cmd.extend(["--init-script", str(init_script)])
    _run_cmd(gradle_cmd, cwd=gradlew.parent, env=process_env, on_log=on_log)

    progress(80, "Step 8: 准备签名密钥...")
    _log(on_log, "Step 8: 准备签名密钥...")
    keystore_file = task_keystore_dir / "release.keystore"
    keystore_reused = env.get("KEYSTORE_REUSED", "false").lower() == "true"

    keytool = _find_java_tool(process_env, "keytool")
    if not keytool:
        raise RuntimeError("未找到 keytool，请安装 JDK 并配置 PATH")

    if keystore_reused:
        if not keystore_file.exists():
            raise RuntimeError("复用签名密钥失败：未找到 keystore")
    else:
        if not keystore_file.exists():
            _run_cmd([
                keytool,
                "-genkeypair",
                "-v",
                "-keystore", str(keystore_file),
                "-alias", env.get("KEY_ALIAS", "key0"),
                "-keyalg", "RSA",
                "-keysize", "2048",
                "-validity", "10000",
                "-storepass", env.get("KEYSTORE_PASSWORD", "android"),
                "-keypass", env.get("KEY_PASSWORD", "android"),
                "-dname", "CN=APK Builder, OU=Dev, O=Company, L=City, ST=State, C=CN"
            ], env=process_env, on_log=on_log)

    progress(90, "Step 9: 处理构建产物...")
    _log(on_log, "Step 9: 处理构建产物...")

    if output_format == "aab":
        bundle_dir = android_app_dir / "build" / "outputs" / "bundle" / "release"
        aab_files = list(bundle_dir.glob("*.aab"))
        if not aab_files:
            raise RuntimeError("未找到 AAB 输出")
        unsigned_aab = aab_files[0]
        signed_aab = task_output_dir / f"{env.get('APP_NAME', 'app')}-v{env.get('VERSION_NAME', '1.0.0')}.aab"
        jarsigner = _find_java_tool(process_env, "jarsigner")
        if not jarsigner:
            raise RuntimeError("未找到 jarsigner，请安装 JDK 并配置 PATH")
        _run_cmd([
            jarsigner,
            "-digestalg", "SHA-256",
            "-sigalg", "SHA256withRSA",
            "-keystore", str(keystore_file),
            "-storepass", env.get("KEYSTORE_PASSWORD", "android"),
            "-keypass", env.get("KEY_PASSWORD", "android"),
            "-signedjar", str(signed_aab),
            str(unsigned_aab),
            env.get("KEY_ALIAS", "key0")
        ], env=process_env, on_log=on_log)
        output_file = signed_aab
        _verify_signed_artifact_matches_keystore(
            artifact_file=signed_aab,
            artifact_format="aab",
            keytool=keytool,
            env=process_env,
            on_log=on_log,
        )
    else:
        apk_dir = android_app_dir / "build" / "outputs" / "apk" / "release"
        apk_files = list(apk_dir.glob("*.apk"))
        if not apk_files:
            raise RuntimeError("未找到 APK 输出")
        unsigned_apk = apk_files[0]
        aligned_apk = task_output_dir / "app-release-aligned.apk"
        signed_apk = task_output_dir / f"{env.get('APP_NAME', 'app')}-v{env.get('VERSION_NAME', '1.0.0')}.apk"

        zipalign = _find_build_tool(android_home, "zipalign.exe" if os.name == "nt" else "zipalign")
        apksigner = _find_build_tool(android_home, "apksigner.bat" if os.name == "nt" else "apksigner")

        _run_cmd([str(zipalign), "-p", "-f", "4", str(unsigned_apk), str(aligned_apk)], env=process_env, on_log=on_log)
        _run_cmd([
            str(apksigner),
            "sign",
            "--ks", str(keystore_file),
            "--ks-key-alias", env.get("KEY_ALIAS", "key0"),
            "--ks-pass", f"pass:{env.get('KEYSTORE_PASSWORD', 'android')}",
            "--key-pass", f"pass:{env.get('KEY_PASSWORD', 'android')}",
            "--out", str(signed_apk),
            str(aligned_apk)
        ], env=process_env, on_log=on_log)
        output_file = signed_apk
        _verify_signed_artifact_matches_keystore(
            artifact_file=signed_apk,
            artifact_format="apk",
            keytool=keytool,
            env=process_env,
            on_log=on_log,
            apksigner=str(apksigner),
        )


    progress(100, "Step 10: 构建完成")
    _log(on_log, "Step 10: 构建完成")

    return {
        "output_file": str(output_file),
        "output_format": output_format
    }
