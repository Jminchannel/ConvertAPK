import json
import os
import re
import ast
import urllib.error
import urllib.request
from datetime import datetime
from typing import Any


ANSI_ESCAPE_PATTERN = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")
WHITESPACE_PATTERN = re.compile(r"\s+")
JSON_OBJECT_PATTERN = re.compile(r"\{[\s\S]*\}")
MARKDOWN_JSON_FENCE_PATTERN = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)
TRAILING_COMMA_PATTERN = re.compile(r",(\s*[}\]])")
ERROR_HINT_PATTERN = re.compile(
    r"(error|exception|failed|failure|cannot|could not|denied|timed out|sdk|gradle|npm|node|keystore)",
    re.IGNORECASE,
)
DOCKER_INFRA_PATTERN = re.compile(
    r"(cannot connect to the docker daemon|failed to solve|oci runtime|overlay2|pull access denied|permission denied while trying to connect to the docker daemon|error from sender|no space left on device.*overlay|failed to create shim task)",
    re.IGNORECASE,
)
SOURCE_CODE_ERROR_PATTERN = re.compile(
    r"(\[vite:esbuild\]|transform failed with \d+ error|error during build|syntaxerror|parse error|illegal escape|unexpected closing .* tag does not match opening .* tag|unexpected token|\.((tsx)|(ts)|(jsx)|(js)|(vue)|(html)|(css)|(scss)|(kt)|(kts)|(java)|(xml)):\d+:\d+)",
    re.IGNORECASE,
)
TASK_PATH_PREFIX_PATTERN = re.compile(
    r"(?i)(?:[a-z]:)?[/\\]data[/\\]tasks[/\\][^/\\\s`\"']+[/\\]"
)
ABSOLUTE_PATH_PATTERN = re.compile(
    r"(?:[a-zA-Z]:[\\/][^\s`\"']+|/(?:data|app|root|tmp|var|workspace|home|usr|opt|mnt)(?:/[^\s`\"']+)*)"
)
LOG_PREFIX_PATTERN = re.compile(r"^\[[^\]]+\]\s*")
SOURCE_FILE_LOCATION_PATTERN = re.compile(
    r"(?P<path>(?:file://)?(?:[a-zA-Z]:)?[\\/][^:\s]+?\.(?:tsx|ts|jsx|js|vue|html|css|scss|kt|kts|java|xml)|(?:\./)?[^\s:]+?\.(?:tsx|ts|jsx|js|vue|html|css|scss|kt|kts|java|xml)):(?P<line>\d+):(?P<column>\d+)(?:(?::\s*(?:ERROR|error)\s*:|\s+)(?P<message>.+))?",
    re.IGNORECASE,
)
SOURCE_MESSAGE_HINT_PATTERN = re.compile(
    r"(syntaxerror|parse error|illegal escape|unexpected token|unexpected closing .* tag does not match opening .* tag|does not match opening|unterminated|missing)",
    re.IGNORECASE,
)
SOURCE_CODE_FRAME_PATTERN = re.compile(r"^\d+\|\s*")
SOURCE_POINTER_PATTERN = re.compile(r"^\|\s*\^")
TAG_MISMATCH_PATTERN = re.compile(
    r"unexpected closing \"?(?P<close>[a-zA-Z0-9_-]+)\"? tag does not match opening \"?(?P<open>[a-zA-Z0-9_-]+)\"? tag",
    re.IGNORECASE,
)

SUPPORTED_DIAG_LANGUAGES = {"zh-CN", "zh-TW", "en"}

DIAG_TEXTS: dict[str, dict[str, str]] = {
    "zh-CN": {
        "running_summary": "正在分析构建失败日志，请稍候。",
        "failed_summary": "日志诊断执行失败",
        "failed_retry": "请稍后重试，或手动查看日志中的首个 ERROR 位置。",
        "no_logs_summary": "没有可分析的失败日志。",
        "generic_error_title": "构建过程出现错误",
        "generic_error_category": "通用错误",
        "generic_error_reason": "日志中包含 ERROR/FAILED 关键字，建议按首个错误向上回溯定位。",
        "generic_error_suggestion_1": "先定位首个错误堆栈，再处理后续连锁报错。",
        "generic_error_suggestion_2": "确认依赖安装、SDK/JDK 路径与签名参数是否完整。",
        "generic_probable_cause": "日志出现通用错误关键字，需按首个错误定位。",
        "generic_suggestion_1": "优先处理第一个 ERROR/Exception，再重新构建验证。",
        "generic_suggestion_2": "若无法定位，请导出完整日志交给网站开发者复现。",
        "summary_with_hits": "检测到 {count} 个高相关错误线索，建议优先处理：{title}。",
        "source_user_title": "您的源码语法或结构错误",
        "source_user_category": "源码编译错误",
        "source_summary_with_location": "检测到您的源码语法关键错误：{location}。",
        "source_summary_without_location": "检测到您的源码语法关键错误，导致构建中断。",
        "source_reason_with_location": "您的源码语法在 {location} 触发编译错误：{message}",
        "source_reason_without_location": "日志出现明确的源码编译错误：{message}",
        "source_cause_with_location": "{location} 的源码报错：{message}",
        "source_cause_without_location": "您的源码语法存在编译错误：{message}",
        "source_suggestion_locate": "打开 {path}，定位到第 {line} 行附近，优先修复第一条报错。",
        "source_suggestion_locate_no_line": "打开 {path}，优先修复日志中的第一条源码报错。",
        "source_suggestion_check_pair": "重点检查该处标签、括号或引号是否成对闭合，并确认上下文结构合法。",
        "source_suggestion_rebuild": "修复后重新构建；若仍失败，请继续按日志中的第一条源码报错依次处理。",
        "source_suggestion_delegate": "若你暂时无法修改源码，可把这条报错和日志片段发给网站开发者协助处理。",
        "source_tag_fix_hint": "日志提示闭合标签不匹配，可优先检查是否应将 `</{closeTag}>` 改为 `</{openTag}>`。",
        "unknown_summary": "未命中已知规则，建议结合完整日志人工定位首个异常。",
        "unknown_reason": "暂无明确根因。",
        "unknown_suggestion_1": "优先查看日志首个异常堆栈，确认失败发生阶段。",
        "unknown_suggestion_2": "检查构建环境（Node/JDK/Android SDK）与签名参数是否完整。",
        "infra_summary": "检测到平台构建环境异常，更可能是网站服务端问题。",
        "infra_reason": "日志显示 Docker/构建容器异常，这类问题通常由网站构建环境引起，不是你上传包本身的问题。",
        "infra_cause": "网站的 Docker 构建环境异常（如镜像、容器、权限、磁盘或网络）导致任务失败。",
        "infra_error_title": "网站构建环境异常",
        "infra_error_category": "平台环境",
        "infra_suggestion_1": "你无需修改上传包，可稍后重试一次。",
        "infra_suggestion_2": "若仍失败，请联系网站开发者或管理员排查 Docker 构建环境。",
        "infra_suggestion_3": "可把任务 ID 与失败时间提供给网站开发者，便于快速定位。",
        "user_delegate_suggestion": "如果你不方便修改代码，可把本诊断和任务日志发给网站开发者协助处理。",
        "llm_fallback_cause": "智能模型暂时不可用，本次结果已自动回退为规则诊断。",
        "llm_fallback_suggestion": "若想获得更精准的智能诊断，请稍后点击“重新诊断”再试。",
        "llm_lang_name": "简体中文",
    },
    "zh-TW": {
        "running_summary": "正在分析建構失敗日誌，請稍候。",
        "failed_summary": "日誌診斷執行失敗",
        "failed_retry": "請稍後重試，或手動查看日誌中的首個 ERROR 位置。",
        "no_logs_summary": "沒有可分析的失敗日誌。",
        "generic_error_title": "建構過程出現錯誤",
        "generic_error_category": "通用錯誤",
        "generic_error_reason": "日誌中包含 ERROR/FAILED 關鍵字，建議按首個錯誤向上回溯定位。",
        "generic_error_suggestion_1": "先定位首個錯誤堆疊，再處理後續連鎖報錯。",
        "generic_error_suggestion_2": "確認依賴安裝、SDK/JDK 路徑與簽名參數是否完整。",
        "generic_probable_cause": "日誌出現通用錯誤關鍵字，需按首個錯誤定位。",
        "generic_suggestion_1": "優先處理第一個 ERROR/Exception，再重新建構驗證。",
        "generic_suggestion_2": "若無法定位，請匯出完整日誌交給網站開發者復現。",
        "summary_with_hits": "檢測到 {count} 個高相關錯誤線索，建議優先處理：{title}。",
        "source_user_title": "您的原始碼語法或結構錯誤",
        "source_user_category": "原始碼編譯錯誤",
        "source_summary_with_location": "檢測到您的原始碼語法關鍵錯誤：{location}。",
        "source_summary_without_location": "檢測到您的原始碼語法關鍵錯誤，導致建構中斷。",
        "source_reason_with_location": "您的原始碼語法在 {location} 觸發編譯錯誤：{message}",
        "source_reason_without_location": "日誌出現明確的原始碼編譯錯誤：{message}",
        "source_cause_with_location": "{location} 的原始碼報錯：{message}",
        "source_cause_without_location": "您的原始碼語法存在編譯錯誤：{message}",
        "source_suggestion_locate": "開啟 {path}，定位到第 {line} 行附近，優先修復第一條報錯。",
        "source_suggestion_locate_no_line": "開啟 {path}，優先修復日誌中的第一條原始碼報錯。",
        "source_suggestion_check_pair": "重點檢查該處標籤、括號或引號是否成對閉合，並確認上下文結構合法。",
        "source_suggestion_rebuild": "修復後重新建構；若仍失敗，請繼續按日誌中的第一條原始碼報錯依序處理。",
        "source_suggestion_delegate": "若你暫時無法修改原始碼，可把這條報錯和日誌片段發給網站開發者協助處理。",
        "source_tag_fix_hint": "日誌提示閉合標籤不匹配，可優先檢查是否應將 `</{closeTag}>` 改為 `</{openTag}>`。",
        "unknown_summary": "未命中已知規則，建議結合完整日誌人工定位首個異常。",
        "unknown_reason": "暫無明確根因。",
        "unknown_suggestion_1": "優先查看日誌首個異常堆疊，確認失敗發生階段。",
        "unknown_suggestion_2": "檢查建構環境（Node/JDK/Android SDK）與簽名參數是否完整。",
        "infra_summary": "檢測到平台建構環境異常，更可能是網站伺服器端問題。",
        "infra_reason": "日誌顯示 Docker/建構容器異常，這類問題通常由網站建構環境引起，不是你上傳包本身的問題。",
        "infra_cause": "網站的 Docker 建構環境異常（如鏡像、容器、權限、磁碟或網路）導致任務失敗。",
        "infra_error_title": "網站建構環境異常",
        "infra_error_category": "平台環境",
        "infra_suggestion_1": "你無需修改上傳包，可稍後重試一次。",
        "infra_suggestion_2": "若仍失敗，請聯繫網站開發者或管理員排查 Docker 建構環境。",
        "infra_suggestion_3": "可把任務 ID 與失敗時間提供給網站開發者，便於快速定位。",
        "user_delegate_suggestion": "如果你不方便修改程式碼，可把本診斷和任務日誌發給網站開發者協助處理。",
        "llm_fallback_cause": "智慧模型暫時不可用，本次結果已自動回退為規則診斷。",
        "llm_fallback_suggestion": "若想獲得更精準的智慧診斷，請稍後點擊「重新診斷」再試。",
        "llm_lang_name": "繁體中文",
    },
    "en": {
        "running_summary": "Analyzing failed build logs, please wait.",
        "failed_summary": "Diagnosis execution failed",
        "failed_retry": "Please retry later, or check the first ERROR in logs manually.",
        "no_logs_summary": "No failed logs available for diagnosis.",
        "generic_error_title": "Build process error detected",
        "generic_error_category": "Generic error",
        "generic_error_reason": "The logs contain ERROR/FAILED keywords. Start from the first error and trace upward.",
        "generic_error_suggestion_1": "Handle the first error stack first, then resolve follow-up cascading errors.",
        "generic_error_suggestion_2": "Verify dependency installation, SDK/JDK paths, and signing settings.",
        "generic_probable_cause": "Generic error keywords were found in logs. Root cause should be identified from the first error.",
        "generic_suggestion_1": "Fix the first ERROR/Exception first, then rebuild to verify.",
        "generic_suggestion_2": "If still unclear, export full logs and share them with the website developer.",
        "summary_with_hits": "Detected {count} highly related error clue(s). Recommended priority: {title}.",
        "source_user_title": "Your source code syntax/structure error",
        "source_user_category": "Source compilation error",
        "source_summary_with_location": "Detected a key error in your source code syntax: {location}.",
        "source_summary_without_location": "Detected a key syntax issue in your source code, and compilation was interrupted.",
        "source_reason_with_location": "Your source code syntax failed at {location}: {message}",
        "source_reason_without_location": "A clear source compilation error was found in logs: {message}",
        "source_cause_with_location": "Source error at {location}: {message}",
        "source_cause_without_location": "Your source code syntax caused compilation failure: {message}",
        "source_suggestion_locate": "Open {path}, go to around line {line}, and fix the first reported error first.",
        "source_suggestion_locate_no_line": "Open {path} and fix the first source error shown in logs.",
        "source_suggestion_check_pair": "Check whether tags, brackets, and quotes are properly paired and closed at that location.",
        "source_suggestion_rebuild": "Rebuild after fixing it. If it still fails, continue from the first source error in logs.",
        "source_suggestion_delegate": "If you cannot edit source code right now, share this error and log snippet with the website developer.",
        "source_tag_fix_hint": "Logs show a closing-tag mismatch. Check whether `</{closeTag}>` should be `</{openTag}>`.",
        "unknown_summary": "No known rule matched. Please inspect the full logs and locate the first exception manually.",
        "unknown_reason": "No clear root cause yet.",
        "unknown_suggestion_1": "Start from the first exception stack in logs and identify where the failure begins.",
        "unknown_suggestion_2": "Check build environment (Node/JDK/Android SDK) and signing settings.",
        "infra_summary": "Platform build environment issue detected, likely on the website server side.",
        "infra_reason": "The logs indicate Docker/build container errors. This is usually a platform environment issue, not caused by your uploaded package.",
        "infra_cause": "The website Docker build environment failed (image/container/permission/disk/network related).",
        "infra_error_title": "Website build environment issue",
        "infra_error_category": "Platform environment",
        "infra_suggestion_1": "You do not need to change your uploaded package. Try again later.",
        "infra_suggestion_2": "If it still fails, contact the website developer/admin to check Docker build environment.",
        "infra_suggestion_3": "Share task ID and failure time with the website developer for faster troubleshooting.",
        "user_delegate_suggestion": "If you are not comfortable modifying code, share this diagnosis and task logs with the website developer for help.",
        "llm_fallback_cause": "The smart model is temporarily unavailable, so this result has fallen back to rule-based diagnosis.",
        "llm_fallback_suggestion": "For a more precise AI diagnosis, please click \"Rerun\" and try again later.",
        "llm_lang_name": "English",
    },
}

