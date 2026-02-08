package com.jmin.tubbim

import androidx.activity.result.contract.ActivityResultContracts
import android.webkit.ValueCallback
import android.net.Uri
import android.content.Intent
import android.app.Activity
import android.annotation.SuppressLint
import android.os.Bundle
import android.view.View
import android.view.WindowManager
import android.widget.Toast
import android.webkit.CookieManager
import android.graphics.Color
import android.webkit.WebChromeClient
import android.webkit.WebChromeClient.FileChooserParams
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.webkit.WebResourceRequest
import android.app.DownloadManager
import android.os.Environment
import androidx.activity.OnBackPressedCallback
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowInsetsControllerCompat
import androidx.core.view.ViewCompat
import com.jmin.tubbim.utils.AppConfig
import com.jmin.tubbim.utils.SystemBarsConfig


class MainActivity : AppCompatActivity() {
    private lateinit var webView: WebView
    private var lastBackPressAt: Long = 0L
    private var filePathCallback: ValueCallback<Array<Uri>>? = null
    private val fileChooserLauncher = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { result ->
        val callback = filePathCallback
        if (callback == null) return@registerForActivityResult
        val uris = if (result.resultCode == Activity.RESULT_OK) {
            val data = result.data
            val clipData = data?.clipData
            when {
                clipData != null -> Array(clipData.itemCount) { idx -> clipData.getItemAt(idx).uri }
                data?.data != null -> arrayOf(data.data!!)
                else -> emptyArray()
            }
        } else {
            emptyArray()
        }
        callback.onReceiveValue(uris)
        filePathCallback = null
    }

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        applySystemBarsConfig(AppConfig.systemBars)

        // 创建WebView
        webView = WebView(this)
        setContentView(webView)
        webView.clipToPadding = false
        applyNavigationInsets()

