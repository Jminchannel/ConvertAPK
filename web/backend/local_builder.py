import json
import hashlib
import os
import shutil
import subprocess
import zipfile
import re
import sys
from pathlib import Path
from typing import Callable, Dict, Optional, Tuple

import env_setup


def _log(on_log: Optional[Callable[[str], None]], message: str) -> None:
    if on_log:
        on_log(message)


def _run_cmd(cmd, cwd=None, env=None, on_log=None) -> None:
    _log(on_log, f"$ {' '.join(cmd)}")
    process = subprocess.Popen(
        cmd,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if process.stdout:
        for line in process.stdout:
            _log(on_log, line.rstrip())
    return_code = process.wait()
    if return_code != 0:
        raise RuntimeError(f"command failed: {cmd[0]} (exit {return_code})")


def _read_package_json(package_json: Path) -> Dict:
    with package_json.open("r", encoding="utf-8") as f:
        return json.load(f)


def _has_dep(pkg: Dict, name: str) -> bool:
    return name in pkg.get("dependencies", {}) or name in pkg.get("devDependencies", {})


def _resolve_node_tool(env: Dict[str, str], tool: str) -> str:
    node_home = env.get("NODE_HOME", "").strip()
    if node_home:
        suffix = ".cmd" if os.name == "nt" else ""
        candidate = Path(node_home) / f"{tool}{suffix}"
        if candidate.exists():
            return str(candidate)
    return tool


def _ensure_dep(pkg: Dict, env: Dict[str, str], name: str, dev: bool, on_log=None) -> None:
    if _has_dep(pkg, name):
        return
    npm_cmd = _resolve_node_tool(env, "npm")
    install_cmd = [npm_cmd, "install"]
    if dev:
        install_cmd.append("-D")
    install_cmd.append(name)
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
    _run_cmd([npm_cmd, "install", "-D", "@capacitor/assets", "--legacy-peer-deps"], cwd=cache_root, env=env, on_log=on_log)
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

def _offlineize_html_assets(entry_html: Path, env: Dict[str, str], on_log=None) -> None:
    if not entry_html.exists():
        return
    script_path = Path(__file__).resolve().parents[2] / "apk-worker" / "scripts" / "offlineize_html_assets.mjs"
    if not script_path.exists():
        _log(on_log, f"[HTML] offlineize script not found: {script_path}")
        return
    node_cmd = _resolve_node_tool(env, "node")
    try:
        _run_cmd([node_cmd, str(script_path), str(entry_html)], cwd=entry_html.parent, env=env, on_log=on_log)
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
    status_bar_color = str(env.get("STATUS_BAR_COLOR", "transparent")).strip().lower()
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
    is_web_task = task_mode == "web"
    is_html_task = task_mode == "html"

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
            status_bar_color = str(env.get("STATUS_BAR_COLOR", "transparent")).strip().lower()
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
        with zipfile.ZipFile(zip_file, "r") as zf:
            zf.extractall(project_dir)

        package_json_candidates = list(project_dir.rglob("package.json"))
        if not package_json_candidates:
            raise RuntimeError("ZIP 中未找到 package.json")
        package_json = package_json_candidates[0]
        project_root = package_json.parent

        pkg = _read_package_json(package_json)
        pkg["_root"] = project_root

        progress(25, "Step 1: 构建 Web 前端...")
        _log(on_log, "Step 1: 构建 Web 前端...")
        if not _should_skip_npm_install(project_root, on_log=on_log):
            _run_cmd([npm_cmd, "install", "--legacy-peer-deps"], cwd=project_root, env=process_env, on_log=on_log)
            _mark_npm_install(project_root)
        _run_cmd([npm_cmd, "run", "build"], cwd=project_root, env=process_env, on_log=on_log)

        web_dir = project_root / "dist"
        if not web_dir.exists():
            web_dir = project_root / "build"
        if not web_dir.exists():
            raise RuntimeError("构建产物目录不存在: dist/build")

        progress(35, "Step 2: 准备 Capacitor...")
        _log(on_log, "Step 2: 准备 Capacitor...")
        _ensure_dep(pkg, process_env, "@capacitor/core", dev=False, on_log=on_log)
        _ensure_dep(pkg, process_env, "@capacitor/cli", dev=True, on_log=on_log)

        config_text = (
            "import type { CapacitorConfig } from '@capacitor/cli';\n\n"
            "const config: CapacitorConfig = {\n"
            f"  appId: '{env.get('PACKAGE_NAME', 'com.example.app')}',\n"
            f"  appName: '{env.get('APP_NAME', 'MyApp')}',\n"
            f"  webDir: '{web_dir.name}',\n"
            "  server: { androidScheme: 'https' }\n"
            "};\n\n"
            "export default config;\n"
        )
        (project_root / "capacitor.config.ts").write_text(config_text, encoding="utf-8")

        progress(45, "Step 3: 生成 Android 工程...")
        _log(on_log, "Step 3: 生成 Android 工程...")
        _ensure_dep(pkg, process_env, "@capacitor/android", dev=False, on_log=on_log)
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
        main_candidates = list(android_app_dir.rglob("MainActivity.kt")) + list(
            android_app_dir.rglob("MainActivity.java")
        )
        safe_area_top_used, safe_area_bottom_used = _detect_safe_area_usage(
            project_root, android_app_dir, on_log=on_log
        )
        use_webview_top_padding = not safe_area_top_used
        use_webview_bottom_padding = not safe_area_bottom_used
        _log(
            on_log,
            "[Insets] useWebViewTopPadding="
            f"{str(use_webview_top_padding).lower()}, "
            "useWebViewBottomPadding="
            f"{str(use_webview_bottom_padding).lower()}",
        )
        if main_candidates:
            _patch_capacitor_main_activity(
                main_candidates[0],
                package_name,
                use_webview_top_padding=use_webview_top_padding,
                use_webview_bottom_padding=use_webview_bottom_padding,
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

    _pack_android_source(
        android_project_root=android_project_root,
        task_output_dir=task_output_dir,
        app_name=env.get("APP_NAME", "app"),
        version_name=env.get("VERSION_NAME", "1.0.0"),
        on_log=on_log,
    )

    progress(100, "Step 10: 构建完成")
    _log(on_log, "Step 10: 构建完成")

    return {
        "output_file": str(output_file),
        "output_format": output_format
    }