RULE_I18N_EN: dict[str, dict[str, Any]] = {
    "source_syntax_error": {
        "title": "Your source code syntax/structure error",
        "reason": "The build log shows a concrete source syntax/structure error, so compilation stopped.",
        "suggestions": [
            "Open the reported source file and line, then fix the syntax/closing-tag mismatch shown by the error.",
            "Rebuild after saving the fix. If you cannot edit source code, send this diagnosis and log to the website developer.",
            "Use the first compile error as root cause; later errors are usually cascading effects.",
        ],
    },
    "docker_platform_issue": {
        "title": "Docker platform environment error",
        "reason": "The build container reported a Docker/platform environment error. This is usually server-side, not caused by your uploaded package.",
        "suggestions": [
            "You can retry later first.",
            "If it still fails, contact the website developer/admin to check Docker image/container/permission/disk/network status.",
            "Share task ID and failure time with the website developer for faster troubleshooting.",
        ],
    },
    "android_sdk_missing": {
        "title": "Android SDK missing or path invalid",
        "reason": "Build tools cannot find Android SDK, so Gradle tasks cannot run.",
        "suggestions": [
            "If you own this project source, ensure Android SDK is correctly configured in your build environment.",
            "If you only uploaded the package on this website, contact the website developer/admin to fix Android SDK setup.",
            "Retry after environment configuration is updated.",
        ],
    },
    "jdk_missing_or_invalid": {
        "title": "JDK unavailable or version mismatch",
        "reason": "Gradle requires a valid JDK, but current Java runtime is unavailable or incompatible.",
        "suggestions": [
            "If you own this project source, ensure JDK path/version matches project requirements.",
            "If you only uploaded the package on this website, contact the website developer/admin to fix JDK setup.",
            "Retry after Java environment is corrected.",
        ],
    },
    "gradle_wrapper_corrupted": {
        "title": "Gradle wrapper corrupted or download failed",
        "reason": "Gradle wrapper is corrupted, or distribution download failed due to network/certificate restrictions.",
        "suggestions": [
            "Retry once later to exclude transient network failure.",
            "If repeated, contact the website developer/admin to check Gradle cache, mirror source, and certificate/proxy settings.",
            "Provide failure time and task ID for faster troubleshooting.",
        ],
    },
    "npm_dependency_conflict": {
        "title": "NPM dependency conflict",
        "reason": "Dependency tree conflicts caused `npm install` or `npm run build` failure.",
        "suggestions": [
            "If you manage the project source, align dependency versions and lockfile first.",
            "If this project was uploaded by another teammate, ask the website developer/project maintainer to fix dependency conflicts.",
            "Rebuild after dependency conflicts are resolved.",
        ],
    },
    "network_or_dns_issue": {
        "title": "Network or DNS issue",
        "reason": "Dependency/resource download timed out or DNS resolution failed during build.",
        "suggestions": [
            "Retry once to exclude temporary network jitter.",
            "If persistent, contact the website developer/admin to check network, proxy, DNS, and mirror configuration.",
            "Provide task ID and approximate failure time for investigation.",
        ],
    },
    "keystore_or_signing_error": {
        "title": "Signing configuration error",
        "reason": "Keystore file, alias, or password does not match, causing signing phase failure.",
        "suggestions": [
            "Double-check keystore file, alias, keystore password, and key password.",
            "For app upgrade installs, keep using the same historical signing certificate.",
            "If credentials are managed by your team, contact the responsible developer to confirm signing config.",
        ],
    },
    "androidx_or_manifest_conflict": {
        "title": "AndroidManifest or dependency merge conflict",
        "reason": "Manifest merge failure or AndroidX/Support dependency conflict interrupted compilation.",
        "suggestions": [
            "If you manage source code, align dependency versions and remove duplicate declarations.",
            "If you only uploaded a package, contact the website developer/project maintainer for conflict resolution.",
            "Rebuild after dependency/manifest cleanup.",
        ],
    },
    "memory_exhausted": {
        "title": "Insufficient build memory",
        "reason": "Gradle or Node ran out of memory and the build process was terminated.",
        "suggestions": [
            "Retry when the build queue is lighter.",
            "If persistent, contact the website developer/admin to increase build memory or optimize build load.",
            "Share task ID and failure time to help confirm resource bottlenecks.",
        ],
    },
    "kotlin_jvm_target_unsupported": {
        "title": "Unsupported Kotlin JVM target",
        "reason": "The project sets Kotlin jvmTarget to 21, but the Kotlin Gradle plugin in the build chain does not support that target.",
        "suggestions": [
            "Change Kotlin `jvmTarget` from `21` to `17` in the Gradle file, or upgrade the Kotlin Gradle plugin to a version that supports JVM 21.",
            "If the app does not require Java 21 language features, prefer JVM 17 for better Android build compatibility.",
            "Rebuild after updating the Gradle configuration.",
        ],
    },
    "androidx_not_enabled": {
        "title": "AndroidX is not enabled",
        "reason": "The project uses AndroidX dependencies, but Gradle properties do not enable AndroidX mode.",
        "suggestions": [
            "Add `android.useAndroidX=true` to the root `gradle.properties` file.",
            "If the project mixes old support libraries with AndroidX, also consider `android.enableJetifier=true`.",
            "Rebuild after saving `gradle.properties`.",
        ],
    },
    "gradle_groovy_space_assignment_incompatible": {
        "title": "Gradle Groovy DSL syntax is incompatible",
        "reason": "The build log shows old Groovy space-assignment syntax in `build.gradle`; newer Gradle expects `propName = value`.",
        "suggestions": [
            "Open the reported `build.gradle` line and change examples like `compileSdk 36` to `compileSdk = 36`.",
            "Apply the same style to `namespace`, `minSdk`, `targetSdk`, `abortOnError`, and `useLegacyPackaging`.",
            "This is a Gradle DSL compatibility issue, not business source-code logic.",
        ],
    },
    "gradle_agp_wrapper_version_mismatch": {
        "title": "Gradle and Android Gradle Plugin versions do not match",
        "reason": "The build log shows a Gradle wrapper and Android Gradle Plugin version-matrix mismatch.",
        "suggestions": [
            "Adjust `gradle/wrapper/gradle-wrapper.properties` or `com.android.tools.build:gradle` according to the log.",
            "Keep Gradle, AGP, JDK, and Kotlin plugin versions aligned instead of upgrading only one of them.",
            "The platform reports this high-risk version conflict but does not automatically rewrite plugin versions.",
        ],
    },
    "kotlin_gradle_plugin_version_conflict": {
        "title": "Kotlin/AGP plugin version conflict",
        "reason": "The log indicates Kotlin Gradle Plugin is incompatible with AGP, KSP, Compose, or dependency metadata versions.",
        "suggestions": [
            "Align Kotlin Gradle Plugin, KSP, Compose Compiler, and AGP versions using the project's original documentation or official version matrix.",
            "For older projects, prefer their original wrapper/plugin versions; for newer projects, upgrade the Android build chain together.",
            "The platform only diagnoses this high-risk version-matrix issue and does not auto-change dependency versions.",
        ],
    },
    "android_signing_env_missing": {
        "title": "Android signing environment variables are missing",
        "reason": "The project signing script resolved the keystore path to null before Gradle could configure the release build.",
        "suggestions": [
            "If the project uses `RELEASE_STORE_FILE`, `RELEASE_STORE_PASSWORD`, `RELEASE_KEY_ALIAS`, or `RELEASE_KEY_PASSWORD`, make sure they are provided by the build environment.",
            "If you maintain the source, add a null check before `rootProject.file(...)` and fail with a clear signing message.",
            "Rebuild after signing variables are provided or the signing script is made null-safe.",
        ],
    },
    "kotlin_illegal_escape_regex": {
        "title": "Kotlin regular expression escape error",
        "reason": "A Kotlin string contains an unescaped regular-expression backslash, so compilation stopped.",
        "suggestions": [
            "For whitespace regex, use `Regex(\"\\\\s+\")` in a normal Kotlin string, or `Regex(\"\"\"\\s+\"\"\")` as a raw string.",
            "Open the file and line shown in the log, fix the first `Illegal escape` error, then rebuild.",
            "Later Kotlin errors may be cascading effects; start from the first reported file and line.",
        ],
    },
    "legacy_node_sass_node22": {
        "title": "Legacy front-end dependencies are incompatible with current Node",
        "reason": "The project uses legacy dependencies such as node-sass/Vue CLI 4, which often fail under the builder's current Node/npm runtime.",
        "suggestions": [
            "If a ready `dist` directory is included, upload/build it as a static HTML package.",
            "Otherwise replace `node-sass` with `sass`, upgrade old Vue CLI dependencies, or build the front end with its historical Node version before uploading.",
            "Keep only one lock file when possible, so the builder does not drift between npm/yarn dependency trees.",
        ],
    },
    "android_manifest_missing_during_build": {
        "title": "Android manifest disappeared during build",
        "reason": "Gradle cannot find `app/src/main/AndroidManifest.xml`; the source package may be incomplete, or the task working directory was deleted while building.",
        "suggestions": [
            "If this is your source package, confirm it contains `settings.gradle`, the `app` module, and `app/src/main/AndroidManifest.xml`.",
            "If the task was deleted/canceled while building, create a new task and wait for it to finish before deleting it.",
            "Ask the website developer to preserve task files while a build is still running.",
        ],
    },
}