        // 配置WebView设置
        val webSettings: WebSettings = webView.settings
        webSettings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            javaScriptCanOpenWindowsAutomatically = true
            loadWithOverviewMode = true
            useWideViewPort = true
            setSupportMultipleWindows(false)
            builtInZoomControls = false
            displayZoomControls = false
            setSupportZoom(false)
            cacheMode = WebSettings.LOAD_DEFAULT
            allowFileAccess = true
            allowContentAccess = true
            mixedContentMode = WebSettings.MIXED_CONTENT_ALWAYS_ALLOW
        }
        when (AppConfig.webViewUaMode) {
            "pc" -> webSettings.userAgentString = AppConfig.desktopUserAgent
            else -> webSettings.userAgentString = WebSettings.getDefaultUserAgent(this)
        }
        CookieManager.getInstance().apply {
            setAcceptCookie(true)
            setAcceptThirdPartyCookies(webView, true)
        }

        // 设置WebViewClient和WebChromeClient
        webView.apply {
            isVerticalScrollBarEnabled = false
            isHorizontalScrollBarEnabled = false
            overScrollMode = View.OVER_SCROLL_NEVER
            setBackgroundColor(Color.TRANSPARENT)
            setOnLongClickListener { true }
            setOnTouchListener { _, event ->
                event.pointerCount > 1
            }
            webViewClient = object : WebViewClient() {
                override fun shouldOverrideUrlLoading(view: WebView?, request: WebResourceRequest?): Boolean {
                    val url = request?.url ?: return false
                    val scheme = url.scheme ?: return false
                    if (scheme == "http" || scheme == "https") {
                        view?.loadUrl(url.toString())
                        return true
                    }
                    return try {
                        startActivity(Intent(Intent.ACTION_VIEW, url))
                        true
                    } catch (_: Exception) {
                        false
                    }
                }

                override fun onPageFinished(view: WebView?, url: String?) {
                    super.onPageFinished(view, url)
                    injectFilePickerPolyfill()
                }
            }
            webChromeClient = object : WebChromeClient() {
                override fun onShowFileChooser(
                    webView: WebView?,
                    filePathCallback: ValueCallback<Array<Uri>>?,
                    fileChooserParams: FileChooserParams?
                ): Boolean {
                    this@MainActivity.filePathCallback?.onReceiveValue(null)
                    this@MainActivity.filePathCallback = filePathCallback
                    val acceptTypes = fileChooserParams?.acceptTypes
                        ?.mapNotNull { it?.trim() }
                        ?.filter { it.isNotEmpty() }
                        ?: emptyList()
                    val allowMultiple = fileChooserParams?.mode == FileChooserParams.MODE_OPEN_MULTIPLE
                    val intent = Intent(Intent.ACTION_OPEN_DOCUMENT).apply {
                        addCategory(Intent.CATEGORY_OPENABLE)
                        addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                        type = if (acceptTypes.size == 1) acceptTypes[0] else "*/*"
                        if (acceptTypes.size > 1) {
                            putExtra(Intent.EXTRA_MIME_TYPES, acceptTypes.toTypedArray())
                        }
                        putExtra(Intent.EXTRA_ALLOW_MULTIPLE, allowMultiple)
                    }
                    val chooserTitle = fileChooserParams?.title ?: "选择文件"
                    val chooser = Intent.createChooser(intent, chooserTitle)
                    return try {
                        fileChooserLauncher.launch(chooser)
                        true
                    } catch (e: Exception) {
                        this@MainActivity.filePathCallback = null
                        false
                    }
                }
            }
            // 加载H5游戏地址
            loadUrl(AppConfig.webViewUrl)
        }
        webView.setDownloadListener { url, userAgent, _, mimeType, _ ->
            try {
                val request = DownloadManager.Request(Uri.parse(url))
                request.setMimeType(mimeType)
                request.addRequestHeader("User-Agent", userAgent)
                request.setTitle("下载文件")
                request.setDescription(url)
                request.setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED)
                request.setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS, "download")
                val dm = getSystemService(DOWNLOAD_SERVICE) as DownloadManager
                dm.enqueue(request)
            } catch (_: Exception) {
            }
        }

        onBackPressedDispatcher.addCallback(
            this,
            object : OnBackPressedCallback(true) {
                override fun handleOnBackPressed() {
                    if (::webView.isInitialized && webView.canGoBack()) {
                        webView.goBack()
                        return
                    }
                    if (!AppConfig.doubleClickExit) {
                        finish()
                        return
                    }
                    val now = System.currentTimeMillis()
                    if (now - lastBackPressAt <= 2000) {
                        finish()
                    } else {
                        lastBackPressAt = now
                        Toast.makeText(this@MainActivity, "再按一次退出应用", Toast.LENGTH_SHORT).show()
                    }
                }
            }
        )
    }

    private fun injectFilePickerPolyfill() {
        val script = """
            (function() {
              if (window.__capFilePickerPatched) return;
              window.__capFilePickerPatched = true;
              function makeFileHandle(file) {
                return {
                  kind: 'file',
                  name: file.name,
                  getFile: function() { return Promise.resolve(file); }
                };
              }
              function makeDirHandle(files) {
                var fileHandles = (files || []).map(makeFileHandle);
                var entries = fileHandles.map(function(h) { return [h.name, h]; });
                return {
                  kind: 'directory',
                  name: 'selected',
                  entries: function() {
                    var i = 0;
                    return {
                      [Symbol.asyncIterator]: function() { return this; },
                      next: function() {
                        if (i < entries.length) return Promise.resolve({ value: entries[i++], done: false });
                        return Promise.resolve({ done: true });
                      }
                    };
                  },
                  values: function() {
                    var i = 0;
                    return {
                      [Symbol.asyncIterator]: function() { return this; },
                      next: function() {
                        if (i < fileHandles.length) return Promise.resolve({ value: fileHandles[i++], done: false });
                        return Promise.resolve({ done: true });
                      }
                    };
                  },
                  getFileHandle: function(name) {
                    var found = fileHandles.find(function(h) { return h.name === name; });
                    return found ? Promise.resolve(found) : Promise.reject(new Error('Not found'));
                  },
                  queryPermission: function() { return Promise.resolve('granted'); },
                  requestPermission: function() { return Promise.resolve('granted'); }
                };
              }
              function pickFiles(options, directory) {
                return new Promise(function(resolve, reject) {
                  try {
                    var input = document.createElement('input');
                    input.type = 'file';
                    input.style.display = 'none';
                    if (directory) {
                      input.setAttribute('webkitdirectory', '');
                      input.setAttribute('directory', '');
                    }
                    if (options && options.multiple) input.multiple = true;
                    var accept = [];
                    if (options && Array.isArray(options.types)) {
                      options.types.forEach(function(t) {
                        if (t && t.accept) {
                          Object.keys(t.accept).forEach(function(mime) {
                            accept.push(mime);
                            (t.accept[mime] || []).forEach(function(ext) { accept.push(ext); });
                          });
                        }
                      });
                    }
                    if (accept.length) input.accept = accept.join(',');
                    document.body.appendChild(input);
                    input.addEventListener('change', function() {
                      var files = Array.prototype.slice.call(input.files || []);
                      document.body.removeChild(input);
                      if (!files.length) {
                        reject(new Error('No file selected'));
                        return;
                      }
                      resolve(files);
                    }, { once: true });
                    input.click();
                  } catch (e) {
                    reject(e);
                  }
                });
              }
              if (!window.showOpenFilePicker) {
                window.showOpenFilePicker = function(options) {
                  return pickFiles(options, false).then(function(files) {
                    return files.map(makeFileHandle);
                  });
                };
              }
              if (!window.showDirectoryPicker) {
                window.showDirectoryPicker = function(options) {
                  return pickFiles(options, true).then(function(files) {
                    return makeDirHandle(files);
                  });
                };
              }
            })();
        """.trimIndent()
        webView.evaluateJavascript(script, null)
    }

