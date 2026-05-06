package com.jmin.tubbim.utils

import android.graphics.Color
import com.jmin.tubbim.BuildConfig

/**
 * 全局打包配置（作为模板时，只需要改 Gradle 的 buildConfigField 即可）。
 *
 * 你以后每次打包一个新壳 App，建议只改：
 * - `app/build.gradle.kts` -> defaultConfig 里的 BuildConfig 字段
 */
object AppConfig {

    /**
     * WebView 要加载的首页 URL（全局变量）
     *
     * 默认从 BuildConfig 读取，方便打包时改，不需要动代码。
     */
    val webViewUrl: String =
        BuildConfig.WEBVIEW_URL.takeIf { it.isNotBlank() } ?: DEFAULT_WEBVIEW_URL

    /**
     * 系统栏（状态栏）策略（全局变量）
     */
    val systemBars: SystemBarsConfig = SystemBarsConfig(
        hideStatusBar = BuildConfig.HIDE_STATUS_BAR,
        statusBarBackground = StatusBarBackground.from(BuildConfig.STATUS_BAR_BACKGROUND),
        lightStatusBarIcons = BuildConfig.LIGHT_STATUS_BAR_ICONS,
    )

    /**
     * 是否双击返回退出
     */
    val doubleClickExit: Boolean = BuildConfig.DOUBLE_CLICK_EXIT

    /**
     * 当 BuildConfig 未配置/为空时的兜底 URL
     */
    private const val DEFAULT_WEBVIEW_URL: String =
        "https://gcdn.yskrngame.com/games/game77_1/index.html"
}

data class SystemBarsConfig(
    /**
     * 是否隐藏系统状态栏（true=隐藏；false=显示）
     */
    val hideStatusBar: Boolean,

    /**
     * 状态栏背景（白底/透明）
     */
    val statusBarBackground: StatusBarBackground,

    /**
     * 状态栏图标颜色风格：
     * - true：深色图标（适合白底）
     * - false：浅色图标（适合深色背景/游戏画面）
     *
     * 注意：Android 的 API 名叫 “light status bar”，含义是“深色图标”。
     */
    val lightStatusBarIcons: Boolean,
) {
    /**
     * 是否允许内容绘制到状态栏下方（透明状态栏一般需要）
     */
    val drawBehindStatusBar: Boolean
        get() = statusBarBackground == StatusBarBackground.TRANSPARENT

    val statusBarColor: Int
        get() = when (statusBarBackground) {
            StatusBarBackground.TRANSPARENT -> Color.TRANSPARENT
            StatusBarBackground.WHITE -> Color.WHITE
        }
}

enum class StatusBarBackground {
    TRANSPARENT,
    WHITE;

    companion object {
        /**
         * 允许从 BuildConfig 的字符串读取（忽略大小写）：
         * - "transparent"
         * - "white"
         */
        fun from(raw: String?): StatusBarBackground {
            return when (raw?.trim()?.lowercase()) {
                "white" -> WHITE
                "transparent" -> TRANSPARENT
                else -> TRANSPARENT
            }
        }
    }
}


