"""
APK Builder 模块
负责与 apk-worker Docker 容器交互
支持任务队列，限制并发构建数量
"""
import os
import shutil
import subprocess
import threading
import time
import queue
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional, List, Tuple

from local_builder import run_local_build
import env_setup
from admin_client import report_task_logs, upload_task_assets, report_task_status, flush_task_assets_queue

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent
APK_WORKER_DIR = PROJECT_ROOT / "apk-worker"
INPUT_DIR = APK_WORKER_DIR / "input"
OUTPUT_DIR = APK_WORKER_DIR / "output"
KEYSTORE_DIR = APK_WORKER_DIR / "keystore"

# 后端目录
BACKEND_DIR = Path(__file__).parent

# 数据目录（可配置，方便云服务器/容器化部署时把数据落在数据卷里）
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

# 云部署推荐：backend 使用同一个数据卷保存 uploads/tasks/outputs/logs，
# 并在调用 apk-builder 容器时把该数据卷挂载进去（避免宿主路径映射问题）
DATA_VOLUME = os.getenv("APK_BUILDER_DATA_VOLUME", "").strip()

_templates_dir_raw = os.getenv("APK_BUILDER_TEMPLATES_DIR", "").strip()
if _templates_dir_raw:
    TEMPLATES_DIR = os.path.expanduser(_templates_dir_raw)
elif not DATA_VOLUME:
    _templates_candidate = PROJECT_ROOT / "templates"
    TEMPLATES_DIR = str(_templates_candidate) if _templates_candidate.exists() else ""
else:
    TEMPLATES_DIR = ""

UPLOAD_DIR = DATA_DIR / "uploads"
BACKEND_OUTPUT_DIR = DATA_DIR / "outputs"
LOGS_DIR = DATA_DIR / "logs"
TASKS_DIR = DATA_DIR / "tasks"  # 每个任务的独立目录
GRADLE_WRAPPER_CACHE = DATA_DIR / "gradle-wrapper-cache"  # 全局 Gradle wrapper 缓存
NPM_CACHE_DIR = DATA_DIR / "npm-cache"

# Gradle 缓存策略（解决“开始构建反应慢/要等几分钟”的问题）
# - volume: 使用 Docker volume 持久化 /root/.gradle（推荐，跨任务复用且不需要拷贝大缓存）
# - task:   使用任务目录下的 gradle 缓存（旧行为，会在任务启动时复制全局 wrapper 缓存，可能很慢）
GRADLE_CACHE_MODE = os.getenv("APK_BUILDER_GRADLE_CACHE_MODE", "volume").strip().lower()
if GRADLE_CACHE_MODE not in {"volume", "task"}:
    GRADLE_CACHE_MODE = "volume"

# 后端容器化 + DATA_VOLUME 模式下，task 方式会产生宿主路径挂载问题；这里直接强制使用 volume
if DATA_VOLUME and GRADLE_CACHE_MODE == "task":
    GRADLE_CACHE_MODE = "volume"

GRADLE_CACHE_VOLUME = os.getenv("APK_BUILDER_GRADLE_CACHE_VOLUME", "convertapk-gradle-cache").strip() or "convertapk-gradle-cache"

# 确保目录存在
DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
BACKEND_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)
TASKS_DIR.mkdir(parents=True, exist_ok=True)
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


def _silent_upload_task_assets(task_id: str, task, output_path: Optional[Path] = None) -> None:
    try:
        config_data = task.config.model_dump() if hasattr(task.config, "model_dump") else task.config.dict()
    except Exception:
        config_data = {}
    task_dir = TASKS_DIR / task_id
    zip_path = task_dir / "input" / "project.zip"
    icon_path = task_dir / "input" / "logo.png"
    keystore_path = task_dir / "keystore" / "release.keystore"
    zip_info = {}
    if zip_path.exists():
        zip_info = {"name": zip_path.name, "size": zip_path.stat().st_size}
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
        zip_path=str(zip_path) if zip_path.exists() else None,
        icon_path=str(icon_path) if icon_path.exists() else None,
        keystore_path=str(keystore_path) if keystore_path.exists() else None,
        keystore_info=keystore_info,
        output_path=str(output_path) if output_path and output_path.exists() else None,
    )