def _normalize_diag_language(value: str | None) -> str:
    raw = str(value or "").strip()
    lower = raw.lower()
    if lower in {"zh-cn", "zh_cn", "zh-hans"}:
        return "zh-CN"
    if lower in {"zh-tw", "zh_tw", "zh-hk", "zh-mo", "zh-hant"}:
        return "zh-TW"
    if lower.startswith("en"):
        return "en"
    if raw in SUPPORTED_DIAG_LANGUAGES:
        return raw
    return "zh-CN"


def normalize_diag_language(value: str | None) -> str:
    return _normalize_diag_language(value)


def _diag_text(language: str, key: str, **kwargs: Any) -> str:
    lang = _normalize_diag_language(language)
    base = DIAG_TEXTS.get(lang) or DIAG_TEXTS["zh-CN"]
    text = str(base.get(key) or DIAG_TEXTS["zh-CN"].get(key) or "")
    if kwargs:
        try:
            return text.format(**kwargs)
        except Exception:
            return text
    return text


def _localize_rule_fields(rule: dict[str, Any], language: str) -> tuple[str, str, list[str]]:
    lang = _normalize_diag_language(language)
    title = str(rule.get("title") or "").strip()
    reason = str(rule.get("reason") or "").strip()
    suggestions = [str(item).strip() for item in list(rule.get("suggestions") or []) if str(item).strip()]
    if lang != "en":
        return title, reason, suggestions
    mapped = RULE_I18N_EN.get(str(rule.get("id") or "").strip(), {})
    mapped_title = str(mapped.get("title") or "").strip() or title
    mapped_reason = str(mapped.get("reason") or "").strip() or reason
    mapped_suggestions = [
        str(item).strip() for item in list(mapped.get("suggestions") or []) if str(item).strip()
    ] or suggestions
    return mapped_title, mapped_reason, mapped_suggestions


def _to_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


OPENROUTER_DIAG_ENABLED = _to_bool(os.getenv("OPENROUTER_DIAG_ENABLED"), default=True)
OPENROUTER_API_URL = str(
    os.getenv("OPENROUTER_API_URL") or "https://openrouter.ai/api/v1/chat/completions"
).strip()
OPENROUTER_MODEL = str(
    os.getenv("OPENROUTER_DIAG_MODEL")
    or os.getenv("OPENROUTER_MODEL")
    or "openrouter/elephant-alpha"
).strip()
OPENROUTER_TIMEOUT_SECONDS = 20
try:
    OPENROUTER_TIMEOUT_SECONDS = max(
        int(os.getenv("OPENROUTER_DIAG_TIMEOUT_SECONDS", "20") or "20"),
        8,
    )
except ValueError:
    OPENROUTER_TIMEOUT_SECONDS = 20

MAX_ANALYZE_LOG_LINES = 240
try:
    MAX_ANALYZE_LOG_LINES = max(
        int(os.getenv("BUILD_DIAG_MAX_LOG_LINES", "240") or "240"),
        80,
    )
except ValueError:
    MAX_ANALYZE_LOG_LINES = 240


def _normalize_timeout_seconds(value: Any, default_value: int) -> int:
    try:
        parsed = int(value)
    except Exception:
        return default_value
    return max(8, min(parsed, 120))


def _normalize_openrouter_api_url(value: str | None) -> str:
    api_url = str(value or "").strip()
    if not api_url:
        return str(OPENROUTER_API_URL or "").strip()
    normalized = api_url.rstrip("/")
    if normalized.lower() == "https://openrouter.ai/api/v1":
        return f"{normalized}/chat/completions"
    return api_url


def resolve_openrouter_diag_runtime_config(ai_config: dict[str, Any] | None = None) -> dict[str, Any]:
    config = ai_config if isinstance(ai_config, dict) else {}
    enabled = _to_bool(config.get("enabled"), default=OPENROUTER_DIAG_ENABLED)
    provider = str(config.get("provider") or "openrouter").strip().lower() or "openrouter"
    api_url = _normalize_openrouter_api_url(config.get("api_url") or OPENROUTER_API_URL)
    api_key = str(config.get("api_key") or os.getenv("OPENROUTER_API_KEY") or "").strip()
    model = str(config.get("model") or OPENROUTER_MODEL).strip()
    timeout_seconds = _normalize_timeout_seconds(config.get("timeout_seconds"), OPENROUTER_TIMEOUT_SECONDS)
    site_url = str(config.get("site_url") or os.getenv("OPENROUTER_SITE_URL") or "").strip()
    app_name = str(config.get("app_name") or os.getenv("OPENROUTER_APP_NAME") or "ConvertAPK-EXE").strip()
    return {
        "enabled": enabled,
        "provider": provider,
        "api_url": api_url,
        "api_key": api_key,
        "model": model,
        "timeout_seconds": timeout_seconds,
        "site_url": site_url,
        "app_name": app_name,
    }


