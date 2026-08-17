package osa.cosa.html2apk

import android.app.Activity
import android.content.ActivityNotFoundException
import android.content.ContentValues
import android.content.Context
import android.content.Intent
import android.content.pm.ActivityInfo
import android.os.Build
import android.os.Bundle
import android.os.Environment
import android.os.Handler
import android.os.Looper
import android.provider.MediaStore
import android.view.View
import android.view.ViewGroup
import android.view.WindowManager
import android.webkit.JavascriptInterface
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.statusBars
import androidx.compose.foundation.layout.systemBarsPadding
import androidx.compose.foundation.layout.windowInsetsTopHeight
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color as ComposeColor
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowInsetsControllerCompat
import osa.cosa.html2apk.ui.theme.HTML2APKTheme

private const val START_URL = "file:///android_asset/html2apkdemo/index.html"

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        applySystemBars()
        WebView.setWebContentsDebuggingEnabled(BuildConfig.DEBUG)
        setContent {
            HTML2APKTheme {
                Box(modifier = Modifier.fillMaxSize()) {
                    val paddingModifier = if (AppConfig.hideSystemBars) Modifier else Modifier.systemBarsPadding()
                    Box(
                        modifier = Modifier
                            .fillMaxSize()
                            .then(paddingModifier)
                            .imePadding(),
                    ) {
                        Html2ApkWebView(startUrl = START_URL, modifier = Modifier.fillMaxSize())
                    }
                    if (!AppConfig.hideSystemBars && !AppConfig.statusBarDrawBehind) {
                        Box(
                            modifier = Modifier
                                .fillMaxWidth()
                                .windowInsetsTopHeight(WindowInsets.statusBars)
                                .background(ComposeColor(AppConfig.statusBarColor)),
                        )
                    }
                }
            }
        }
    }

    override fun onWindowFocusChanged(hasFocus: Boolean) {
        super.onWindowFocusChanged(hasFocus)
        if (hasFocus) {
            applySystemBars()
        }
    }

    private fun applySystemBars() {
        WindowCompat.setDecorFitsSystemWindows(window, false)
        val statusBarColor = AppConfig.statusBarColor
        @Suppress("DEPRECATION")
        window.statusBarColor = statusBarColor
        window.decorView.setBackgroundColor(statusBarColor)

        val controller = WindowInsetsControllerCompat(window, window.decorView)
        controller.isAppearanceLightStatusBars = AppConfig.lightStatusBarIcons
        if (AppConfig.hideSystemBars) {
            window.addFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN)
            window.clearFlags(WindowManager.LayoutParams.FLAG_FORCE_NOT_FULLSCREEN)
            window.decorView.systemUiVisibility =
                View.SYSTEM_UI_FLAG_FULLSCREEN or View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
            controller.systemBarsBehavior =
                WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
            controller.hide(WindowInsetsCompat.Type.statusBars())
        } else {
            window.clearFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN)
            window.addFlags(WindowManager.LayoutParams.FLAG_FORCE_NOT_FULLSCREEN)
            var visibility = View.SYSTEM_UI_FLAG_VISIBLE
            if (AppConfig.lightStatusBarIcons) {
                visibility = visibility or View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR
            }
            window.decorView.systemUiVisibility = visibility
            controller.show(WindowInsetsCompat.Type.statusBars())
        }
    }
}

