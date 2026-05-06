package osa.cosa.html2apk

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue

object AppConfig {
    private fun resolveOrientation(raw: String): OrientationMode {
        return when (raw.trim().lowercase()) {
            "portrait" -> OrientationMode.PORTRAIT
            "landscape" -> OrientationMode.LANDSCAPE
            else -> OrientationMode.FOLLOW_SENSOR
        }
    }

    private fun resolveWebFillMode(raw: String): WebFillMode {
        return when (raw.trim().lowercase()) {
            "cover" -> WebFillMode.COVER
            else -> WebFillMode.CONTAIN
        }
    }

    var hideSystemBars by mutableStateOf(BuildConfig.HIDE_STATUS_BAR)

    var orientationMode by mutableStateOf(resolveOrientation(BuildConfig.SCREEN_ORIENTATION))

    var enableDoubleBackExit by mutableStateOf(BuildConfig.DOUBLE_CLICK_EXIT)

    var webFillMode by mutableStateOf(
        resolveWebFillMode(
            runCatching {
                val field = BuildConfig::class.java.getField("WEB_FILL_MODE")
                (field.get(null) as? String).orEmpty()
            }.getOrElse { "contain" }
        )
    )

    val useFilePickerForDownload: Boolean
        get() {
            val mode = runCatching {
                val field = BuildConfig::class.java.getField("DOWNLOAD_MODE")
                (field.get(null) as? String).orEmpty().trim().lowercase()
            }.getOrElse { "picker" }
            return mode != "silent"
        }

    val statusBarBackground: String
        get() = BuildConfig.STATUS_BAR_BACKGROUND

    val lightStatusBarIcons: Boolean
        get() = BuildConfig.LIGHT_STATUS_BAR_ICONS
}

enum class OrientationMode {
    FOLLOW_SENSOR,
    PORTRAIT,
    LANDSCAPE,
}

enum class WebFillMode {
    CONTAIN,
    COVER,
}