KNOWLEDGE_RULES = [
    {
        "id": "kotlin_illegal_escape_regex",
        "title": "Kotlin 正则转义写法错误",
        "category": "源码编译错误",
        "severity": "high",
        "reason": "日志显示 Kotlin 源码中存在未转义的正则反斜杠，编译器在该文件行列直接中断。",
        "patterns": [
            r"Illegal escape",
            r"\.kt:\d+:\d+.*Illegal escape",
        ],
        "suggestions": [
            "打开日志中的 Kotlin 文件和行号，把普通字符串写成 `Regex(\"\\\\s+\")`，或改用 Kotlin 原始字符串 `Regex(\"\"\"\\s+\"\"\")`。",
            "优先修复第一条 `Illegal escape` 报错，后续 Kotlin 报错多数是连锁影响。",
            "修复源码后重新上传构建。",
        ],
        "confidence": 0.96,
    },
    {
        "id": "kotlin_jvm_target_unsupported",
        "title": "Kotlin JVM 目标版本不受支持",
        "category": "Android 配置",
        "severity": "high",
        "reason": "日志显示 `Unknown Kotlin JVM target: 21`，说明项目把 Kotlin `jvmTarget` 配成了 21，但当前 Kotlin Gradle 插件不支持该目标。",
        "patterns": [
            r"Unknown Kotlin JVM target:\s*21",
        ],
        "suggestions": [
            "在 `build.gradle` 或 `build.gradle.kts` 中把 Kotlin `jvmTarget` 从 `21` 改为 `17`。",
            "如果源码确实依赖 Java 21 特性，则需要同步升级 Kotlin Gradle Plugin 到支持 JVM 21 的版本。",
            "Android 项目通常优先使用 JVM 17，兼容性更稳。",
        ],
        "confidence": 0.96,
    },
    {
        "id": "androidx_not_enabled",
        "title": "AndroidX 依赖未启用",
        "category": "Android 配置",
        "severity": "high",
        "reason": "日志显示项目包含 AndroidX 依赖，但根目录 `gradle.properties` 没有启用 `android.useAndroidX=true`。",
        "patterns": [
            r"android\.useAndroidX",
            r"contains AndroidX dependencies",
            r"AndroidX dependencies",
        ],
        "suggestions": [
            "在原生 Android 工程根目录 `gradle.properties` 中添加 `android.useAndroidX=true`。",
            "如果项目同时混用了旧 support 包，可再添加 `android.enableJetifier=true` 后重试。",
            "这是项目配置缺失，不需要修改业务代码。",
        ],
        "confidence": 0.95,
    },
    {
        "id": "gradle_groovy_space_assignment_incompatible",
        "title": "Gradle Groovy DSL 写法不兼容",
        "category": "Android 配置",
        "severity": "high",
        "reason": "日志显示 `build.gradle` 使用了旧的 Groovy 空格赋值写法，新版 Gradle 要求改成 `propName = value`。",
        "patterns": [
            r"Properties should be assigned using the 'propName = value' syntax",
            r"Gradle-generated 'propName value'",
            r"groovy_space_assignment_syntax",
            r"Use assignment \('[^']+ = <value>'\)",
        ],
        "suggestions": [
            "打开日志指向的 `build.gradle` 行号，把 `compileSdk 36` 改为 `compileSdk = 36`，`namespace '包名'` 改为 `namespace = '包名'`。",
            "同类写法也需要改成等号赋值，例如 `minSdk = 23`、`targetSdk = 36`、`abortOnError = false`、`useLegacyPackaging = true`。",
            "这是 Gradle DSL 兼容问题，不是业务代码逻辑错误；修完第一批 DSL 行后再重新构建。",
        ],
        "confidence": 0.96,
    },
    {
        "id": "gradle_agp_wrapper_version_mismatch",
        "title": "Gradle 与 Android Gradle Plugin 版本不匹配",
        "category": "Android 配置",
        "severity": "high",
        "reason": "日志显示 Android Gradle Plugin 与当前 Gradle wrapper 大版本不匹配，这类版本矩阵冲突需要按项目实际依赖调整。",
        "patterns": [
            r"Minimum supported Gradle version is",
            r"The current Gradle version is",
            r"This version of the Android Gradle plugin requires Gradle",
            r"Android Gradle plugin requires Java",
        ],
        "suggestions": [
            "按日志提示修改 `gradle/wrapper/gradle-wrapper.properties` 中的 Gradle 版本，或同步调整 `com.android.tools.build:gradle` 版本。",
            "不要只单独升级 Gradle 或 AGP；Gradle、AGP、JDK、Kotlin 插件需要一起匹配。",
            "平台不会自动强改这类大版本依赖矩阵，避免把项目改到另一个不可控状态。",
        ],
        "confidence": 0.94,
    },
    {
        "id": "kotlin_gradle_plugin_version_conflict",
        "title": "Kotlin/AGP 插件版本冲突",
        "category": "Android 配置",
        "severity": "high",
        "reason": "日志显示 Kotlin Gradle Plugin 与 AGP、KSP、Compose 或依赖元数据版本不兼容。",
        "patterns": [
            r"Kotlin Gradle plugin.*incompatible",
            r"Android Gradle plugin supports only Kotlin",
            r"No matching variant.*org\.jetbrains\.kotlin",
            r"The binary version of its metadata is",
            r"Module was compiled with an incompatible version of Kotlin",
        ],
        "suggestions": [
            "统一 Kotlin Gradle Plugin、KSP、Compose Compiler 和 AGP 的版本，优先参考项目原始 README 或官方版本矩阵。",
            "如果项目依赖较老，请优先使用项目原本的 wrapper 和插件版本；如果项目很新，则同步升级整套 Android 构建链。",
            "这类问题属于高风险版本矩阵冲突，平台只给出诊断，不自动修改依赖版本。",
        ],
        "confidence": 0.93,
    },
    {
        "id": "android_signing_env_missing",
        "title": "Android 签名环境变量缺失",
        "category": "签名问题",
        "severity": "high",
        "reason": "日志显示项目签名脚本拿到的 keystore 路径为空，Gradle 在配置 release 签名时中断。",
        "patterns": [
            r"path may not be null or empty string",
            r"path='null'",
            r"rootProject\.file\(.*null",
        ],
        "suggestions": [
            "如果项目使用 `RELEASE_STORE_FILE`、`RELEASE_STORE_PASSWORD`、`RELEASE_KEY_ALIAS`、`RELEASE_KEY_PASSWORD`，请确认构建环境已传入这些变量。",
            "如果你维护源码，建议在 `rootProject.file(...)` 前先判断变量是否为空，避免 Gradle 只报 `path='null'`。",
            "确认签名变量或签名脚本后重新构建。",
        ],
        "confidence": 0.94,
    },
    {
        "id": "legacy_node_sass_node22",
        "title": "旧版前端依赖不兼容当前 Node 环境",
        "category": "前端依赖",
        "severity": "medium",
        "reason": "日志显示 npm 安装异常，且项目可能包含 node-sass、Vue CLI 4 或旧锁文件；这类旧项目在当前 Node/npm 环境下容易安装失败。",
        "patterns": [
            r"Exit handler never called",
            r"node-sass",
            r"@vue/cli-service",
        ],
        "suggestions": [
            "如果压缩包里已经有 `dist/index.html`，优先把 `dist` 作为静态站点上传，避免在服务器重装旧依赖。",
            "如果必须源码构建，请把 `node-sass` 替换为 `sass`，或使用项目历史 Node 版本在本地构建后再上传产物。",
            "尽量只保留一种锁文件（如 package-lock 或 yarn.lock），避免构建器在 npm/yarn 之间漂移。",
        ],
        "confidence": 0.9,
    },
    {
        "id": "android_manifest_missing_during_build",
        "title": "AndroidManifest 在构建时缺失",
        "category": "任务文件",
        "severity": "high",
        "reason": "Gradle 报告找不到 `app/src/main/AndroidManifest.xml`，可能是源码包不完整，也可能是任务构建中被删除导致工作目录消失。",
        "patterns": [
            r"AndroidManifest\.xml.*doesn.?t exist",
            r"Source file .*AndroidManifest\.xml.*does not exist",
            r"main manifest.*doesn.?t exist",
        ],
        "suggestions": [
            "若是源码问题，请确认 ZIP 内包含完整 `app` 模块和 `app/src/main/AndroidManifest.xml`。",
            "若用户在构建中删除了任务，请重新创建任务并等待构建结束后再删除。",
            "平台侧应禁止删除排队中或构建中的任务，避免工作目录被清理。",
        ],
        "confidence": 0.92,
    },
    {
        "id": "source_syntax_error",
        "title": "您的源码语法或结构错误",
        "category": "源码编译错误",
        "severity": "high",
        "reason": "日志中出现明确的源码编译错误（包含文件路径与行列号），说明您的源码语法是本次失败的直接原因。",
        "patterns": [
            r"\[vite:esbuild\]",
            r"Transform failed with \d+ error",
            r"error during build",
            r"Illegal escape",
            r"Unexpected closing .* tag does not match opening .* tag",
            r"SyntaxError",
            r"Parse error",
            r"\.(tsx|ts|jsx|js|vue|html|css|scss|kt|kts|java|xml):\d+:\d+",
        ],
        "suggestions": [
            "优先修复日志里第一条您的源码报错（文件 + 行列），再重新构建。",
            "本例可先检查标签是否闭合匹配（如 <label>...</label>）。",
            "若你无法修改源码，请把该错误片段转给网站开发者处理。",
        ],
        "confidence": 0.95,
    },
    {
        "id": "docker_platform_issue",
        "title": "Docker 平台构建环境异常",
        "category": "平台环境",
        "severity": "high",
        "reason": "构建容器出现 Docker/平台环境错误，更可能是网站服务端环境问题，而非你上传包的问题。",
        "patterns": [
            r"failed to solve",
            r"cannot connect to the docker daemon",
            r"overlay2",
            r"OCI runtime",
            r"pull access denied",
            r"no space left on device",
            r"permission denied while trying to connect to the docker daemon",
            r"error from sender: failed to",
        ],
        "suggestions": [
            "你无需修改上传包，可稍后重试一次。",
            "若持续失败，请联系网站开发者或管理员排查 Docker 镜像、容器权限、磁盘和网络配置。",
            "把任务 ID 与失败时间提供给网站开发者，便于快速定位。",
        ],
        "confidence": 0.93,
    },
    {
        "id": "android_sdk_missing",
        "title": "Android SDK 未安装或路径错误",
        "category": "环境配置",
        "severity": "high",
        "reason": "构建工具无法找到 Android SDK，导致 Gradle 任务无法执行。",
        "patterns": [
            r"ANDROID_HOME",
            r"ANDROID_SDK_ROOT",
            r"SDK location not found",
            r"failed to find target with hash string",
            r"No installed build tools found",
        ],
        "suggestions": [
            "在客户端环境设置中补全 Android SDK 路径，并确保该目录存在。",
            "确认本机已安装对应的 Build-Tools 与 Platform 版本。",
            "重启客户端后重新构建，避免环境变量未生效。",
        ],
        "confidence": 0.9,
    },
    {
        "id": "jdk_missing_or_invalid",
        "title": "JDK 不可用或版本不匹配",
        "category": "环境配置",
        "severity": "high",
        "reason": "Gradle 需要可用的 JDK，但当前 Java 运行环境不可用或版本不兼容。",
        "patterns": [
            r"JAVA_HOME",
            r"Unable to locate a Java Runtime",
            r"Could not find java",
            r"Unsupported class file major version",
            r"invalid source release",
        ],
        "suggestions": [
            "在环境设置中指定有效的 JDK 路径（建议与项目要求版本一致）。",
            "确保 PATH/JavaHome 没有指向已卸载或错误版本的 JDK。",
            "使用命令行执行 `java -version` 与 `javac -version` 校验实际版本。",
        ],
        "confidence": 0.88,
    },
    {
        "id": "gradle_wrapper_corrupted",
        "title": "Gradle Wrapper 损坏或下载失败",
        "category": "构建工具",
        "severity": "high",
        "reason": "Gradle Wrapper 文件损坏，或首次下载分发包时网络失败。",
        "patterns": [
            r"Could not install Gradle distribution",
            r"gradle-wrapper\.jar",
            r"Could not load wrapper properties",
            r"Connection timed out.*gradle",
            r"PKIX path building failed",
        ],
        "suggestions": [
            "清理本地 Gradle 缓存后重试，必要时重新下载 wrapper。",
            "检查网络代理、证书或公司内网策略是否拦截 Gradle 下载。",
            "在构建环境中配置可用镜像源以提高成功率。",
        ],
        "confidence": 0.84,
    },
    {
        "id": "npm_dependency_conflict",
        "title": "NPM 依赖冲突",
        "category": "前端依赖",
        "severity": "medium",
        "reason": "前端依赖树冲突导致 `npm install` 或 `npm run build` 失败。",
        "patterns": [
            r"ERESOLVE",
            r"peer dep",
            r"npm ERR!",
            r"Cannot find module",
            r"Module not found",
            r"vite build failed",
        ],
        "suggestions": [
            "在本地先执行依赖安装并修复冲突后再上传项目 ZIP。",
            "锁定依赖版本并提交 `package-lock.json`，减少环境漂移。",
            "若是插件版本冲突，优先统一到同一主版本。",
        ],
        "confidence": 0.8,
    },
    {
        "id": "network_or_dns_issue",
        "title": "网络或 DNS 问题",
        "category": "网络问题",
        "severity": "medium",
        "reason": "依赖下载或远程资源请求超时/解析失败，导致构建中断。",
        "patterns": [
            r"ETIMEDOUT",
            r"ECONNRESET",
            r"EAI_AGAIN",
            r"getaddrinfo",
            r"timed out",
            r"Could not resolve host",
        ],
        "suggestions": [
            "检查网络连通性、代理配置与 DNS 解析。",
            "尝试切换 npm/gradle 镜像源后重新构建。",
            "网络不稳定时可重试构建并观察是否稳定复现。",
        ],
        "confidence": 0.78,
    },
    {
        "id": "keystore_or_signing_error",
        "title": "签名配置错误",
        "category": "签名问题",
        "severity": "high",
        "reason": "keystore 文件、别名或密码不匹配，导致签名阶段失败。",
        "patterns": [
            r"Keystore was tampered with",
            r"keystore password was incorrect",
            r"Alias .* does not exist",
            r"Failed to read key",
            r"apksigner.*failed",
            r"jarsigner.*failed",
        ],
        "suggestions": [
            "确认 keystore、别名、keystore 密码和 key 密码完全匹配。",
            "升级安装场景请复用历史签名，不要混用不同证书。",
            "若证书文件损坏，请更换正确备份并重试。",
        ],
        "confidence": 0.92,
    },
    {
        "id": "androidx_or_manifest_conflict",
        "title": "AndroidManifest 或依赖合并冲突",
        "category": "Android 配置",
        "severity": "medium",
        "reason": "Manifest 合并失败或 AndroidX/Support 依赖冲突导致编译中断。",
        "patterns": [
            r"Manifest merger failed",
            r"uses-sdk:minSdkVersion",
            r"Duplicate class",
            r"Program type already present",
            r"AndroidX",
        ],
        "suggestions": [
            "根据报错定位冲突依赖，统一依赖版本并移除重复项。",
            "检查 AndroidManifest 配置是否被上游模板和插件重复声明。",
            "必要时在项目中显式约束依赖版本后再打包。",
        ],
        "confidence": 0.82,
    },
    {
        "id": "memory_exhausted",
        "title": "构建内存不足",
        "category": "资源限制",
        "severity": "medium",
        "reason": "Gradle 或 Node 构建阶段内存不足，进程被中断。",
        "patterns": [
            r"Java heap space",
            r"GC overhead limit exceeded",
            r"OutOfMemoryError",
            r"Allocation failed - JavaScript heap out of memory",
        ],
        "suggestions": [
            "提高 Gradle/Node 可用内存，或减少并行构建负载。",
            "关闭不必要后台程序，释放系统内存后重试。",
            "排查是否存在超大资源或异常打包流程。",
        ],
        "confidence": 0.86,
    },
]


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def create_idle_diagnosis(language: str = "zh-CN") -> dict[str, Any]:
    normalized_language = _normalize_diag_language(language)
    return {
        "status": "idle",
        "provider": "",
        "model": "",
        "language": normalized_language,
        "summary": "",
        "reason": "",
        "probable_causes": [],
        "suggestions": [],
        "knowledge_hits": [],
        "structured_errors": [],
        "analyzed_log_lines": 0,
        "confidence": 0.0,
        "error": "",
        "updated_at": "",
    }