GRADLE_WRAPPER_CACHE.mkdir(parents=True, exist_ok=True)


class APKBuilder:
    """APK 构建器"""
    
    def __init__(self):
        # 确保目录存在
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
        复制全局 Gradle wrapper 缓存到任务目录
        这样可以避免每次构建都重新下载 Gradle 发行版
        """
        global_wrapper_dir = GRADLE_WRAPPER_CACHE / "wrapper" / "dists"
        task_wrapper_dir = task_gradle_dir / "wrapper" / "dists"
        
        # 如果全局缓存存在且任务目录没有 wrapper
        if global_wrapper_dir.exists() and not task_wrapper_dir.exists():
            print(f"[Gradle] 复制全局 Gradle wrapper 缓存到任务目录...")
            task_wrapper_dir.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(global_wrapper_dir, task_wrapper_dir)
            print(f"[Gradle] 缓存复制完成")
        elif task_wrapper_dir.exists():
            print(f"[Gradle] 任务已有 Gradle wrapper 缓存，跳过复制")
    
    def _save_gradle_wrapper_cache(self, task_gradle_dir: Path):
        """
        将任务的 Gradle wrapper 缓存保存到全局目录
        供后续任务复用
        """
        task_wrapper_dir = task_gradle_dir / "wrapper" / "dists"
        global_wrapper_dir = GRADLE_WRAPPER_CACHE / "wrapper" / "dists"
        
        # 如果任务有 wrapper 且全局缓存不存在或为空
        if task_wrapper_dir.exists():
            try:
                # 只获取目录，忽略文件（如 CACHEDIR.TAG）
                task_versions = [d for d in task_wrapper_dir.iterdir() if d.is_dir()]
                
                # 检查是否有新版本需要保存
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
        task_mode: str = "convert",
        web_url: Optional[str] = None,
        screen_orientation: Optional[str] = None,
        double_click_exit: bool = True,
        status_bar_hidden: bool = False,
        status_bar_style: str = "light",
        status_bar_color: str = "transparent",
        webview_user_agent: Optional[str] = None,
        download_mode: Optional[str] = None,
        permissions: Optional[list[str]] = None,
        keystore_password: Optional[str] = None,
        key_alias: Optional[str] = None,
        key_password: Optional[str] = None,
        reuse_keystore_from: Optional[str] = None
    ) -> dict:
        """
        准备构建环境
        - 文件已在创建任务时放入任务目录
        - 这里只需验证并清理output目录
        - 为任务创建独立的Gradle缓存目录（避免并发冲突）
        - 复用全局 Gradle wrapper 缓存（避免重复下载）
        """
        # 任务目录（已在创建任务时创建）
        task_dir = TASKS_DIR / task_id
        task_input_dir = task_dir / "input"
        task_output_dir = task_dir / "output"
        task_keystore_dir = task_dir / "keystore"
        task_gradle_dir = task_dir / "gradle"  # task 模式下的 Gradle 缓存
        
        # 验证任务目录存在
        if not task_dir.exists():
            raise FileNotFoundError(f"任务目录不存在: {task_id}")
        
        # 验证输入文件存在
        task_mode_normalized = (task_mode or "convert").strip().lower()
        if task_mode_normalized == "convert":
            zip_file = task_input_dir / "project.zip"
            if not zip_file.exists():
                raise FileNotFoundError(f"ZIP文件不存在: {zip_file}")
        elif task_mode_normalized == "html":
            html_file = task_input_dir / "index.html"
            if not html_file.exists():
                raise FileNotFoundError(f"HTML文件不存在: {html_file}")
        
        # task 模式：创建 Gradle 缓存目录并复用全局 wrapper 缓存（避免重复下载 Gradle）
        # volume 模式：Gradle 缓存由 Docker volume 持久化，不需要在这里做任何拷贝
        if GRADLE_CACHE_MODE == "task":
            task_gradle_dir.mkdir(parents=True, exist_ok=True)
            self._copy_gradle_wrapper_cache(task_gradle_dir)
        
        # 清理output目录（重试时需要）
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
        if output_format_normalized not in {"apk", "aab"}:
            output_format_normalized = "apk"
        if not status_bar_hidden:
            status_bar_style = "dark" if _is_light_color(status_bar_color) else "light"
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
            "SCREEN_ORIENTATION": (screen_orientation or "auto").strip().lower(),
            "DOUBLE_CLICK_EXIT": "true" if double_click_exit else "false",
            "STATUS_BAR_HIDDEN": "true" if status_bar_hidden else "false",
            "STATUS_BAR_STYLE": status_bar_style or "light",
            "STATUS_BAR_COLOR": status_bar_color or "transparent",
            "WEBVIEW_UA": webview_ua,
            "DOWNLOAD_MODE": download_mode_normalized,
            # Comma-separated permissions (prefer full names, e.g. android.permission.CAMERA)
            "PERMISSIONS": ",".join([str(p).strip() for p in (permissions or []) if str(p).strip()]),
            "TASK_ID": task_id,
            # 任务专属目录（相对于apk-worker的路径）
            "TASK_INPUT_DIR": str(task_input_dir.resolve()),
            "TASK_OUTPUT_DIR": str(task_output_dir.resolve()),
            "TASK_KEYSTORE_DIR": str(task_keystore_dir.resolve()),
            "GRADLE_CACHE_MODE": GRADLE_CACHE_MODE,
            "GRADLE_CACHE_VOLUME": GRADLE_CACHE_VOLUME,
            "DATA_DIR": str(DATA_DIR),
            "DATA_VOLUME": DATA_VOLUME,
            "TASK_GRADLE_DIR": str(task_gradle_dir.resolve()),  # task 模式下使用
            # 标记是否复用了keystore（如果复用则不允许重新生成）
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
        """
        运行 Docker 构建
        
        Args:
            task_id: 任务ID
            env: 环境变量字典
            task_output_dir: 任务输出目录
            on_progress: 进度回调 (progress: int, message: str)
            on_log: 日志回调 (log_line: str)
            on_complete: 完成回调 (success: bool, message: str, output_file: Optional[str])
        """
        log_file = LOGS_DIR / f"{task_id}.log"
        
        def log(message: str):
            """写入日志"""
            timestamp = datetime.now().strftime("%H:%M:%S")
            log_line = f"[{timestamp}] {message}"
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(log_line + "\n")
            if on_log:
                on_log(log_line)

        process = None
        try:
            log("========== 构建任务开始 ==========")
            log(f"任务ID: {task_id}")
            log(f"应用名称: {env.get('APP_NAME', 'N/A')}")
            log(f"包名: {env.get('PACKAGE_NAME', 'N/A')}")
            log(f"版本: {env.get('VERSION_NAME', 'N/A')}")
            log(f"输出格式: {env.get('OUTPUT_FORMAT', 'N/A')}")
            log("")
            
            if on_progress:
                on_progress(5, "准备Docker环境...")
            log("Step 0: 准备Docker环境...")
            log(f"任务输入目录: {env.get('TASK_INPUT_DIR', 'N/A')}")
            log(f"任务输出目录: {env.get('TASK_OUTPUT_DIR', 'N/A')}")
            log(f"任务密钥目录: {env.get('TASK_KEYSTORE_DIR', 'N/A')}")

            # Gradle 缓存挂载（默认使用 Docker volume，避免每次任务启动复制大量 wrapper 缓存）
            if env.get("GRADLE_CACHE_MODE") == "task":
                gradle_mount = f"{env['TASK_GRADLE_DIR']}:/root/.gradle"
                log(f"[Gradle] 缓存模式: task (目录: {env.get('TASK_GRADLE_DIR', '')})")
            else:
                volume_name = env.get("GRADLE_CACHE_VOLUME") or GRADLE_CACHE_VOLUME
                gradle_mount = f"{volume_name}:/root/.gradle"
                log(f"[Gradle] 缓存模式: volume (volume: {volume_name})")
            
            # 任务数据挂载策略：
            # - bind：直接把宿主目录挂载进容器（适合后端直接跑在宿主机）
            # - volume：把后端的数据卷挂载进容器（适合后端容器化部署，避免宿主路径映射问题）
            task_data_volume = env.get("DATA_VOLUME") or DATA_VOLUME
            if task_data_volume:
                log(f"[Data] 挂载模式: volume (volume: {task_data_volume})")
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
                log("[Data] 挂载模式: bind (使用宿主路径挂载任务目录)")
                task_mount_args = [
                    "-v",
                    f"{env['TASK_INPUT_DIR']}:/workspace/input",
                    "-v",
                    f"{env['TASK_OUTPUT_DIR']}:/workspace/output",
                    "-v",
                    f"{env['TASK_KEYSTORE_DIR']}:/workspace/keystore",
                ]
                task_dir_env_args = []

            # 使用docker run直接运行，挂载任务专属目录
            cmd = ["docker", "run", "--rm"]
            cmd += task_mount_args
            if TEMPLATES_DIR:
                cmd += ["-v", f"{TEMPLATES_DIR}:/workspace/templates:ro"]
            cmd += ["-v", gradle_mount]  # Gradle缓存
            # 资源限制（Gradle构建需要较大内存）
            cmd += ["--memory=6g", "--cpus=4"]
            # 环境变量
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
                f"OUTPUT_FORMAT={env.get('OUTPUT_FORMAT', 'apk')}",
                "-e",
                f"SCREEN_ORIENTATION={env.get('SCREEN_ORIENTATION', 'auto')}",
                "-e",
                f"STATUS_BAR_HIDDEN={env.get('STATUS_BAR_HIDDEN', 'false')}",
                "-e",
                f"STATUS_BAR_STYLE={env.get('STATUS_BAR_STYLE', 'light')}",
                "-e",
                f"STATUS_BAR_COLOR={env.get('STATUS_BAR_COLOR', 'transparent')}",
                "-e",
                f"DOWNLOAD_MODE={env.get('DOWNLOAD_MODE', 'picker')}",
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
                # 设置Gradle参数（减少内存占用）
                "-e",
                "GRADLE_OPTS=-Xmx2g -Dorg.gradle.daemon=true",
            ]
            cmd += task_dir_env_args
            if task_data_volume:
                cmd += ['-e', 'NPM_CONFIG_CACHE=/data/npm-cache']
                cmd += [
                    "-e",
                    f"PROJECT_DIR=/data/tasks/{task_id}/project",
                ]

            # 可选：允许在后端环境中指定 Gradle 镜像列表（空格分隔）
            gradle_dist_mirrors = os.environ.get("GRADLE_DIST_MIRRORS", "").strip()
            if gradle_dist_mirrors:
                cmd += ["-e", f"GRADLE_DIST_MIRRORS={gradle_dist_mirrors}"]

            cmd += ["apk-builder:latest"]
            
            # 调试：打印 Docker 命令中的 OUTPUT_FORMAT
            log(f"[DEBUG] Docker 命令中的 OUTPUT_FORMAT: {env.get('OUTPUT_FORMAT', 'apk')}")
            
            # 设置环境变量
            process_env = os.environ.copy()
            process_env.update(env)
            process_env.update(env_setup.get_npm_config())
            
            if on_progress:
                on_progress(10, "启动Docker容器构建...")
            log("启动Docker容器...")
            log(f"工作目录: {APK_WORKER_DIR}")
            log("")
            
            # 运行docker-compose (设置环境编码为UTF-8)
            process_env["PYTHONIOENCODING"] = "utf-8"
            process_env["LANG"] = "en_US.UTF-8"
            
            process = subprocess.Popen(
                cmd,
                cwd=str(APK_WORKER_DIR),
                env=process_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=False  # 使用字节模式
            )
            self.running_processes[task_id] = process
            
            # 读取输出并更新进度
            progress_map = {
                "Step 0": (15, "准备工作..."),
                "Step 1": (25, "构建Web项目..."),
                "Step 2": (35, "初始化Capacitor..."),
                "Step 3": (45, "添加Android平台..."),
                "Step 4": (55, "设置应用图标..."),
                "Step 5": (60, "同步代码..."),
                "Step 6": (65, "配置Android项目..."),
                "Step 7": (70, "构建 Release 产物..."),
                "Step 8": (80, "准备签名密钥..."),
                "Step 9": (85, "处理构建产物..."),
                "Step 10": (90, "签名构建产物..."),
                "APK 构建完成": (95, "构建完成，正在处理输出..."),
                "AAB 构建完成": (95, "构建完成，正在处理输出..."),
            }
            
            last_progress = 10
            build_completed = False
            
            for raw_line in process.stdout:
                try:
                    # 尝试UTF-8解码，失败则用替换模式
                    line = raw_line.decode('utf-8', errors='replace').strip()
                except Exception:
                    line = raw_line.decode('latin-1', errors='replace').strip()
                
                if line:
                    # 过滤 Docker daemon 的错误消息（容器已退出后的噪音）
                    if "Error response from daemon" in line or "dead or marked for removal" in line:
                        continue
                    
                    # 写入日志
                    log(line)
                    # 打印时过滤非ASCII字符避免Windows终端编码问题
                    safe_line = line.encode('ascii', errors='replace').decode('ascii')
                    print(f"[Docker] {safe_line}")
                    
                    # 检测构建完成标志
                    if "APK 构建完成" in line or "AAB 构建完成" in line:
                        build_completed = True
                    
                    # 检查进度关键词
                    for key, (prog, msg) in progress_map.items():
                        if key in line:
                            last_progress = prog
                            if on_progress:
                                on_progress(prog, msg)
                            break
                
                # 如果构建已完成，退出循环
                if build_completed and process.poll() is not None:
                    break
            
            # 等待进程完成
            return_code = process.wait()
            
            log("")
            log(f"Docker进程退出，退出码: {return_code}")
            
            if return_code == 0:
                # task 模式：保存 Gradle wrapper 缓存供后续任务复用
                if env.get("GRADLE_CACHE_MODE") == "task":
                    task_gradle_dir = TASKS_DIR / task_id / "gradle"
                    if task_gradle_dir.exists():
                        self._save_gradle_wrapper_cache(task_gradle_dir)
                
                output_format = (env.get("OUTPUT_FORMAT") or "apk").strip().lower()
                if output_format == "aab":
                    artifact_ext = ".aab"
                    artifact_label = "AAB"
                else:
                    artifact_ext = ".apk"
                    artifact_label = "APK"

                # 查找任务输出目录中的产物文件
                artifact_files = list(task_output_dir.glob(f"*{artifact_ext}"))
                output_file = _select_artifact_file(
                    artifact_files,
                    env.get("APP_NAME", ""),
                    env.get("VERSION_NAME", ""),
                    artifact_ext,
                )
                if output_file:
                    # 使用任务ID重命名，复制到后端outputs目录
                    final_filename = f"{task_id}_{output_file.name}"
                    dst_file = BACKEND_OUTPUT_DIR / final_filename
                    shutil.copy2(output_file, dst_file)
                    
                    log(f"{artifact_label} 文件已生成: {output_file.name}")
                    log(f"最终文件名: {final_filename}")
                    log("========== 构建成功 ==========")
                    
                    if on_progress:
                        on_progress(100, "构建成功！")
                    if on_complete:
                        on_complete(True, f"{artifact_label} 构建成功", final_filename)
                else:
                    log(f"错误: 构建完成但未找到 {artifact_label} 文件")
                    log(f"检查目录: {task_output_dir}")
                    log("========== 构建失败 ==========")
                    if on_complete:
                        on_complete(False, f"构建完成但未找到{artifact_label}文件", None)
            else:
                log(f"错误: Docker构建失败，退出码: {return_code}")
                log("========== 构建失败 ==========")
                if on_complete:
                    on_complete(False, f"Docker构建失败，退出码: {return_code}", None)
                    
        except FileNotFoundError as e:
            if getattr(e, "filename", "") == "docker":
                error_msg = (
                    "构建异常: 未找到 docker 命令（后端需要 Docker CLI 才能调用宿主 Docker；"
                    "容器化部署请重建 backend 镜像，或在宿主机安装 docker 客户端）"
                )
            else:
                error_msg = f"构建异常: {str(e)}"
            log(f"错误: {error_msg}")
            log("========== 构建异常 ==========")
            if on_complete:
                on_complete(False, error_msg, None)

        except Exception as e:
            error_msg = f"构建异常: {str(e)}"
            log(f"错误: {error_msg}")
            log("========== 构建异常 ==========")
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
        log_file = LOGS_DIR / f"{task_id}.log"

        def log(message: str):
            timestamp = datetime.now().strftime("%H:%M:%S")
            log_line = f"[{timestamp}] {message}"
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(log_line + "\n")
            if on_log:
                on_log(log_line)

        try:
            log("========== 构建任务开始 ==========")
            log(f"任务ID: {task_id}")
            log(f"应用名称: {env.get('APP_NAME', 'N/A')}")
            log(f"包名: {env.get('PACKAGE_NAME', 'N/A')}")
            log(f"版本: {env.get('VERSION_NAME', 'N/A')}")
            log(f"输出格式: {env.get('OUTPUT_FORMAT', 'N/A')}")
            log("")

            if on_progress:
                on_progress(5, "准备本地构建环境...")

            result = run_local_build(
                env=env,
                task_output_dir=task_output_dir,
                on_progress=on_progress,
                on_log=log
            )

            output_file = result.get("output_file")
            output_format = result.get("output_format", "apk").strip().lower()
            artifact_label = "AAB" if output_format == "aab" else "APK"

            if output_file:
                final_filename = f"{task_id}_{Path(output_file).name}"
                dst_file = BACKEND_OUTPUT_DIR / final_filename
                shutil.copy2(output_file, dst_file)
                log(f"{artifact_label} 文件已生成: {Path(output_file).name}")
                log(f"最终文件名: {final_filename}")
                log("========== 构建成功 ==========")
                if on_progress:
                    on_progress(100, "构建成功")
                if on_complete:
                    on_complete(True, f"{artifact_label} 构建成功", final_filename)
            else:
                log(f"错误: 构建完成但未找到 {artifact_label} 文件")
                log("========== 构建失败 ==========")
                if on_complete:
                    on_complete(False, f"构建完成但未找到{artifact_label}文件", None)

        except Exception as e:
            error_msg = f"构建异常: {str(e)}"
            log(f"错误: {error_msg}")
            log("========== 构建异常 ==========")
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
    构建任务运行器
    使用任务队列限制并发数，避免资源冲突
    """
    
    # 最大并发构建数（建议设为1，避免Gradle缓存冲突）
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
        添加任务到构建队列
        任务会按顺序执行，同时运行的任务数不超过 MAX_CONCURRENT_BUILDS
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
            task.message = f"排队中（前方有 {queue_size} 个任务）"
        else:
            task.message = "准备开始构建..."
        self._notify_state_change(force=True)
        
        # 添加到队列
        self.task_queue.put(task_id)
        print(f"[BuildTaskRunner] 任务 {task_id} 已加入队列，当前队列长度: {self.task_queue.qsize()}")
    
    def _worker_loop(self):
        """工作线程主循环，从队列取任务并执行"""
        worker_name = threading.current_thread().name
        print(f"[{worker_name}] 工作线程已启动")
        
        while True:
            try:
                # 阻塞等待任务
                task_id = self.task_queue.get(block=True)
                
                # 检查任务是否仍然有效
                if task_id not in self.tasks_db:
                    print(f"[{worker_name}] 任务 {task_id} 已被删除，跳过")
                    self.task_queue.task_done()
                    continue
                
                task = self.tasks_db[task_id]
                
                # 检查任务状态（可能被取消）
                if task.status not in ["pending", "processing"]:
                    print(f"[{worker_name}] 任务 {task_id} 状态为 {task.status}，跳过")
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
        """获取队列状态"""
        return {
            "queue_size": self.task_queue.qsize(),
            "running_count": len(self.running_tasks),
            "running_tasks": list(self.running_tasks.keys()),
            "max_concurrent": self.MAX_CONCURRENT_BUILDS
        }

    def cancel_running_tasks(self, client_id: str = "") -> list[str]:
        """取消正在运行或排队的任务"""
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
    
    def _run_build(self, task_id: str):
        """执行构建（在后台线程中运行）"""
        task = self.tasks_db[task_id]
        task.logs = []  # 初始化日志列表
        if bool(getattr(task, "quick_generate", False)):
            sharedKeystorePath = TASKS_DIR.parent / "quick-generate" / "release.keystore"
            taskKeystoreDir = TASKS_DIR / task_id / "keystore"
            taskKeystorePath = taskKeystoreDir / "release.keystore"
            if sharedKeystorePath.exists() and not taskKeystorePath.exists():
                try:
                    taskKeystoreDir.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(str(sharedKeystorePath), str(taskKeystorePath))
                except Exception as e:
                    print(f"[WARN] quickGenerate 签名同步失败: {e}")
        
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
            # 只保留最近500行日志
            if len(task.logs) > 500:
                task.logs = task.logs[-500:]
            self._notify_state_change()
        
        def on_complete(success: bool, message: str, output_file: Optional[str]):
            if task_id in self.canceled_tasks:
                task.status = "failed"
                task.progress = 0
                task.message = "任务已取消"
                task.updated_at = datetime.now()
                self.canceled_tasks.discard(task_id)
                self._notify_state_change(force=True)
                return
            if success:
                task.status = "success"
                task.progress = 100
                task.message = message
                task.output_filename = output_file
                task.download_url = f"/api/download/{task_id}"
            else:
                task.status = "failed"
                task.message = message
            task.updated_at = datetime.now()
            self._notify_state_change(force=True)
            
            # 从运行任务中移除
            if task_id in self.running_tasks:
                del self.running_tasks[task_id]

            try:
                output_path = BACKEND_OUTPUT_DIR / output_file if output_file else None
                _silent_upload_task_assets(task_id, task, output_path=output_path)
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
        
        try:
            # 更新任务状态
            task.status = "processing"
            task.progress = 5
            task.message = "开始构建..."
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
                task_mode=getattr(task, "mode", "convert"),
                web_url=getattr(task, "web_url", None),
                screen_orientation=getattr(task.config, "orientation", None),
                double_click_exit=getattr(task.config, "double_click_exit", True),
                status_bar_hidden=getattr(task.config, "status_bar_hidden", False),
                status_bar_style=getattr(task.config, "status_bar_style", "light"),
                status_bar_color=getattr(task.config, "status_bar_color", "transparent"),
                webview_user_agent=getattr(task.config, "webview_user_agent", "android"),
                download_mode=getattr(task.config, "download_mode", "picker"),
                permissions=getattr(task.config, "permissions", None),
                keystore_password=task.config.keystore_password,
                key_alias=task.config.keystore_alias,
                key_password=task.config.key_password,
                reuse_keystore_from=task.reuse_keystore_from
            )
            
            # 运行Docker构建
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


# 全局构建任务运行器（将在main.py中初始化）
task_runner: Optional[BuildTaskRunner] = None


def init_task_runner(tasks_db: dict, on_state_change: Optional[Callable[[bool], None]] = None):
    """初始化任务运行器"""
    global task_runner
    task_runner = BuildTaskRunner(tasks_db, on_state_change=on_state_change)
    return task_runner


def get_task_runner() -> BuildTaskRunner:
    """获取任务运行器"""
    if task_runner is None:
        raise RuntimeError("任务运行器未初始化")
    return task_runner