@Composable
fun Html2ApkWebView(startUrl: String, modifier: Modifier = Modifier) {
    val context = LocalContext.current

    var canGoBack by remember { mutableStateOf(false) }
    var lastBackPressTime by remember { mutableStateOf(0L) }
    var pendingFileCallback by remember { mutableStateOf<ValueCallback<Array<android.net.Uri>>?>(null) }
    var pendingDownload by remember { mutableStateOf<PendingDownload?>(null) }
    val orientationMode = AppConfig.orientationMode
    val useContainFillMode = shouldUseContainFillMode()

    val fileChooserLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.StartActivityForResult(),
    ) { result ->
        val uris = WebChromeClient.FileChooserParams.parseResult(result.resultCode, result.data)
        pendingFileCallback?.onReceiveValue(uris)
        pendingFileCallback = null
    }

    val saveDocumentLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.StartActivityForResult(),
    ) { result ->
        val pending = pendingDownload
        pendingDownload = null
        if (pending == null) return@rememberLauncherForActivityResult
        if (result.resultCode != Activity.RESULT_OK) {
            Toast.makeText(context, "已取消保存", Toast.LENGTH_SHORT).show()
            return@rememberLauncherForActivityResult
        }
        val uri = result.data?.data
        if (uri == null) {
            Toast.makeText(context, "保存失败: 未选择文件位置", Toast.LENGTH_SHORT).show()
            return@rememberLauncherForActivityResult
        }
        try {
            context.contentResolver.openOutputStream(uri)?.use { it.write(pending.bytes) }
            Toast.makeText(context, "已保存: ${pending.filename}", Toast.LENGTH_SHORT).show()
        } catch (e: Exception) {
            Toast.makeText(context, "保存失败: ${e.message}", Toast.LENGTH_SHORT).show()
        }
    }

    val webView = remember {
        WebView(context).apply {
            layoutParams = ViewGroup.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT,
            )
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = true
            settings.useWideViewPort = useContainFillMode
            settings.loadWithOverviewMode = useContainFillMode
            settings.cacheMode = WebSettings.LOAD_DEFAULT
            settings.allowFileAccess = true
            settings.allowContentAccess = true
            settings.allowFileAccessFromFileURLs = true
            settings.allowUniversalAccessFromFileURLs = false
            if (useContainFillMode) {
                setInitialScale(0)
            } else {
                setInitialScale(100)
            }

            addJavascriptInterface(
                DownloadBridge(context) { filename, mimeType, bytes ->
                    val safeName = filename.ifBlank { "download_${System.currentTimeMillis()}" }
                    val pending = PendingDownload(safeName, mimeType, bytes)
                    if (shouldUseFilePickerForDownload()) {
                        pendingDownload = pending
                        val intent = Intent(Intent.ACTION_CREATE_DOCUMENT).apply {
                            addCategory(Intent.CATEGORY_OPENABLE)
                            type = if (mimeType.isBlank()) "application/octet-stream" else mimeType
                            putExtra(Intent.EXTRA_TITLE, safeName)
                        }
                        saveDocumentLauncher.launch(intent)
                    } else {
                        saveToDownloads(context, pending)
                    }
                },
                "AndroidDownload",
            )

            webViewClient = object : WebViewClient() {
                override fun onPageFinished(view: WebView, url: String) {
                    canGoBack = view.canGoBack()
                    view.evaluateJavascript(INJECT_DOWNLOAD_HOOK, null)
                }
            }

            webChromeClient = object : WebChromeClient() {
                override fun onShowFileChooser(
                    webView: WebView?,
                    filePathCallback: ValueCallback<Array<android.net.Uri>>?,
                    fileChooserParams: FileChooserParams?,
                ): Boolean {
                    if (filePathCallback == null || fileChooserParams == null) return false

                    pendingFileCallback?.onReceiveValue(null)
                    pendingFileCallback = filePathCallback

                    return try {
                        fileChooserLauncher.launch(fileChooserParams.createIntent())
                        true
                    } catch (_: ActivityNotFoundException) {
                        pendingFileCallback?.onReceiveValue(null)
                        pendingFileCallback = null
                        false
                    }
                }
            }
        }
    }

    BackHandler(enabled = canGoBack) {
        webView.goBack()
    }
    BackHandler(enabled = !canGoBack) {
        if (AppConfig.enableDoubleBackExit) {
            val now = System.currentTimeMillis()
            if (now - lastBackPressTime <= 1500) {
                (context as? ComponentActivity)?.finish()
            } else {
                lastBackPressTime = now
                Toast.makeText(context, "再按一次退出应用", Toast.LENGTH_SHORT).show()
            }
        } else {
            (context as? ComponentActivity)?.finish()
        }
    }

    DisposableEffect(orientationMode) {
        val activity = context as? ComponentActivity
        activity?.requestedOrientation = when (orientationMode) {
            OrientationMode.FOLLOW_SENSOR -> ActivityInfo.SCREEN_ORIENTATION_UNSPECIFIED
            OrientationMode.PORTRAIT -> ActivityInfo.SCREEN_ORIENTATION_PORTRAIT
            OrientationMode.LANDSCAPE -> ActivityInfo.SCREEN_ORIENTATION_LANDSCAPE
        }
        onDispose { }
    }

    DisposableEffect(startUrl) {
        webView.loadUrl(startUrl)
        onDispose {
            pendingFileCallback?.onReceiveValue(null)
            pendingFileCallback = null
            webView.destroy()
        }
    }

    AndroidView(
        factory = { webView },
        modifier = modifier,
    )
}