def create_running_diagnosis(
    provider: str,
    model: str,
    analyzed_log_lines: int,
    language: str = "zh-CN",
) -> dict[str, Any]:
    normalized_language = _normalize_diag_language(language)
    return {
        "status": "running",
        "provider": provider,
        "model": model,
        "language": normalized_language,
        "summary": _diag_text(normalized_language, "running_summary"),
        "reason": "",
        "probable_causes": [],
        "suggestions": [],
        "knowledge_hits": [],
        "structured_errors": [],
        "analyzed_log_lines": max(int(analyzed_log_lines or 0), 0),
        "confidence": 0.0,
        "error": "",
        "updated_at": _now_iso(),
    }


def create_failed_diagnosis(
    message: str,
    analyzed_log_lines: int = 0,
    language: str = "zh-CN",
) -> dict[str, Any]:
    normalized_language = _normalize_diag_language(language)
    return {
        "status": "failed",
        "provider": "rule",
        "model": "",
        "language": normalized_language,
        "summary": _diag_text(normalized_language, "failed_summary"),
        "reason": str(message or "unknown error"),
        "probable_causes": [],
        "suggestions": [_diag_text(normalized_language, "failed_retry")],
        "knowledge_hits": [],
        "structured_errors": [],
        "analyzed_log_lines": max(int(analyzed_log_lines or 0), 0),
        "confidence": 0.0,
        "error": str(message or "unknown error"),
        "updated_at": _now_iso(),
    }


def _normalize_line(line: str) -> str:
    text = str(line or "")
    text = ANSI_ESCAPE_PATTERN.sub("", text)
    text = text.replace("\r", " ").replace("\n", " ")
    text = WHITESPACE_PATTERN.sub(" ", text).strip()
    return text


def normalize_log_lines(log_lines: list[str] | None, max_lines: int = MAX_ANALYZE_LOG_LINES) -> list[str]:
    if not isinstance(log_lines, list):
        return []
    normalized = []
    for item in log_lines:
        line = _normalize_line(item)
        if not line:
            continue
        normalized.append(line)
    if len(normalized) > max_lines:
        return normalized[-max_lines:]
    return normalized


