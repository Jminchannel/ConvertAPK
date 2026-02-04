package osa.cosa.html2apk

import android.content.ActivityNotFoundException
import android.content.ContentValues
import android.os.Bundle
import android.os.Environment
import android.graphics.Color
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
import android.provider.MediaStore
import java.util.Locale
import android.content.pm.ActivityInfo
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.systemBarsPadding
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowInsetsControllerCompat
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.viewinterop.AndroidView
import androidx.activity.result.contract.ActivityResultContracts
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
                val paddingModifier = if (AppConfig.hideSystemBars) Modifier else Modifier.systemBarsPadding()
                Box(modifier = Modifier.fillMaxSize().then(paddingModifier)) {
                    Html2ApkWebView(startUrl = START_URL, modifier = Modifier.fillMaxSize())
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
        val statusBarBackground = AppConfig.statusBarBackground.trim().lowercase()
        val drawBehind = statusBarBackground == "transparent"
        WindowCompat.setDecorFitsSystemWindows(window, !drawBehind)
        window.statusBarColor = if (drawBehind) Color.TRANSPARENT else Color.WHITE

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
    val orientationMode = AppConfig.orientationMode

    val fileChooserLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.StartActivityForResult(),
    ) { result ->
        val uris = WebChromeClient.FileChooserParams.parseResult(result.resultCode, result.data)
        pendingFileCallback?.onReceiveValue(uris)
        pendingFileCallback = null
    }

    val webView = remember {
        WebView(context).apply {
            layoutParams = ViewGroup.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT,
            )
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = true
            settings.useWideViewPort = true
            settings.loadWithOverviewMode = true
            settings.cacheMode = WebSettings.LOAD_DEFAULT
            settings.allowFileAccess = true
            settings.allowContentAccess = true
            settings.allowFileAccessFromFileURLs = true
            settings.allowUniversalAccessFromFileURLs = false
            setInitialScale(0)

            addJavascriptInterface(DownloadBridge(context), "AndroidDownload")

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
      if (href.startsWith('blob:') && window.AndroidDownload && window.AndroidDownload.saveBlob) {
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

private class DownloadBridge(private val context: android.content.Context) {
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

            val resolver = context.contentResolver
            val values = ContentValues().apply {
                put(MediaStore.Downloads.DISPLAY_NAME, filename)
                put(MediaStore.Downloads.MIME_TYPE, mimeType)
                put(MediaStore.Downloads.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS)
            }
            val uri = resolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, values)
            if (uri != null) {
                resolver.openOutputStream(uri)?.use { it.write(bytes) }
                Toast.makeText(context, "已保存到下载: $filename", Toast.LENGTH_SHORT).show()
            } else {
                Toast.makeText(context, "保存失败: 无法创建文件", Toast.LENGTH_SHORT).show()
            }
        } catch (e: Exception) {
            Toast.makeText(context, "保存失败: ${e.message}", Toast.LENGTH_SHORT).show()
        }
    }
}