private const val INJECT_DOWNLOAD_HOOK = """
(function(){
  if (window.__androidDownloadHooked) return;
  window.__androidDownloadHooked = true;
  const origClick = HTMLAnchorElement.prototype.click;
  HTMLAnchorElement.prototype.click = function() {
    try {
      const href = this.href || '';
      const filename = this.download || ('download_' + Date.now());
      if ((href.startsWith('blob:') || href.startsWith('data:')) && window.AndroidDownload && window.AndroidDownload.saveBlob) {
        if (href.startsWith('data:')) {
          window.AndroidDownload.saveBlob(filename, href);
          return;
        }
        fetch(href).then(r => r.blob()).then(b => {
          const reader = new FileReader();
          reader.onloadend = () => {
            window.AndroidDownload.saveBlob(filename, reader.result);
          };
          reader.readAsDataURL(b);
        });
        return;
      }
    } catch (e) {}
    return origClick.call(this);
  };
})();
"""

private data class PendingDownload(
    val filename: String,
    val mimeType: String,
    val bytes: ByteArray,
)

private fun shouldUseFilePickerForDownload(): Boolean {
    // Compatible with old templates that don't have AppConfig.useFilePickerForDownload
    // or BuildConfig.DOWNLOAD_MODE.
    val mode = runCatching {
        val field = BuildConfig::class.java.getField("DOWNLOAD_MODE")
        (field.get(null) as? String).orEmpty().trim().lowercase()
    }.getOrElse { "" }
    return mode != "silent"
}

private fun shouldUseContainFillMode(): Boolean {
    val mode = runCatching {
        val field = BuildConfig::class.java.getField("WEB_FILL_MODE")
        (field.get(null) as? String).orEmpty().trim().lowercase()
    }.getOrElse { "" }
    return mode != "cover"
}

private fun saveToDownloads(context: Context, pending: PendingDownload) {
    try {
        val resolver = context.contentResolver
        val mimeType = pending.mimeType.ifBlank { "application/octet-stream" }
        val values = ContentValues().apply {
            put(MediaStore.Downloads.DISPLAY_NAME, pending.filename)
            put(MediaStore.Downloads.MIME_TYPE, mimeType)
            put(MediaStore.Downloads.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                put(MediaStore.Downloads.IS_PENDING, 1)
            }
        }

        val uri = resolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, values)
            ?: throw IllegalStateException("无法创建下载条目")

        resolver.openOutputStream(uri)?.use { it.write(pending.bytes) }
            ?: throw IllegalStateException("无法打开输出流")

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            val doneValues = ContentValues().apply {
                put(MediaStore.Downloads.IS_PENDING, 0)
            }
            resolver.update(uri, doneValues, null, null)
        }

        Toast.makeText(context, "已保存到下载目录: Downloads/${pending.filename}", Toast.LENGTH_LONG).show()
    } catch (e: Exception) {
        Toast.makeText(context, "保存失败: ${e.message}", Toast.LENGTH_LONG).show()
    }
}

private class DownloadBridge(
    private val context: Context,
    private val onSaveRequested: (String, String, ByteArray) -> Unit,
) {
    @JavascriptInterface
    fun saveBlob(filename: String, dataUrl: String?) {
        if (dataUrl.isNullOrBlank()) return
        try {
            val commaIndex = dataUrl.indexOf(',')
            if (commaIndex <= 0) return
            val header = dataUrl.substring(0, commaIndex)
            val base64Data = dataUrl.substring(commaIndex + 1)
            val mimeMatch = Regex("^data:([^;]+);base64$").find(header)
            val mimeType = mimeMatch?.groupValues?.get(1) ?: "application/octet-stream"
            val bytes = android.util.Base64.decode(base64Data, android.util.Base64.DEFAULT)

            Handler(Looper.getMainLooper()).post {
                onSaveRequested(filename, mimeType, bytes)
            }
        } catch (e: Exception) {
            Toast.makeText(context, "保存失败: ${e.message}", Toast.LENGTH_SHORT).show()
        }
    }
}