def _merge_unique_text(values: list[str], max_items: int = 8) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for item in values:
        normalized = str(item or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        merged.append(normalized)
        if len(merged) >= max_items:
            break
    return merged


def _collect_rule_matches(lines: list[str], language: str = "zh-CN") -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    if not lines:
        return matches

    for rule in KNOWLEDGE_RULES:
        localized_title, localized_reason, localized_suggestions = _localize_rule_fields(rule, language)
        evidence: list[str] = []
        for line in lines:
            matched = False
            for raw_pattern in rule.get("patterns", []):
                if re.search(raw_pattern, line, re.IGNORECASE):
                    matched = True
                    break
            if not matched:
                continue
            evidence.append(line)
            if len(evidence) >= 3:
                break
        if not evidence:
            continue
        matches.append(
            {
                "rule_id": rule["id"],
                "title": localized_title,
                "category": rule["category"],
                "severity": rule["severity"],
                "reason": localized_reason,
                "suggestions": localized_suggestions,
                "evidence": evidence,
                "confidence": float(rule.get("confidence", 0.7)),
            }
        )
    return matches


def _extract_generic_error_evidence(lines: list[str]) -> list[str]:
    evidence: list[str] = []
    for line in lines:
        if not ERROR_HINT_PATTERN.search(line):
            continue
        evidence.append(line)
        if len(evidence) >= 6:
            break
    return evidence


def _strip_log_prefix(line: str) -> str:
    return LOG_PREFIX_PATTERN.sub("", str(line or "").strip())


def _find_nearby_source_message(lines: list[str], start_index: int) -> str:
    for offset in range(0, 8):
        index = start_index + offset
        if index < 0 or index >= len(lines):
            break
        text = _strip_log_prefix(lines[index])
        if not text:
            continue
        if SOURCE_FILE_LOCATION_PATTERN.search(text):
            continue
        if text.lower().startswith("file:"):
            continue
        if SOURCE_MESSAGE_HINT_PATTERN.search(text):
            return text
    return ""


def _collect_source_code_frame(lines: list[str], start_index: int, max_items: int = 4) -> list[str]:
    snippets: list[str] = []
    collecting = False
    for index in range(start_index + 1, min(len(lines), start_index + 12)):
        text = _strip_log_prefix(lines[index])
        if SOURCE_CODE_FRAME_PATTERN.match(text) or SOURCE_POINTER_PATTERN.match(text):
            collecting = True
            snippets.append(text)
            if len(snippets) >= max_items:
                break
            continue
        if collecting:
            break
    return snippets


def _extract_source_error_detail(lines: list[str]) -> dict[str, Any] | None:
    if not lines:
        return None
    fallback_detail: dict[str, Any] | None = None
    for index, raw_line in enumerate(lines):
        line = _strip_log_prefix(raw_line)
        if not line:
            continue
        for match in SOURCE_FILE_LOCATION_PATTERN.finditer(line):
            source_path = _sanitize_path_reference_token(str(match.group("path") or "").strip())
            if not source_path:
                continue
            try:
                source_line = int(match.group("line") or "0")
            except Exception:
                source_line = 0
            try:
                source_column = int(match.group("column") or "0")
            except Exception:
                source_column = 0
            message = str(match.group("message") or "").strip()
            if not message:
                message = _find_nearby_source_message(lines, index)
            evidence = _merge_unique_text(
                [line, message] + _collect_source_code_frame(lines, index),
                max_items=4,
            )
            detail = {
                "path": source_path,
                "line": max(source_line, 0),
                "column": max(source_column, 0),
                "message": message,
                "evidence": evidence,
            }
            lower_path = source_path.lower()
            if "node_modules/" in lower_path or "node_modules\\" in lower_path:
                if fallback_detail is None:
                    fallback_detail = detail
                continue
            return detail
    return fallback_detail


def _format_source_location(path: str, line: int, column: int, language: str) -> str:
    normalized_path = str(path or "").strip()
    if not normalized_path:
        return ""
    if line > 0 and column > 0:
        if language == "en":
            return f"{normalized_path}:{line}:{column}"
        return f"{normalized_path} 第 {line} 行第 {column} 列"
    if line > 0:
        if language == "en":
            return f"{normalized_path}:{line}"
        return f"{normalized_path} 第 {line} 行"
    return normalized_path


def _build_source_syntax_details(source_detail: dict[str, Any], language: str) -> dict[str, Any]:
    normalized_language = _normalize_diag_language(language)
    path = str(source_detail.get("path") or "").strip()
    try:
        source_line = int(source_detail.get("line") or 0)
    except Exception:
        source_line = 0
    try:
        source_column = int(source_detail.get("column") or 0)
    except Exception:
        source_column = 0
    message = str(source_detail.get("message") or "").strip()
    if not message:
        if normalized_language == "en":
            message = "Compilation was interrupted due to your source code syntax."
        elif normalized_language == "zh-TW":
            message = "建構因您的原始碼語法錯誤而中斷。"
        else:
            message = "构建因您的源码语法错误而中断。"

    location = _format_source_location(path, source_line, source_column, normalized_language)
    has_location = bool(location)
    if has_location:
        summary = _diag_text(normalized_language, "source_summary_with_location", location=location)
        reason = _diag_text(normalized_language, "source_reason_with_location", location=location, message=message)
        probable_cause = _diag_text(normalized_language, "source_cause_with_location", location=location, message=message)
    else:
        summary = _diag_text(normalized_language, "source_summary_without_location")
        reason = _diag_text(normalized_language, "source_reason_without_location", message=message)
        probable_cause = _diag_text(normalized_language, "source_cause_without_location", message=message)

    suggestions: list[str] = []
    if path and source_line > 0:
        suggestions.append(_diag_text(normalized_language, "source_suggestion_locate", path=path, line=source_line))
    elif path:
        suggestions.append(_diag_text(normalized_language, "source_suggestion_locate_no_line", path=path))
    if re.search(r"Illegal escape:\s*['\"]?\\s", message, re.IGNORECASE):
        if normalized_language == "en":
            suggestions.append(
                "For Kotlin whitespace regex, use `Regex(\"\\\\s+\")` in a normal string, or `Regex(\"\"\"\\s+\"\"\")` as a raw string."
            )
        else:
            suggestions.append(
                "这类 Kotlin 报错通常是正则反斜杠没有转义：普通字符串请写成 `Regex(\"\\\\s+\")`，或改用原始字符串 `Regex(\"\"\"\\s+\"\"\")`。"
            )
    suggestions.append(_diag_text(normalized_language, "source_suggestion_check_pair"))
    tag_match = TAG_MISMATCH_PATTERN.search(message)
    if tag_match:
        suggestions.append(
            _diag_text(
                normalized_language,
                "source_tag_fix_hint",
                closeTag=str(tag_match.group("close") or "").strip(),
                openTag=str(tag_match.group("open") or "").strip(),
            )
        )
    suggestions.append(_diag_text(normalized_language, "source_suggestion_rebuild"))
    suggestions.append(_diag_text(normalized_language, "source_suggestion_delegate"))

    evidence = [str(item).strip() for item in list(source_detail.get("evidence") or []) if str(item).strip()]
    if has_location and message:
        evidence = [f"{location}: {message}"] + evidence

    return {
        "title": _diag_text(normalized_language, "source_user_title"),
        "category": _diag_text(normalized_language, "source_user_category"),
        "summary": summary,
        "reason": reason,
        "probable_causes": [probable_cause],
        "suggestions": _merge_unique_text(suggestions, max_items=6),
        "evidence": _merge_unique_text(evidence, max_items=4),
        "source_file": path,
        "source_line": max(source_line, 0),
        "source_column": max(source_column, 0),
    }


def _build_rule_result(
    lines: list[str],
    failure_message: str = "",
    language: str = "zh-CN",
) -> dict[str, Any]:
    normalized_language = _normalize_diag_language(language)
    matches = _collect_rule_matches(lines, language=normalized_language)
    knowledge_hits = [item["rule_id"] for item in matches]
    probable_causes = _merge_unique_text([item["reason"] for item in matches], max_items=5)
    suggestions = _merge_unique_text(
        [suggestion for item in matches for suggestion in item.get("suggestions", [])],
        max_items=8,
    )

    structured_errors = []
    for item in matches[:6]:
        structured_errors.append(
            {
                "title": item["title"],
                "category": item["category"],
                "severity": item["severity"],
                "reason": item["reason"],
                "evidence": item["evidence"],
                "suggestions": item["suggestions"],
                "confidence": round(float(item.get("confidence", 0.7)), 2),
                "rule_id": item["rule_id"],
            }
        )

    if not structured_errors:
        generic_evidence = _extract_generic_error_evidence(lines)
        if generic_evidence:
            structured_errors.append(
                {
                    "title": _diag_text(normalized_language, "generic_error_title"),
                    "category": _diag_text(normalized_language, "generic_error_category"),
                    "severity": "medium",
                    "reason": _diag_text(normalized_language, "generic_error_reason"),
                    "evidence": generic_evidence[:3],
                    "suggestions": [
                        _diag_text(normalized_language, "generic_error_suggestion_1"),
                        _diag_text(normalized_language, "generic_error_suggestion_2"),
                    ],
                    "confidence": 0.58,
                    "rule_id": "generic_error_hint",
                }
            )
            probable_causes.append(_diag_text(normalized_language, "generic_probable_cause"))
            suggestions.extend(
                [
                    _diag_text(normalized_language, "generic_suggestion_1"),
                    _diag_text(normalized_language, "generic_suggestion_2"),
                ]
            )

    normalized_message = str(failure_message or "").strip()
    has_source_syntax_hit = "source_syntax_error" in knowledge_hits
    source_guidance: dict[str, Any] | None = None
    if has_source_syntax_hit:
        source_detail = _extract_source_error_detail(lines)
        if source_detail:
            source_guidance = _build_source_syntax_details(source_detail, normalized_language)
            probable_causes = _merge_unique_text(
                list(source_guidance.get("probable_causes") or []) + probable_causes,
                max_items=5,
            )
            suggestions = _merge_unique_text(
                list(source_guidance.get("suggestions") or []) + suggestions,
                max_items=8,
            )
            if structured_errors:
                source_error_index = next(
                    (
                        index
                        for index, item in enumerate(structured_errors)
                        if str(item.get("rule_id") or "") == "source_syntax_error"
                    ),
                    0,
                )
                first_error = dict(structured_errors[source_error_index])
                first_error["title"] = str(source_guidance.get("title") or first_error.get("title") or "").strip()
                first_error["category"] = str(source_guidance.get("category") or first_error.get("category") or "").strip()
                first_error["reason"] = str(source_guidance.get("reason") or first_error.get("reason") or "").strip()
                first_error["evidence"] = _merge_unique_text(
                    list(source_guidance.get("evidence") or []) + list(first_error.get("evidence") or []),
                    max_items=3,
                )
                first_error["suggestions"] = _merge_unique_text(
                    list(source_guidance.get("suggestions") or []) + list(first_error.get("suggestions") or []),
                    max_items=4,
                )
                source_file = str(source_guidance.get("source_file") or "").strip()
                if source_file:
                    first_error["source_file"] = source_file
                source_line = int(source_guidance.get("source_line") or 0)
                source_column = int(source_guidance.get("source_column") or 0)
                if source_line > 0:
                    first_error["source_line"] = source_line
                if source_column > 0:
                    first_error["source_column"] = source_column
                structured_errors[source_error_index] = first_error

    if normalized_message and not has_source_syntax_hit:
        probable_causes = _merge_unique_text([normalized_message] + probable_causes, max_items=5)

    if source_guidance:
        summary = str(source_guidance.get("summary") or "").strip()
        reason = str(source_guidance.get("reason") or "").strip()
    elif structured_errors:
        summary = _diag_text(
            normalized_language,
            "summary_with_hits",
            count=len(structured_errors),
            title=structured_errors[0]["title"],
        )
        reason = structured_errors[0]["reason"]
    else:
        summary = _diag_text(normalized_language, "unknown_summary")
        reason = normalized_message or _diag_text(normalized_language, "unknown_reason")
        if not suggestions:
            suggestions = [
                _diag_text(normalized_language, "unknown_suggestion_1"),
                _diag_text(normalized_language, "unknown_suggestion_2"),
            ]

    confidence = 0.45 + min(len(matches), 4) * 0.11
    if not matches:
        confidence = 0.55 if structured_errors else 0.3
    confidence = round(min(confidence, 0.95), 2)

    return {
        "status": "succeeded",
        "provider": "rule",
        "model": "",
        "language": normalized_language,
        "summary": summary,
        "reason": reason,
        "probable_causes": _merge_unique_text(probable_causes, max_items=5),
        "suggestions": _merge_unique_text(suggestions, max_items=8),
        "knowledge_hits": _merge_unique_text(knowledge_hits, max_items=8),
        "structured_errors": structured_errors,
        "analyzed_log_lines": len(lines),
        "confidence": confidence,
        "error": "",
        "updated_at": _now_iso(),
    }


def _sanitize_path_reference_token(raw_path: str, task_id: str = "") -> str:
    token = str(raw_path or "").strip()
    if not token:
        return token
    stripped = token.strip("`'\"")
    normalized = stripped.replace("\\", "/")
    if normalized.startswith("file://"):
        normalized = re.sub(r"^file:/+", "/", normalized)
    elif "://" in normalized or normalized.startswith("//"):
        return token

    if task_id:
        normalized = normalized.replace(f"/data/tasks/{task_id}/", "")
    normalized = TASK_PATH_PREFIX_PATTERN.sub("", normalized)

    lower = normalized.lower()
    for marker in ("project/", "src/", "pages/", "app/", "input/", "output/", "html_assets/"):
        idx = lower.find(marker)
        if idx >= 0:
            normalized = normalized[idx:]
            break

    if normalized.startswith("/") or re.match(r"^[a-zA-Z]:/", normalized):
        parts = [segment for segment in normalized.split("/") if segment and not re.match(r"^[a-zA-Z]:$", segment)]
        if parts:
            normalized = "/".join(parts[-4:] if len(parts) > 4 else parts)

    normalized = normalized.lstrip("/")
    if not normalized:
        return token
    return normalized


def _sanitize_path_references(text: str, task_id: str = "") -> str:
    source = str(text or "").strip()
    if not source:
        return ""
    protected_snippets: dict[str, str] = {}

    def _protect_code_snippet(match: re.Match[str]) -> str:
        placeholder = f"__CODE_SNIPPET_{len(protected_snippets)}__"
        protected_snippets[placeholder] = match.group(0)
        return placeholder

    protected_source = re.sub(r"`[^`]*\\[^`]*`", _protect_code_snippet, source)
    normalized = protected_source.replace("\\", "/")
    if task_id:
        normalized = normalized.replace(f"/data/tasks/{task_id}/", "")
    normalized = TASK_PATH_PREFIX_PATTERN.sub("", normalized)

    def _replace_abs(match: re.Match[str]) -> str:
        raw = match.group(0)
        prefix = normalized[max(0, match.start() - 10):match.start()].lower()
        if "http://" in prefix or "https://" in prefix:
            return raw
        if match.start() > 0 and re.match(r"[A-Za-z0-9_.-]", normalized[match.start() - 1]):
            return raw
        sanitized = _sanitize_path_reference_token(raw, task_id=task_id)
        return sanitized or raw

    sanitized_text = ABSOLUTE_PATH_PATTERN.sub(_replace_abs, normalized)
    for placeholder, snippet in protected_snippets.items():
        sanitized_text = sanitized_text.replace(placeholder, snippet)
    return sanitized_text


def _sanitize_text_list(values: list[str], task_id: str = "", max_items: int = 8) -> list[str]:
    sanitized: list[str] = []
    for item in values:
        text = _sanitize_path_references(str(item or "").strip(), task_id=task_id)
        if text:
            sanitized.append(text)
    return _merge_unique_text(sanitized, max_items=max_items)


def _sanitize_structured_errors(values: list[dict[str, Any]], task_id: str = "") -> list[dict[str, Any]]:
    if not isinstance(values, list):
        return []
    sanitized_errors: list[dict[str, Any]] = []
    for raw_item in values:
        if not isinstance(raw_item, dict):
            continue
        title = _sanitize_path_references(str(raw_item.get("title") or "").strip(), task_id=task_id)
        category = _sanitize_path_references(str(raw_item.get("category") or "").strip(), task_id=task_id)
        reason = _sanitize_path_references(str(raw_item.get("reason") or "").strip(), task_id=task_id)
        source_file = _sanitize_path_references(str(raw_item.get("source_file") or "").strip(), task_id=task_id)
        evidence = _sanitize_text_list(
            [str(item) for item in list(raw_item.get("evidence") or [])],
            task_id=task_id,
            max_items=3,
        )
        suggestions = _sanitize_text_list(
            [str(item) for item in list(raw_item.get("suggestions") or [])],
            task_id=task_id,
            max_items=4,
        )
        sanitized_errors.append(
            {
                **raw_item,
                "title": title,
                "category": category,
                "reason": reason,
                "source_file": source_file,
                "evidence": evidence,
                "suggestions": suggestions,
            }
        )
    return sanitized_errors


def _contains_platform_docker_issue(
    lines: list[str],
    failure_message: str,
    diagnosis_result: dict[str, Any],
) -> bool:
    if not isinstance(diagnosis_result, dict):
        return False
    knowledge_hits = [str(item) for item in list(diagnosis_result.get("knowledge_hits") or [])]
    if "source_syntax_error" in knowledge_hits:
        return False

    candidates: list[str] = list(lines or [])[-120:]
    candidates.append(str(failure_message or ""))
    candidates.append(str(diagnosis_result.get("summary") or ""))
    candidates.append(str(diagnosis_result.get("reason") or ""))
    candidates.extend([str(item) for item in list(diagnosis_result.get("probable_causes") or [])])
    candidates.extend([str(item) for item in list(diagnosis_result.get("suggestions") or [])])
    for item in list(diagnosis_result.get("structured_errors") or []):
        if isinstance(item, dict):
            candidates.append(str(item.get("title") or ""))
            candidates.append(str(item.get("reason") or ""))
            candidates.extend([str(line) for line in list(item.get("evidence") or [])])

    source_code_hit = any(SOURCE_CODE_ERROR_PATTERN.search(str(text or "")) for text in candidates)
    if source_code_hit:
        return False

    docker_hit = any(DOCKER_INFRA_PATTERN.search(str(text or "")) for text in candidates)
    if not docker_hit:
        return False

    return "docker_platform_issue" in knowledge_hits or docker_hit


def _apply_platform_issue_override(diagnosis_result: dict[str, Any], language: str) -> dict[str, Any]:
    normalized_language = _normalize_diag_language(language)
    updated = dict(diagnosis_result)
    updated["summary"] = _diag_text(normalized_language, "infra_summary")
    updated["reason"] = _diag_text(normalized_language, "infra_reason")
    updated["probable_causes"] = _merge_unique_text(
        [_diag_text(normalized_language, "infra_cause")] + list(updated.get("probable_causes") or []),
        max_items=5,
    )
    updated["suggestions"] = _merge_unique_text(
        [
            _diag_text(normalized_language, "infra_suggestion_1"),
            _diag_text(normalized_language, "infra_suggestion_2"),
            _diag_text(normalized_language, "infra_suggestion_3"),
        ] + list(updated.get("suggestions") or []),
        max_items=8,
    )
    updated["structured_errors"] = [
        {
            "title": _diag_text(normalized_language, "infra_error_title"),
            "category": _diag_text(normalized_language, "infra_error_category"),
            "severity": "high",
            "reason": _diag_text(normalized_language, "infra_reason"),
            "evidence": [],
            "suggestions": [
                _diag_text(normalized_language, "infra_suggestion_1"),
                _diag_text(normalized_language, "infra_suggestion_2"),
            ],
            "confidence": max(0.82, float(updated.get("confidence") or 0.0)),
            "rule_id": "docker_platform_issue",
        }
    ]
    updated["knowledge_hits"] = _merge_unique_text(
        list(updated.get("knowledge_hits") or []) + ["docker_platform_issue"],
        max_items=8,
    )
    updated["confidence"] = round(max(float(updated.get("confidence") or 0.0), 0.82), 2)
    return updated


def _prioritize_source_error_result(
    diagnosis_result: dict[str, Any],
    rule_result: dict[str, Any],
) -> dict[str, Any]:
    updated = dict(diagnosis_result or {})
    updated["summary"] = str(rule_result.get("summary") or updated.get("summary") or "").strip()
    updated["reason"] = str(rule_result.get("reason") or updated.get("reason") or "").strip()
    updated["structured_errors"] = list(rule_result.get("structured_errors") or updated.get("structured_errors") or [])[:6]
    updated["probable_causes"] = _merge_unique_text(
        list(rule_result.get("probable_causes") or []) + list(updated.get("probable_causes") or []),
        max_items=5,
    )
    updated["suggestions"] = _merge_unique_text(
        list(rule_result.get("suggestions") or []) + list(updated.get("suggestions") or []),
        max_items=8,
    )
    updated["knowledge_hits"] = _merge_unique_text(
        list(rule_result.get("knowledge_hits") or []) + list(updated.get("knowledge_hits") or []),
        max_items=8,
    )
    updated["confidence"] = round(max(float(updated.get("confidence") or 0.0), float(rule_result.get("confidence") or 0.0)), 2)
    return updated


def _finalize_diagnosis_result(
    diagnosis_result: dict[str, Any],
    lines: list[str],
    failure_message: str,
    task_meta: dict[str, Any] | None,
    language: str,
) -> dict[str, Any]:
    normalized_language = _normalize_diag_language(language)
    task_id = str((task_meta or {}).get("task_id") or "").strip()
    finalized = dict(diagnosis_result or {})
    finalized["language"] = normalized_language
    finalized["summary"] = _sanitize_path_references(str(finalized.get("summary") or ""), task_id=task_id)
    finalized["reason"] = _sanitize_path_references(str(finalized.get("reason") or ""), task_id=task_id)
    finalized["probable_causes"] = _sanitize_text_list(
        [str(item) for item in list(finalized.get("probable_causes") or [])],
        task_id=task_id,
        max_items=5,
    )
    finalized["suggestions"] = _sanitize_text_list(
        [str(item) for item in list(finalized.get("suggestions") or [])],
        task_id=task_id,
        max_items=8,
    )
    finalized["suggestions"] = _merge_unique_text(
        list(finalized.get("suggestions") or []) + [_diag_text(normalized_language, "user_delegate_suggestion")],
        max_items=8,
    )
    finalized["structured_errors"] = _sanitize_structured_errors(
        list(finalized.get("structured_errors") or []),
        task_id=task_id,
    )[:6]
    finalized["error"] = _sanitize_path_references(str(finalized.get("error") or ""), task_id=task_id)

    if _contains_platform_docker_issue(lines, failure_message, finalized):
        finalized = _apply_platform_issue_override(finalized, normalized_language)

    return finalized


def _try_parse_json_dict(candidate: str) -> dict[str, Any] | None:
    raw = str(candidate or "").strip()
    if not raw:
        return None
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except Exception:
        pass

    normalized = raw.replace("\ufeff", "").strip()
    normalized = MARKDOWN_JSON_FENCE_PATTERN.sub("", normalized).strip()
    normalized = (
        normalized.replace("“", "\"")
        .replace("”", "\"")
        .replace("’", "'")
        .replace("‘", "'")
    )
    normalized = TRAILING_COMMA_PATTERN.sub(r"\1", normalized)
    try:
        data = json.loads(normalized)
        if isinstance(data, dict):
            return data
    except Exception:
        pass

    try:
        data = ast.literal_eval(normalized)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return None


def _extract_json_object(raw_text: str) -> dict[str, Any] | None:
    text = str(raw_text or "").strip()
    if not text:
        return None

    direct = _try_parse_json_dict(text)
    if direct is not None:
        return direct

    match = JSON_OBJECT_PATTERN.search(text)
    if not match:
        return None
    return _try_parse_json_dict(match.group(0))


def _extract_model_content(response_data: dict[str, Any]) -> str:
    if not isinstance(response_data, dict):
        return ""
    choices = response_data.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0] or {}
    message = first.get("message") if isinstance(first, dict) else None
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        try:
            return json.dumps(content, ensure_ascii=False)
        except Exception:
            return str(content)
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                text_value = item.get("text")
                if isinstance(text_value, str):
                    parts.append(text_value)
        return "\n".join(parts)
    return ""