override fun onWindowFocusChanged(hasFocus: Boolean) {
        super.onWindowFocusChanged(hasFocus)
        if (hasFocus) {
            applySystemBarsConfig(AppConfig.systemBars)
        }
    }

    override fun onDestroy() {
        webView.destroy()
        super.onDestroy()
    }

    private fun applyNavigationInsets() {
        val root = window.decorView
        val drawBehindStatusBar = AppConfig.systemBars.drawBehindStatusBar
        val hideStatusBar = AppConfig.systemBars.hideStatusBar
        ViewCompat.setOnApplyWindowInsetsListener(root) { _, insets ->
            val nav = insets.getInsets(WindowInsetsCompat.Type.navigationBars())
            val status = insets.getInsets(WindowInsetsCompat.Type.statusBars())
            val topInset = if (drawBehindStatusBar && !hideStatusBar) status.top else 0
            webView.setPadding(nav.left, topInset, nav.right, nav.bottom)
            webView.post {
                val script = "(function(){var t=" + topInset + ";var b=" + nav.bottom +
                    ";var root=document.documentElement;" +
                    "root.style.boxSizing='border-box';root.style.paddingTop=t+'px';root.style.paddingBottom=b+'px';" +
                    "if(document.body){document.body.style.boxSizing='border-box';document.body.style.paddingTop=t+'px';document.body.style.paddingBottom=b+'px';}" +
                    "})();"
                webView.evaluateJavascript(script, null)
            }
            insets
        }
        ViewCompat.requestApplyInsets(root)
    }

    private fun applySystemBarsConfig(config: SystemBarsConfig) {
        // 透明状态栏一般需要“内容绘制到状态栏下方”
        WindowCompat.setDecorFitsSystemWindows(window, !config.drawBehindStatusBar)

        @Suppress("DEPRECATION")
        window.statusBarColor = config.statusBarColor

        val controller = WindowInsetsControllerCompat(window, window.decorView)
        controller.isAppearanceLightStatusBars = config.lightStatusBarIcons

        if (config.hideStatusBar) {
            window.addFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN)
            window.clearFlags(WindowManager.LayoutParams.FLAG_FORCE_NOT_FULLSCREEN)
            @Suppress("DEPRECATION")
            window.decorView.systemUiVisibility =
                View.SYSTEM_UI_FLAG_FULLSCREEN or View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
            controller.systemBarsBehavior =
                WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
            controller.hide(WindowInsetsCompat.Type.statusBars())
        } else {
            window.clearFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN)
            window.addFlags(WindowManager.LayoutParams.FLAG_FORCE_NOT_FULLSCREEN)
            @Suppress("DEPRECATION")
            window.decorView.systemUiVisibility =
                if (config.lightStatusBarIcons) {
                    View.SYSTEM_UI_FLAG_VISIBLE or View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR
                } else {
                    View.SYSTEM_UI_FLAG_VISIBLE
                }
            controller.show(WindowInsetsCompat.Type.statusBars())
        }
    }
}
