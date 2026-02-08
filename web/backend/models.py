from typing_compat import patch_typing_eval_type

patch_typing_eval_type()

import re

from pydantic import BaseModel, ConfigDict, field_validator
from typing import Optional, List
from enum import Enum
from datetime import datetime


class BuildStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"


class AppConfig(BaseModel):
    """APK构建配置"""
    model_config = ConfigDict(from_attributes=True)
    app_name: str
    package_name: str
    version_name: str = "1.0.0"
    version_code: int = 1
    keystore_alias: Optional[str] = None
    keystore_password: Optional[str] = None
    key_password: Optional[str] = None
    output_format: str = "apk"
    # portrait / landscape / auto (auto = follow system, do not force in AndroidManifest)
    orientation: str = "auto"
    # Double-click back to exit
    double_click_exit: bool = True
    # Status Bar
    status_bar_hidden: bool = False
    status_bar_style: str = "light"  # light | dark
    status_bar_color: str = "transparent"  # transparent | #FFFFFF
    # WebView UA (web mode)
    webview_user_agent: str = "android"  # android | pc
    # HTML mode resource localization switch: true = offlineize remote assets, false = keep remote links
    html_localize_resources: bool = True
    # HTML mode download behavior: silent (save directly) | picker (system file manager)
    download_mode: str = "picker"
    # Frontend sends short names (e.g. INTERNET) or full names (android.permission.INTERNET)
    permissions: List[str] = []

    @field_validator("package_name")
    @classmethod
    def validate_package_name(cls, value: str) -> str:
        trimmed = value.strip() if isinstance(value, str) else ""
        if not trimmed:
            raise ValueError("package_name is required")
        if not re.fullmatch(r"[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+", trimmed):
            raise ValueError(
                "package_name must be dot-separated, lowercase letters/digits/underscore, and each segment must start with a letter"
            )
        return trimmed

    @field_validator("keystore_password", "key_password")
    @classmethod
    def validate_sign_passwords(cls, value: Optional[str], info) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, str) and value == "":
            return None
        raw = str(value)
        if len(raw) < 6:
            raise ValueError(f"{info.field_name} must be at least 6 characters")
        return raw

    @field_validator("orientation")
    @classmethod
    def validate_orientation(cls, value: str) -> str:
        raw = (value or "").strip().lower()
        if raw in {"portrait", "landscape", "auto"}:
            return raw
        # Backward/forward compatible default: follow system
        return "auto"

    @field_validator("permissions")
    @classmethod
    def validate_permissions(cls, value: List[str]) -> List[str]:
        if not value:
            return []
        normalized: list[str] = []
        seen = set()
        for item in value:
            perm = str(item or "").strip()
            if not perm:
                continue
            if perm.startswith("android.permission."):
                full = perm
            elif "." in perm:
                # allow any fully qualified permission name (including custom permissions)
                full = perm
            else:
                full = f"android.permission.{perm}"
            if full in seen:
                continue
            seen.add(full)
            normalized.append(full)
        return normalized

    @field_validator("status_bar_style")
    @classmethod
    def validate_status_bar_style(cls, value: str) -> str:
        raw = (value or "").strip().lower()
        return raw if raw in {"light", "dark"} else "light"

    @field_validator("status_bar_color")
    @classmethod
    def validate_status_bar_color(cls, value: str) -> str:
        raw = (value or "").strip()
        if not raw:
            return "transparent"
        lower = raw.lower()
        if lower in {"transparent", "@android:color/transparent"}:
            return "transparent"
        if lower in {"white", "#ffffff", "#ffffffff"}:
            return "#FFFFFF"
        # accept hex colors (#RRGGBB / #AARRGGBB)
        if re.fullmatch(r"#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{8})", raw):
            return raw.upper()
        # fallback: keep as-is (lets advanced users pass custom references)
        return raw

    @field_validator("webview_user_agent")
    @classmethod
    def validate_webview_user_agent(cls, value: str) -> str:
        raw = (value or "").strip().lower()
        if raw in {"pc", "desktop", "windows"}:
            return "pc"
        return "android"

    @field_validator("download_mode")
    @classmethod
    def validate_download_mode(cls, value: str) -> str:
        raw = (value or "").strip().lower()
        if raw in {"silent", "picker"}:
            return raw
        if raw in {"explorer", "file_manager", "resource_manager"}:
            return "picker"
        return "picker"

    @field_validator("output_format")
    @classmethod
    def validate_output_format(cls, value: str) -> str:
        raw = (value or "").strip().lower()
        if raw in {"apk", "aab"}:
            return raw
        if "aab" in raw or "bundle" in raw:
            return "aab"
        return "apk"


class BuildTask(BaseModel):
    """构建任务"""
    model_config = ConfigDict(from_attributes=True)
    id: str
    client_id: str = ""  # 客户端ID，用于隔离不同设备/浏览器
    quick_generate: bool = False
    mode: str = "convert"
    web_url: Optional[str] = None
    filename: Optional[str] = None
    html_filename: Optional[str] = None
    icon_filename: Optional[str] = None
    keystore_filename: Optional[str] = None
    config: AppConfig
    status: BuildStatus = BuildStatus.PENDING
    created_at: datetime
    updated_at: datetime
    progress: int = 0
    message: str = ""
    download_url: Optional[str] = None
    output_filename: Optional[str] = None
    logs: List[str] = []
    reuse_keystore_from: Optional[str] = None  # 复用某个任务的签名密钥


class BuildTaskCreate(BaseModel):
    """创建构建任务的请求"""
    client_id: str  # 客户端ID
    quick_generate: bool = False
    mode: str = "convert"
    web_url: Optional[str] = None
    filename: Optional[str] = None
    html_filename: Optional[str] = None
    icon_filename: Optional[str] = None
    keystore_filename: Optional[str] = None
    config: AppConfig
    reuse_keystore_from: Optional[str] = None  # 复用某个任务的签名密钥


class BuildTaskResponse(BaseModel):
    """构建任务响应"""
    model_config = ConfigDict(from_attributes=True)
    id: str
    client_id: str = ""
    quick_generate: bool = False
    mode: str = "convert"
    web_url: Optional[str] = None
    filename: Optional[str] = None
    html_filename: Optional[str] = None
    icon_filename: Optional[str] = None
    keystore_filename: Optional[str] = None
    config: AppConfig
    status: BuildStatus
    created_at: datetime
    updated_at: datetime
    progress: int
    message: str
    download_url: Optional[str] = None
    output_filename: Optional[str] = None
    logs: List[str] = []
    reuse_keystore_from: Optional[str] = None


class UpdateTaskRequest(BaseModel):
    """更新任务请求"""
    client_id: str  # 客户端ID（用于验证所有权）
    filename: Optional[str] = None  # 新的ZIP文件名（可选）
    html_filename: Optional[str] = None  # 新的HTML文件名（可选）
    icon_filename: Optional[str] = None  # 新的图标文件名（可选）
    version_name: str
    version_code: int
    output_format: Optional[str] = None  # apk / aab（可选）
    # APK style overrides (optional)
    orientation: Optional[str] = None
    double_click_exit: Optional[bool] = None
    status_bar_hidden: Optional[bool] = None
    status_bar_style: Optional[str] = None  # light | dark
    status_bar_color: Optional[str] = None  # transparent | #FFFFFF
    webview_user_agent: Optional[str] = None  # android | pc (web mode)
    html_localize_resources: Optional[bool] = None  # true | false (html mode)
    download_mode: Optional[str] = None  # silent | picker (html mode)
    permissions: Optional[List[str]] = None