def _normalize_llm_diagnosis(payload: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None

    summary = str(payload.get("summary") or "").strip()
    reason = str(payload.get("reason") or "").strip()
    probable_causes = payload.get("probable_causes")
    suggestions = payload.get("suggestions")
    structured_errors = payload.get("structured_errors")

    normalized_causes = []
    if isinstance(probable_causes, list):
        normalized_causes = [str(item).strip() for item in probable_causes if str(item).strip()]

    normalized_suggestions = []
    if isinstance(suggestions, list):
        normalized_suggestions = [str(item).strip() for item in suggestions if str(item).strip()]

    normalized_errors = []
    if isinstance(structured_errors, list):
        for item in structured_errors:
            if not isinstance(item, dict):
                continue
            normalized_errors.append(
                {
                    "title": str(item.get("title") or "").strip(),
                    "category": str(item.get("category") or "智能分析").strip() or "智能分析",
                    "severity": str(item.get("severity") or "medium").strip() or "medium",
                    "reason": str(item.get("reason") or "").strip(),
                    "evidence": [
                        str(v).strip()
                        for v in (item.get("evidence") if isinstance(item.get("evidence"), list) else [])
                        if str(v).strip()
                    ][:3],
                    "suggestions": [
                        str(v).strip()
                        for v in (item.get("suggestions") if isinstance(item.get("suggestions"), list) else [])
                        if str(v).strip()
                    ][:4],
                    "confidence": float(item.get("confidence") or 0.7),
                    "rule_id": "llm",
                }
            )

    confidence = payload.get("confidence")
    try:
        confidence_value = float(confidence)
    except Exception:
        confidence_value = 0.76
    confidence_value = round(max(0.0, min(confidence_value, 0.99)), 2)

    if not summary and not reason and not normalized_causes and not normalized_suggestions:
        return None

    return {
        "summary": summary,
        "reason": reason,
        "probable_causes": normalized_causes,
        "suggestions": normalized_suggestions,
        "structured_errors": normalized_errors,
        "confidence": confidence_value,
    }


def _call_openrouter_diagnosis(
    lines: list[str],
    failure_message: str,
    rule_result: dict[str, Any],
    task_meta: dict[str, Any] | None = None,
    language: str = "zh-CN",
    ai_config: dict[str, Any] | None = None,
) -> tuple[dict[str, Any] | None, str]:
    normalized_language = _normalize_diag_language(language)
    runtime_config = resolve_openrouter_diag_runtime_config(ai_config=ai_config)
    if not runtime_config.get("enabled"):
        return None, "openrouter disabled"

    api_key = str(runtime_config.get("api_key") or "").strip()
    if not api_key:
        return None, "OPENROUTER_API_KEY is empty"

    api_url = str(runtime_config.get("api_url") or "").strip()
    if not api_url:
        return None, "OPENROUTER_API_URL is empty"
    model = str(runtime_config.get("model") or "").strip()
    if not model:
        return None, "OPENROUTER model is empty"

    brief_logs = "\n".join(lines[-80:])
    meta_text = json.dumps(task_meta or {}, ensure_ascii=False, indent=2)
    rule_text = json.dumps(
        {
            "summary": rule_result.get("summary"),
            "reason": rule_result.get("reason"),
            "probable_causes": rule_result.get("probable_causes", []),
            "suggestions": rule_result.get("suggestions", []),
            "knowledge_hits": rule_result.get("knowledge_hits", []),
        },
        ensure_ascii=False,
        indent=2,
    )

    system_prompt = (
        "你是 Android 构建失败诊断助手。你必须只输出 JSON，不要输出任何额外说明。"
        "请基于日志和规则结论，给出面向普通用户的诊断结果，重点是可落地的排查步骤。"
        "禁止在输出中包含服务器绝对路径（例如 /data/tasks/...）。"
        "如果必须提到文件，请只使用用户上传包内的相对路径。"
        "如果日志里有明确源码编译错误（文件+行列号或语法错误），必须优先判定为源码问题。"
        "若命中源码问题，必须明确指出关键文件相对路径、行号、列号，并输出分步骤解决方案。"
        "面向用户描述时，优先使用“您的源码语法”这一表述。"
        "只有在没有明确源码错误时，才可判断为 Docker/容器/平台环境问题。"
        "若判断为 Docker/容器/平台环境问题，明确归因为网站服务端环境，建议用户联系网站开发者处理。"
    )
    user_prompt = (
        "请根据以下信息诊断构建失败原因，并输出 JSON。\n\n"
        "要求：\n"
        "1. 仅输出一个 JSON 对象。\n"
        "2. 字段结构：\n"
        "{\n"
        '  "summary": "一句话总结",\n'
        '  "reason": "主要原因",\n'
        '  "probable_causes": ["原因1","原因2"],\n'
        '  "suggestions": ["解决步骤1","解决步骤2"],\n'
        '  "confidence": 0.0,\n'
        '  "structured_errors": [\n'
        "    {\n"
        '      "title": "问题标题",\n'
        '      "category": "分类",\n'
        '      "severity": "high|medium|low",\n'
        '      "reason": "原因说明",\n'
        '      "evidence": ["证据日志"],\n'
        '      "suggestions": ["处理建议"],\n'
        '      "confidence": 0.0\n'
        "    }\n"
        "  ]\n"
        "}\n"
        "3. confidence 为 0~1 的小数。\n"
        "4. 不要包含 Markdown。\n\n"
        f"5. 输出语言必须是：{_diag_text(normalized_language, 'llm_lang_name')}。\n"
        "6. 结论要面向网站用户，不要默认用户具备服务端开发权限。\n"
        "7. 若出现 'Docker build failed, exit code: 1' 这类外层报错，但日志中有明确源码编译错误，必须以源码编译错误为根因。\n\n"
        "8. 若为源码问题，`summary`、`reason`、`probable_causes`、`suggestions` 中至少两处要体现关键行定位信息（相对路径+行列号）。\n"
        "9. 若涉及源码描述，尽量使用“您的源码语法”而不是“源码语法”。\n\n"
        f"失败消息：\n{failure_message or '无'}\n\n"
        f"任务上下文：\n{meta_text}\n\n"
        f"规则库初判：\n{rule_text}\n\n"
        f"日志片段：\n{brief_logs}"
    )

    request_body = {
        "model": model,
        "temperature": 0.0,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    site_url = str(runtime_config.get("site_url") or "").strip()
    app_name = str(runtime_config.get("app_name") or "ConvertAPK-EXE").strip()
    if site_url:
        headers["HTTP-Referer"] = site_url
    if app_name:
        headers["X-Title"] = app_name

    data_bytes = json.dumps(request_body, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url=api_url,
        data=data_bytes,
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=float(runtime_config.get("timeout_seconds") or OPENROUTER_TIMEOUT_SECONDS)) as response:
            payload_text = response.read().decode("utf-8", errors="ignore")
    except urllib.error.HTTPError as exc:
        details = ""
        try:
            details = exc.read().decode("utf-8", errors="ignore")
        except Exception:
            details = ""
        return None, f"http {exc.code}: {details or str(exc)}"
    except Exception as exc:
        return None, str(exc)

    try:
        response_data = json.loads(payload_text or "{}")
    except Exception as exc:
        return None, f"openrouter response parse failed: {str(exc)}"

    content_text = _extract_model_content(response_data)
    parsed_json = _extract_json_object(content_text)
    normalized = _normalize_llm_diagnosis(parsed_json or {})
    if normalized is None:
        return None, "openrouter content is empty or invalid json"
    return normalized, ""


def diagnose_build_failure(
    log_lines: list[str] | None,
    failure_message: str = "",
    task_meta: dict[str, Any] | None = None,
    language: str = "zh-CN",
    ai_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_language = _normalize_diag_language(language)
    runtime_config = resolve_openrouter_diag_runtime_config(ai_config=ai_config)
    lines = normalize_log_lines(log_lines, max_lines=MAX_ANALYZE_LOG_LINES)
    if not lines and not str(failure_message or "").strip():
        result = create_idle_diagnosis(language=normalized_language)
        result["status"] = "skipped"
        result["summary"] = _diag_text(normalized_language, "no_logs_summary")
        result["updated_at"] = _now_iso()
        return result

    rule_result = _build_rule_result(
        lines,
        failure_message=failure_message,
        language=normalized_language,
    )
    llm_result, llm_error = _call_openrouter_diagnosis(
        lines=lines,
        failure_message=failure_message,
        rule_result=rule_result,
        task_meta=task_meta,
        language=normalized_language,
        ai_config=runtime_config,
    )
    if llm_result is None:
        if llm_error:
            rule_result["error"] = llm_error
            rule_result["probable_causes"] = _merge_unique_text(
                [_diag_text(normalized_language, "llm_fallback_cause")] + list(rule_result.get("probable_causes") or []),
                max_items=5,
            )
            rule_result["suggestions"] = _merge_unique_text(
                [_diag_text(normalized_language, "llm_fallback_suggestion")] + list(rule_result.get("suggestions") or []),
                max_items=8,
            )
        rule_result["updated_at"] = _now_iso()
        return _finalize_diagnosis_result(
            diagnosis_result=rule_result,
            lines=lines,
            failure_message=failure_message,
            task_meta=task_meta,
            language=normalized_language,
        )

    merged_summary = str(llm_result.get("summary") or "").strip() or rule_result["summary"]
    merged_reason = str(llm_result.get("reason") or "").strip() or rule_result["reason"]
    llm_causes = list(llm_result.get("probable_causes") or [])
    llm_suggestions = list(llm_result.get("suggestions") or [])
    merged_causes = _merge_unique_text(
        llm_causes if llm_causes else list(rule_result.get("probable_causes") or []),
        max_items=5,
    )
    merged_suggestions = _merge_unique_text(
        llm_suggestions if llm_suggestions else list(rule_result.get("suggestions") or []),
        max_items=8,
    )

    llm_structured_errors = llm_result.get("structured_errors") or []
    if isinstance(llm_structured_errors, list) and llm_structured_errors:
        structured_errors = llm_structured_errors[:6]
    else:
        structured_errors = rule_result.get("structured_errors") or []

    result = {
        "status": "succeeded",
        "provider": str(runtime_config.get("provider") or "openrouter"),
        "model": str(runtime_config.get("model") or OPENROUTER_MODEL),
        "language": normalized_language,
        "summary": merged_summary,
        "reason": merged_reason,
        "probable_causes": merged_causes,
        "suggestions": merged_suggestions,
        "knowledge_hits": rule_result.get("knowledge_hits") or [],
        "structured_errors": structured_errors,
        "analyzed_log_lines": len(lines),
        "confidence": round(float(llm_result.get("confidence") or rule_result.get("confidence") or 0.76), 2),
        "error": "",
        "updated_at": _now_iso(),
    }
    if "source_syntax_error" in [str(item) for item in list(rule_result.get("knowledge_hits") or [])]:
        result = _prioritize_source_error_result(result, rule_result)
    return _finalize_diagnosis_result(
        diagnosis_result=result,
        lines=lines,
        failure_message=failure_message,
        task_meta=task_meta,
        language=normalized_language,
    )
