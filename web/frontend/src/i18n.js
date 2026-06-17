/**
 * 国际化配置
 * 支持：英文(en)、简体中文(zh-CN)、繁体中文(zh-TW)
 */

export const messages = {
  'en': {
    // Header
    header: {
      title: 'APK Converter',
      subtitle: 'Web App → Android APK',
      refresh: 'Refresh'
    },
    mobileNav: {
      settings: 'Settings'
    },
    github: {
      star: 'Github Stars',
      starTitle: 'Open the Github project and leave a star'
    },
    // Mode
    mode: {
      title: 'Conversion Mode',
      apk: 'Project to APK',
      web: 'Website to APK',
      html: 'HTML to APK',
      desktop: 'ZIP to Desktop'
    },
    // Guide
    guide: {
      title: 'Quick Guide',
      subtitle: 'How to generate APK',
      step1: 'Create App in Google AI Studio',
      step2: 'Export project as ZIP',
      step3: 'Upload here & Build APK',
      openAiStudio: 'Open AI Studio',
      tips: 'Tip: when exporting. If your app uses camera, import/export (download), tell Gemini: "this feature needs Capacitor adaptation".'
    },
    // 新手引导
    onboarding: {
      kicker: 'First build',
      title: 'Turn a web project into an installable app',
      subtitle: 'Follow the three-step path below: upload your ZIP, confirm app details, then build and download the APK.',
      primaryAction: 'Start first build',
      requirementsAction: 'Packaging requirements',
      flowLabel: 'First build workflow',
      stepUploadTitle: 'Upload project ZIP',
      stepUploadText: 'Use the exported web project or a static HTML package.',
      stepConfigTitle: 'Confirm app info',
      stepConfigText: 'Set app name, package name, version, icon and optional signing.',
      stepBuildTitle: 'Build and download',
      stepBuildText: 'Track logs in real time and download the output after success.',
      materialsTitle: 'Prepare these before starting',
      materialZip: 'Project ZIP',
      materialName: 'App name',
      materialPackage: 'Package name',
      materialIcon: '512x512 icon',
      previewLabel: 'Example task preview',
      previewTitle: 'Example app task',
      previewText: 'Your completed builds will appear here with logs and downloads.',
      previewStatus: 'Ready'
    },
    // Steps
    steps: {
      upload: 'Upload Project',
      configure: 'Configure App',
      build: 'Build APK',
      buildDesktop: 'Build Desktop App'
    },
    // Upload
    upload: {
      title: 'Project File',
      subtitle: 'Upload ZIP exported from Google AI Studio',
      dragDrop: 'Drag & drop ZIP file here, or click to select',
      hint: 'Supports React, Vue and other frontend projects',
      desktopTitle: 'Electron Project ZIP',
      desktopSubtitle: 'Upload a ZIP project and package it as a Windows desktop app',
      desktopDragDrop: 'Drag & drop ZIP file here, or click to select',
      desktopHint: 'Supports frontend projects with package.json or static HTML assets',
      ready: 'File Ready',
      selectNew: 'Select New'
    },
    web: {
      url: 'Website URL',
      urlPlaceholder: 'https://www.example.com',
      urlHint: 'You can omit http/https; we will auto-detect',
      validUrlError: 'Please enter a valid URL',
      urlUnreachable: 'URL is not reachable',
      enableAds: 'Enable Topon Ads (Experimental)',
      adConfig: 'Ad Configuration',
      toponAppId: 'Topon App ID',
      toponAppKey: 'Topon App Key',
      placementId: 'Placement ID (Reward Video)',
      jsIntegration: 'JS Integration Guide',
      copyCode: 'Copy Code',
      codeCopied: 'Copied!'
    },
    html: {
      title: 'HTML File',
      subtitle: 'Upload your HTML entry file',
      upload: 'Upload HTML',
      modeFile: 'File',
      modeEdit: 'Edit',
      editorTitle: 'HTML Editor',
      editorSave: 'Save',
      editorSaving: 'Uploading...',
      editorLoading: 'Loading editor...',
      editorSaved: 'Saved',
      editorUnsaved: 'Unsaved changes',
      editorEmpty: 'Please enter HTML content',
      saveBeforeBuild: 'Please save the HTML before building',
      fixErrors: 'Please fix {count} syntax error(s)',
      fullscreen: 'Fullscreen',
      exitFullscreen: 'Exit fullscreen',
      editorModalOpen: 'Editor is open in fullscreen mode.',
      issues: '{count} issues',
      noIssues: 'No issues',
      issueError: 'Error',
      issueWarning: 'Warning',
      syntaxError: 'Syntax error',
      tagMismatch: 'Tag mismatch: expected </{expected}> but found </{found}>',
      tagUnexpectedClose: 'Unexpected closing tag: </{name}>',
      tagMissingClose: 'Missing closing tag for <{name}>',
      dragDrop: 'Drag & drop HTML file here, or click to select',
      hint: 'HTML entry file is required',
      ready: 'HTML Ready',
      htmlRequired: 'Please upload an HTML file',
      reuseHtml: 'Use previous HTML file',
      preview: 'Preview',
      previewTitle: 'App Preview',
      closePreview: 'Close',
      previewUnavailable: 'No HTML content available for preview',
    },
    cdnLocalize: {
      title: 'CDN External Link Localization',
      scanning: 'Scanning external assets...',
      detected: 'Detected {total} external links, selected {selected}. We recommend enabling localization to avoid missing styles on first offline launch.',
      noLinks: 'No external links detected. Import a new file and rescan.',
      enable: 'Enable localization',
      rescan: 'Rescan',
      selectLinks: 'Select links',
      dialogTitle: 'Select external links to localize',
      selectAll: 'Select all',
      clear: 'Clear',
      selectedCount: 'Selected {selected} / {total}',
      empty: 'No localizable external links detected',
      tip: 'Keep localization enabled to avoid missing styles when first launching offline.',
      done: 'Done',
      occurrences: '{count} references',
      fileCount: '{count} files',
      scanFailed: 'External link scan failed. Switched to localize all external links.',
      rescanReuseConvert: 'Cannot rescan when reusing history task. Please re-upload project file.',
      rescanReuseHtml: 'Cannot rescan when reusing history task. Please re-upload HTML file.',
      type: {
        other: 'other',
        css: 'css',
        script: 'script',
        font: 'font',
        image: 'image',
        media: 'media',
        mixed: 'mixed'
      }
    },
    // Config
    config: {
      title: 'App Configuration',
      updateTitle: 'Update App',
      subtitle: 'Set app basic info and icon',
      updateSubtitle: 'Update "{name}"',
      cancelUpdate: 'Cancel Update',
      appName: 'App Name',
      appNamePlaceholder: 'e.g. My App',
      packageName: 'Package Name',
      packageNamePlaceholder: 'e.g. com.example.myapp',
      packageNameRule: 'Use Android package name: lowercase letters/digits/underscore, dot-separated, each segment starts with a letter (e.g. com.example.app).',
      versionName: 'Version Name',
      versionCode: 'Version Code',
      minVersion: 'Min: {version}',
      outputFormat: 'Output Format',
      apk: 'APK (Direct Install)',
      aab: 'AAB (Google Play)',
      desktopInstallerMode: 'Desktop Installer Mode',
      desktopInstallerPortable: 'Portable (.exe)',
      desktopInstallerNsisWeb: 'Web Installer (NSIS-Web)',
      signConfig: 'Signing Configuration (Optional)',
      signConfigHint: 'If upgrading an existing app, it is recommended to upload your own keystore.',
      keystoreAlias: 'Key Alias',
      keystorePassword: 'Keystore Password',
      keyPassword: 'Key Password',
      keystorePasswordRule: 'Keystore password must be at least 6 characters.',
      keyPasswordRule: 'Key password must be at least 6 characters.',
      keystoreUpload: 'Upload Keystore',
      keystoreUploadToggle: 'Use custom keystore',
      keystoreChoose: 'Choose File',
      keystoreRemove: 'Remove',
      keystoreUploadWarning: 'Using your own keystore: please bump the app version to avoid install conflicts.',
      keystoreUploadInvalid: 'Only .jks or .keystore files are allowed.',
      keystoreUploadSuccess: 'Keystore uploaded successfully.',
      keystoreUploadFailed: 'Keystore upload failed',
      keystoreUploadNotAllowed: 'Keystore upload is not available when updating an existing task.',
      keystoreUpgradePackageHint: 'When upgrading an existing app, ensure the package name is exactly the same.',
      // APK Style
      styleTitle: 'APK Style',
      orientation: 'Screen Orientation',
      orientationPortrait: 'Portrait',
      orientationLandscape: 'Landscape',
      orientationAuto: 'Auto (System)',
      doubleClickExit: 'Double click Back to exit',
      downloadMode: 'Export/Download Mode',
      downloadModeSilent: 'Silent Export',
      downloadModePicker: 'File Picker (Explorer)',
      webFillMode: 'Page Fill Strategy',
      webFillModeContain: 'Contain (Recommended)',
      webFillModeCover: 'Cover (Game Scene)',
      statusBarTitle: 'Status Bar',
      statusBarHidden: 'Hide Status Bar (Fullscreen)',
      statusBarColor: 'Status Bar Color',
      statusBarColorHiddenHint: 'Disabled while fullscreen status bar hiding is enabled.',
      statusBarBackground: 'Background',
      statusBarTransparent: 'Transparent',
      statusBarWhite: 'White',
      statusBarStyle: 'Icon Style',
      statusBarStyleDark: 'Dark Icons',
      statusBarStyleLight: 'Light Icons',
      webviewUserAgent: 'WebView User-Agent',
      webviewUserAgentAndroid: 'Android (Default)',
      webviewUserAgentPc: 'PC (Desktop Browser)',
      permissionsTitle: 'App Permissions',
      enablePermissions: 'Request Additional Permissions',
      permissionsHint: 'Check to configure AndroidManifest.xml permissions',
      perm: {
        INTERNET: 'Access Internet',
        ACCESS_NETWORK_STATE: 'View Network State',
        ACCESS_WIFI_STATE: 'View Wi-Fi State',
        CAMERA: 'Camera',
        READ_EXTERNAL_STORAGE: 'Read Storage',
        WRITE_EXTERNAL_STORAGE: 'Write Storage',
        ACCESS_FINE_LOCATION: 'Precise Location (GPS)',
        ACCESS_COARSE_LOCATION: 'Approximate Location',
        RECORD_AUDIO: 'Record Audio',
        READ_PHONE_STATE: 'Read Phone State',
        CALL_PHONE: 'Make Phone Calls',
        READ_CONTACTS: 'Read Contacts',
        WRITE_CONTACTS: 'Write Contacts',
        VIBRATE: 'Vibrate',
        WAKE_LOCK: 'Prevent Sleep',
        RECEIVE_BOOT_COMPLETED: 'Run at Startup',
        FOREGROUND_SERVICE: 'Foreground Service',
        REQUEST_INSTALL_PACKAGES: 'Install Apps',
        SYSTEM_ALERT_WINDOW: 'Display Over Other Apps',
        BLUETOOTH: 'Bluetooth',
        BLUETOOTH_ADMIN: 'Bluetooth Admin',
        NFC: 'NFC',
        READ_CALENDAR: 'Read Calendar',
        WRITE_CALENDAR: 'Write Calendar'
      },
      createTask: 'Create Build Task',
      updateTask: 'Update & Rebuild',
      creating: 'AI Risk Review in Progress...',
      updateMode: 'Update Mode',
      updateHint: 'Updating existing app, will reuse signing key',
      quickGenerate: 'One-click Generate',
      quickGenerateHint: 'Hide the form and use system-generated defaults',
      quickGenerateModeCustom: 'Custom',
      quickGenerateModeQuick: 'One-click',
      quickGenerateEnabled: 'One-click Generate Enabled',
      quickGenerateDesc: 'All app configuration fields are hidden; defaults will be generated by the system.',
      quickGenerateAuto: 'Auto-increment',
      quickGenerateAllPermissions: 'All permissions'
    },
    // Icon
    icon: {
      title: 'App Icon',
      required: '(Required)',
      uploadHint: 'Click to upload',
      change: 'Change',
      requirements: 'Requirements: 1024×1024 PNG, auto-crop supported'
    },
    // Cropper
    cropper: {
      title: 'Crop Icon',
      hint: 'Drag to select area, output: 1024 × 1024 px',
      cancel: 'Cancel',
      confirm: 'Confirm'
    },
    // Tasks
    tasks: {
      title: 'Build Tasks',
      subtitle: 'View and manage all tasks',
      total: 'Total',
      completed: 'Completed',
      running: 'Running',
      queued: 'Queued',
      noTasks: 'No build tasks',
      createFirst: 'Upload a project and configure to create your first task',
      version: 'v{version}',
      useConfig: 'Use Config',
      viewLogs: 'View Logs',
      retry: 'Retry',
      cancel: 'Cancel',
      start: 'Start Build',
      download: 'Download Product',
      downloadMenu: 'Download Menu',
      downloadSigned: 'Download Keystore',
      delete: 'Delete',
      confirmDelete: 'Delete this task?',
      waiting: 'Waiting',
      jump: 'Jump to',
      go: 'Go',
      newBadge: 'New',
      retryBadge: 'Retry'
    },
    // Status
    status: {
      pending: 'Pending',
      processing: 'Building',
      success: 'Success',
      failed: 'Failed',
      queued: 'Queued ({count} ahead)'
    },
    // Logs
    logs: {
      title: 'Build Logs',
      taskId: 'Task ID',
      loading: 'Loading logs...',
      noLogs: 'No log records',
      close: 'Close'
    },
    // Toast
    toast: {
      uploadSuccess: 'File uploaded successfully',
      uploadFailed: 'Upload failed',
      uploadTooLarge: 'The selected file is {size}, which exceeds the current upload limit of {limit}. Please compress it and try again.',
      taskCreated: 'Build task created',
      taskStarted: 'Build task started',
      desktopModeDisabled: 'Electron desktop mode is disabled',
      nativeModeDisabled: 'Native Android packaging mode is disabled',
      firstBuildHint: 'First build may take around 15 minutes. Later builds should be faster.',
      taskRetried: 'Task reset, please start again',
      taskDeleted: 'Task deleted',
      iconRequired: 'Please upload app icon',
      versionError: 'Version must be greater than previous',
      error: 'Operation failed',
      updateOpened: 'Update download opened',
      feedbackFileLimit: 'Only 5 images max and 10MB each',
      feedbackEmpty: 'Please enter feedback',
      feedbackSent: 'Feedback submitted',
      feedbackFailed: 'Feedback submission failed',
      feedbackCooldown: 'Please wait before sending again',
      feedbackDailyLimit: 'Daily feedback limit reached',
      saved: 'Saved',
      iconSet: 'Icon updated',
      iconUploadFailed: 'Icon upload failed',
      startFailed: 'Failed to start task',
      retryFailed: 'Failed to retry task',
      cancelFailed: 'Failed to cancel task',
      deleteFailed: 'Failed to delete task',
      operationFailed: 'Operation failed',
      cancelConfirm: 'Cancel this task?',
      deleteConfirm: 'Delete this task?'
    },
    donation: {
      title: 'Support the developer',
      button: 'Support',
      message: 'If you find this useful, consider buying the developer a milk tea.',
      subMessage: 'Every little bit helps. Thank you for your support!',
      alipay: 'Alipay',
      wechat: 'WeChat',
      hide: "Don't show again"
    },
    // Environment
    env: {
      missing: 'Build environment missing',
      missingList: 'Missing',
      preparing: 'Preparing environment...',
      fix: 'Fix Now',
      ready: 'Environment ready',
      failed: 'Environment setup failed',
      missingToast: 'Build environment is not ready',
      port: 'Backend Port',
      python: 'Python',
      quickFixHint: 'Prefer Quick Fix to avoid version conflicts. Manual paths are advanced.',
      manualSetup: 'Manual Paths',
      manualHint: 'If you must, fill in paths below (Quick Fix is still recommended).',
      nodePath: 'Node.js Path',
      jdkPath: 'JDK Path',
      androidPath: 'Android SDK Path',
      pythonPath: 'Python Path'
    },
    announcement: {
      title: 'Announcement',
      dismiss: 'Dismiss'
    },
    settings: {
      title: 'Report Bug',
      toolchainSection: 'Toolchain',
      toolchainRoot: 'Toolchain Root',
      toolchainHint: 'Avoid installing under Program Files if possible.',
      npmRegistry: 'NPM Registry',
      npmProxy: 'NPM Proxy',
      npmHttpsProxy: 'NPM HTTPS Proxy',
      dataRoot: 'Data Root',
      dataRootPlaceholder: 'D:\\ConvertAPK\\data',
      dataRootHint: 'Data storage path for tasks/cache/output. Leave empty to use default.',
      selectDir: 'Choose Folder',
      envSection: 'Environment Paths',
      migrateToolchain: 'Move existing toolchain to new path',
      updateSection: 'Updates',
      updateMode: 'Update Mode',
      updateSilent: 'Silent update',
      updatePrompt: 'Prompt before update',
      updateNotify: 'Notify only',
      currentVersion: 'Current version: {version}',
      checkUpdate: 'Check for updates',
      feedbackSection: 'Feedback',
      feedbackDevice: 'Device: {cpu} ({cores} cores) | {ram} | {os}',
      recommendedSpec: 'Recommended: 4+ Cores, 8GB+ RAM',
      feedbackPlaceholder: 'Describe your issue or suggestion...',
      feedbackHint: 'Up to 5 images, 10MB each',
      feedbackSubmitting: 'Submitting...',
      selectImages: 'Select Images',
      noImagesSelected: 'No images selected',
      imagesSelected: '{count} images selected',
      feedbackSubmit: 'Submit feedback',
      aboutSection: 'About',
      aboutDeveloper: 'Developer: @Jmin',
      aboutContact: 'Email: lzm1150772572@gmail.com',
      cancel: 'Cancel',
      save: 'Save',
      saving: 'Saving...'
    },
    updateDialog: {
      title: 'Update Available',
      versionLabel: 'Version',
      notesLabel: 'Release notes',
      noNotes: 'No release notes',
      later: 'Later',
      download: 'Download'
    },
    tip: {
      title: 'Support the developer',
      subtitle: 'Build completed for {name}. If this tool helps you, a small tip keeps it going.',
      defaultApp: 'your app',
      wechat: 'WeChat Pay',
      alipay: 'Alipay',
      note: 'Tips are optional. You can close this anytime.',
      close: 'Close',
      thanks: 'I have tipped'
    },
    firstBuild: {
      title: 'First build may take longer',
      body: 'The first build can take around 15 minutes to download toolchains and dependencies. Later builds are usually much faster.',
      ok: 'Got it'
    },
    window: {
      closePrompt: 'Builds are still running. Exit and cancel the current task?'
    },
    // Theme
    theme: {
      light: 'Light',
      dark: 'Dark'
    },
    // Language
    language: {
      en: 'English',
      'zh-CN': '简体中文',
      'zh-TW': '繁體中文'
    }
  },
  
  'zh-CN': {
    // Header
    header: {
      title: 'APK Converter',
      subtitle: 'Web App → Android APK',
      refresh: '刷新'
    },
    mobileNav: {
      settings: '设置'
    },
    github: {
      star: 'Github Stars',
      starTitle: '打开 Github 项目并点亮 Star'
    },
    // Mode
    mode: {
      title: '转换模式',
      apk: '项目转 APK',
      web: '网页转 APK',
      html: 'HTML 转 APK',
      desktop: 'ZIP 转桌面应用'
    },
    // Guide
    guide: {
      title: '使用指南',
      subtitle: '如何生成 APK',
      step1: '在 Google AI Studio 创建应用',
      step2: '导出项目为 ZIP 包',
      step3: '在此处上传并构建 APK',
      openAiStudio: '打开 AI Studio',
      tips: '提示：如果应用中包含相机、导入/导出（下载）等功能，请在 Google AI Studio 提示 Gemini：“相机、导入/导出（下载）等功能需要做 Capacitor 适配”。'
    },
    // 新手引导
    onboarding: {
      kicker: '第一次构建',
      title: '把网页项目变成可安装应用',
      subtitle: '按下面三步走：上传 ZIP，确认应用信息，然后开始构建并下载 APK。',
      primaryAction: '开始第一个构建',
      requirementsAction: '查看打包要求',
      flowLabel: '首次构建流程',
      stepUploadTitle: '上传项目 ZIP',
      stepUploadText: '使用导出的网页项目，或准备好的静态 HTML 包。',
      stepConfigTitle: '确认应用信息',
      stepConfigText: '设置应用名称、包名、版本、图标和可选签名。',
      stepBuildTitle: '构建并下载',
      stepBuildText: '实时查看日志，成功后下载生成产物。',
      materialsTitle: '开始前准备这些材料',
      materialZip: '项目 ZIP',
      materialName: '应用名称',
      materialPackage: 'Android 包名',
      materialIcon: '512x512 图标',
      previewLabel: '示例任务预览',
      previewTitle: '示例应用任务',
      previewText: '你的构建任务会显示在这里，包含日志和下载入口。',
      previewStatus: '待创建'
    },
    // Steps
    steps: {
      upload: '上传项目',
      configure: '配置应用',
      build: '构建APK',
      buildDesktop: '构建桌面应用'
    },
    // Upload
    upload: {
      title: '项目文件',
      subtitle: '上传 Google AI Studio 导出的 ZIP 包',
      dragDrop: '拖放 ZIP 文件到此处，或点击选择',
      hint: '支持 React、Vue 等前端项目',
      desktopTitle: 'Electron 项目 ZIP',
      desktopSubtitle: '上传 ZIP 项目并打包为 Windows 桌面应用',
      desktopDragDrop: '拖放 ZIP 文件到此处，或点击选择',
      desktopHint: '支持包含 package.json 的前端项目或纯静态 HTML 资源',
      ready: '文件已就绪',
      selectNew: '选择新文件'
    },
    web: {
      url: '网页地址',
      urlPlaceholder: 'https://www.example.com',
      urlHint: '可不带 http/https，系统会自动补全并测试',
      validUrlError: '请输入有效的网址',
      urlUnreachable: '网址无法访问，请检查是否可用',
      enableAds: '启用 Topon 广告（试验版）',
      adConfig: '广告配置',
      toponAppId: 'Topon App ID',
      toponAppKey: 'Topon App Key',
      placementId: '激励视频广告位 ID',
      jsIntegration: 'JS 集成代码示例',
      copyCode: '复制代码',
      codeCopied: '已复制!'
    },
    html: {
      title: 'HTML 文件',
      subtitle: '上传入口 HTML 文件',
      upload: '上传 HTML',
      modeFile: '文件',
      modeEdit: '编辑',
      editorTitle: 'HTML 编辑器',
      editorSave: '保存',
      editorSaving: '上传中...',
      editorLoading: '编辑器加载中...',
      editorSaved: '已保存',
      editorUnsaved: '未保存更改',
      editorEmpty: '请填写 HTML 内容',
      saveBeforeBuild: '请先保存 HTML 再创建构建任务',
      fixErrors: '请先修复 {count} 个语法错误',
      fullscreen: '大屏编辑',
      exitFullscreen: '退出大屏',
      editorModalOpen: '编辑器已在大屏窗口中打开。',
      issues: '{count} 个问题',
      noIssues: '暂无问题',
      issueError: '错误',
      issueWarning: '警告',
      syntaxError: '语法错误',
      tagMismatch: '标签不匹配：应为 </{expected}>，但找到 </{found}>',
      tagUnexpectedClose: '多余的结束标签：</{name}>',
      tagMissingClose: '缺少结束标签：<{name}>',
      dragDrop: '拖拽 HTML 文件到此处，或点击选择',
      hint: '必须包含入口 HTML 文件',
      ready: 'HTML 已就绪',
      htmlRequired: '请上传 HTML 文件',
      reuseHtml: '使用上一版本的 HTML 文件',
      preview: '预览',
      previewTitle: 'APP 预览',
      closePreview: '关闭',
      previewUnavailable: '暂无可预览的 HTML 内容',
    },
    cdnLocalize: {
      title: 'CDN 外链本地化',
      scanning: '正在扫描外链资源...',
      detected: '检测到 {total} 条外链，已选 {selected} 条。建议开启本地化，避免 APP 首启离线时样式丢失。',
      noLinks: '当前未检测到外链资源。导入新文件后可重新扫描。',
      enable: '启用本地化',
      rescan: '重新扫描',
      selectLinks: '选择外链',
      dialogTitle: '选择需要本地化的外链资源',
      selectAll: '全选',
      clear: '清空',
      selectedCount: '已选 {selected} / {total}',
      empty: '未检测到可本地化的外链',
      tip: '建议保持本地化开启，避免 APP 首启离线时样式丢失。',
      done: '完成',
      occurrences: '{count} 次引用',
      fileCount: '{count} 个文件',
      scanFailed: '外链扫描失败，已切换为全部外链本地化。',
      rescanReuseConvert: '复用历史任务时无法重新扫描，请重新上传项目文件。',
      rescanReuseHtml: '复用历史任务时无法重新扫描，请重新上传 HTML 文件。',
      type: {
        other: '其他',
        css: '样式',
        script: '脚本',
        font: '字体',
        image: '图片',
        media: '媒体',
        mixed: '混合'
      }
    },
    // Config
    config: {
      title: '应用配置',
      updateTitle: '更新应用',
      subtitle: '设置应用基本信息和图标',
      updateSubtitle: '更新 "{name}"',
      cancelUpdate: '取消更新',
      appName: '应用名称',
      appNamePlaceholder: '例如：我的应用',
      packageName: '包名',
      packageNamePlaceholder: '例如：com.example.myapp',
      packageNameRule: '需符合 Android 包名规范：小写字母/数字/下划线，点号分隔，每段以字母开头（如 com.example.app）',
      versionName: '版本名称',
      versionCode: '版本号',
      minVersion: '最低: {version}',
      outputFormat: '输出格式',
      apk: 'APK (直接安装)',
      aab: 'AAB (Google Play)',
      desktopInstallerMode: '桌面安装器模式',
      desktopInstallerPortable: '便携版（Portable）',
      desktopInstallerNsisWeb: 'Web 安装器（NSIS-Web）',
      signConfigHint: '如果对已有应用做版本升级，建议上传自带签名文件。',
      signConfig: '签名配置 (可选)',
      keystoreAlias: '密钥别名',
      keystorePassword: '密钥库密码',
      keyPassword: '密钥密码',
      keystorePasswordRule: '密钥库密码至少 6 个字符',
      keyPasswordRule: '密钥密码至少 6 个字符',
      keystoreUpload: '上传签名文件',
      keystoreUploadToggle: '使用自带签名文件',
      keystoreChoose: '选择文件',
      keystoreRemove: '移除',
      keystoreUploadWarning: '使用自己的签名请注意提高应用版本，避免安装冲突。',
      keystoreUploadInvalid: '仅支持 .jks 或 .keystore 文件。',
      keystoreUploadSuccess: '签名文件上传成功。',
      keystoreUploadFailed: '签名文件上传失败',
      keystoreUploadNotAllowed: '更新任务时不支持上传签名文件。',
      keystoreUpgradePackageHint: '升级已有应用时请确保包名与之前完全一致。',
      // APK Style
      styleTitle: 'APK 样式',
      orientation: '屏幕方向',
      orientationPortrait: '强制竖屏',
      orientationLandscape: '强制横屏',
      orientationAuto: '跟随系统',
      doubleClickExit: '双击返回键退出应用',
      downloadMode: '导出/下载方式',
      downloadModeSilent: '静默导出',
      downloadModePicker: '资源管理器',
      webFillMode: '页面填充策略',
      webFillModeContain: '完整显示（推荐）',
      webFillModeCover: '铺满裁切（游戏场景）',
      statusBarTitle: '状态栏设置',
      statusBarHidden: '隐藏状态栏 (全屏)',
      statusBarColor: '状态栏颜色',
      statusBarColorHiddenHint: '已开启全屏隐藏状态栏，颜色设置暂不生效。',
      statusBarBackground: '背景颜色',
      statusBarTransparent: '透明',
      statusBarWhite: '白底',
      statusBarStyle: '图标风格',
      statusBarStyleDark: '深色图标',
      statusBarStyleLight: '浅色图标',
      webviewUserAgent: 'UA 标识',
      webviewUserAgentAndroid: '安卓（默认）',
      webviewUserAgentPc: 'PC',
      permissionsTitle: '应用权限',
      enablePermissions: '申请额外权限',
      permissionsHint: '勾选以配置 AndroidManifest.xml 权限',
      perm: {
        INTERNET: '访问网络',
        ACCESS_NETWORK_STATE: '查看网络状态',
        ACCESS_WIFI_STATE: '查看Wi-Fi状态',
        CAMERA: '使用相机',
        READ_EXTERNAL_STORAGE: '读取存储卡',
        WRITE_EXTERNAL_STORAGE: '写入存储卡',
        ACCESS_FINE_LOCATION: '精确位置 (GPS)',
        ACCESS_COARSE_LOCATION: '大致位置',
        RECORD_AUDIO: '录音',
        READ_PHONE_STATE: '读取手机状态',
        CALL_PHONE: '拨打电话',
        READ_CONTACTS: '读取联系人',
        WRITE_CONTACTS: '写入联系人',
        VIBRATE: '使用振动',
        WAKE_LOCK: '防止手机休眠',
        RECEIVE_BOOT_COMPLETED: '开机自启动',
        FOREGROUND_SERVICE: '前台服务',
        REQUEST_INSTALL_PACKAGES: '安装应用',
        SYSTEM_ALERT_WINDOW: '悬浮窗权限',
        BLUETOOTH: '使用蓝牙',
        BLUETOOTH_ADMIN: '管理蓝牙',
        NFC: '使用 NFC',
        READ_CALENDAR: '读取日历',
        WRITE_CALENDAR: '写入日历'
      },
      createTask: '创建构建任务',
      updateTask: '更新并重新构建',
      creating: 'AI风控审核中...',
      updateMode: '更新模式',
      updateHint: '正在更新已有应用，将复用原有签名密钥',
      quickGenerate: '一键生成',
      quickGenerateHint: '隐藏配置表单，使用系统默认生成配置',
      quickGenerateModeCustom: '自定义',
      quickGenerateModeQuick: '一键',
      quickGenerateEnabled: '已启用一键生成',
      quickGenerateDesc: '已隐藏全部应用配置表单，将使用系统默认配置并自动递增版本。',
      quickGenerateAuto: '系统自动递增',
      quickGenerateAllPermissions: '全部申请'
    },
    // Icon
    icon: {
      title: '应用图标',
      required: '(必填)',
      uploadHint: '点击上传',
      change: '更换',
      requirements: '要求: 1024×1024 PNG，支持自动裁切'
    },
    // Cropper
    cropper: {
      title: '裁切图标',
      hint: '拖动选择区域，输出尺寸：1024 × 1024 像素',
      cancel: '取消',
      confirm: '确认裁切'
    },
    // Tasks
    tasks: {
      title: '构建任务',
      subtitle: '查看和管理所有任务',
      total: '总任务',
      completed: '已完成',
      running: '运行中',
      queued: '排队',
      waiting: '等待中',
      noTasks: '暂无构建任务',
      createFirst: '上传项目文件并配置信息后创建第一个任务',
      version: 'v{version}',
      useConfig: '使用配置',
      viewLogs: '日志',
      retry: '重试',
      start: '开始构建',
      download: '下载产物',
      downloadMenu: '下载菜单',
      downloadSigned: '下载签名密钥',
      delete: '删除',
      cancel: '取消',
      jump: '跳转页码',
      go: '跳转',
      newBadge: '新建',
      retryBadge: '重试'
    },
    // Status
    status: {
      pending: '等待中',
      processing: '构建中',
      success: '成功',
      failed: '失败',
      queued: '排队中（前方{count}个）'
    },
    // Logs
    logs: {
      title: '构建日志',
      taskId: '任务ID',
      loading: '日志加载中...',
      noLogs: '暂无日志记录',
      close: '关闭'
    },
    // Toast
    toast: {
      uploadSuccess: '文件上传成功',
      uploadFailed: '上传失败',
      uploadTooLarge: '当前文件大小为 {size}，超过当前上传限制 {limit}，请压缩后重试。',
      taskCreated: '构建任务已创建',
      taskStarted: '构建任务已启动',
      desktopModeDisabled: 'Electron 桌面模式已关闭',
      nativeModeDisabled: '原生 Android 打包模式已关闭',
      firstBuildHint: '首次构建可能需要约 15 分钟，后续构建会更快。',
      taskRetried: '任务已重置，请重新开始',
      taskDeleted: '任务已删除',
      iconRequired: '请上传应用图标',
      versionError: '版本必须大于之前的值',
      error: '操作失败',
      updateOpened: '已打开更新下载链接',
      feedbackFileLimit: '附件最多 5 张且单张不超过 10MB',
      feedbackEmpty: '请填写反馈内容',
      feedbackSent: '反馈已提交',
      feedbackFailed: '反馈提交失败',
      feedbackCooldown: '提交过于频繁，请稍后再试',
      feedbackDailyLimit: '今日反馈次数已达上限',
      startFailed: '启动任务失败',
      retryFailed: '重试任务失败',
      cancelFailed: '取消任务失败',
      deleteFailed: '删除任务失败',
      operationFailed: '操作失败',
      cancelConfirm: '确定要取消这个任务吗？',
      deleteConfirm: '确定要删除这个任务吗？'
    },
      donation: {
        title: '支持开发者',
        button: '支持作者',
        message: '如果你觉得好用，不妨请开发者喝一杯奶茶。',
        subMessage: '小小心意，非常感谢支持！',
        alipay: '支付宝',
        wechat: '微信',
        hide: '不再提示'
      },
      // Environment
    env: {
      missing: '构建环境缺失',
      missingList: '缺少',
      preparing: '正在准备环境...',
      fix: '立即修复',
      ready: '环境已就绪',
      failed: '环境安装失败',
      missingToast: '构建环境未就绪',
      port: '后端端口',
      python: 'Python',
      quickFixHint: '建议优先使用快速修复，手动填写路径可能导致版本冲突',
      manualSetup: '手动填写路径',
      manualHint: '如确有需要，请填写下方路径（仍建议先使用快速修复）',
      nodePath: 'Node.js 路径',
      jdkPath: 'JDK 路径',
      androidPath: 'Android SDK 路径',
      pythonPath: 'Python 路径'
    },
    announcement: {
      title: '公告',
      dismiss: '我知道了'
    },
    settings: {
      title: '\u53cd\u9988Bug',
      toolchainSection: '工具链配置',
      toolchainRoot: '工具链存放路径',
      toolchainHint: '建议不要放在 Program Files 目录下',
      npmRegistry: 'NPM Registry 镜像',
      npmProxy: 'NPM Proxy 代理',
      npmHttpsProxy: 'NPM HTTPS Proxy 代理',
      dataRoot: '数据存放路径',
      dataRootPlaceholder: 'D:\\ConvertAPK\\data',
      dataRootHint: '任务/缓存/输出数据存储路径，留空使用默认。',
      selectDir: '选择目录',
      envSection: '环境路径',
      migrateToolchain: '迁移已有工具链到新路径',
      updateSection: '客户端更新',
      updateMode: '更新模式',
      updateSilent: '静默更新',
      updatePrompt: '提示更新',
      updateNotify: '仅提醒',
      currentVersion: '当前版本：{version}',
      checkUpdate: '检查更新',
      feedbackSection: '用户反馈',
      feedbackDevice: '当前设备：{cpu}（{cores} 核） | {ram} | {os}',
      recommendedSpec: '建议配置：4核+ CPU，8GB+ 内存',
      feedbackPlaceholder: '请描述你的问题或建议...',
      feedbackHint: '最多 5 张图片，单张不超过 10MB',
      feedbackSubmitting: '提交中...',
      selectImages: '选择图片',
      noImagesSelected: '未选择图片',
      imagesSelected: '已选 {count} 张图片',
      feedbackSubmit: '提交反馈',
      aboutSection: '关于工具',
      aboutDeveloper: '开发者：@Jmin',
      aboutContact: '邮箱：lzm1150772572@gmail.com',
      cancel: '取消',
      save: '保存',
      saving: '保存中...'
    },
    updateDialog: {
      title: '新版本可用',
      versionLabel: '版本号',
      notesLabel: '更新说明',
      noNotes: '暂无更新说明',
      later: '稍后',
      download: '下载更新'
    },
    firstBuild: {
      title: '首次构建可能需要更长时间',
      body: '首次构建会下载工具链和依赖，可能需要约 15 分钟。后续构建通常更快。',
      ok: '知道了'
    },
    window: {
      closePrompt: '当前还有任务在执行，是否关闭应用并中断当前任务？'
    },
    tip: {
      title: '感谢支持',
      subtitle: '构建完成：{name}。如果觉得好用，欢迎请我喝杯咖啡。',
      defaultApp: '你的应用',
      wechat: '微信',
      alipay: '支付宝',
      note: '打赏自愿，可随时关闭。',
      close: '关闭',
      thanks: '已打赏'
    },
    // Theme
    theme: {
      light: '浅色',
      dark: '深色'
    },
    // Language
    language: {
      en: 'English',
      'zh-CN': '简体中文',
      'zh-TW': '繁體中文'
    }
  },
  
  'zh-TW': {
    // Header
    header: {
      title: 'APK Converter',
      subtitle: 'Web App → Android APK',
      refresh: '重新整理'
    },
    mobileNav: {
      settings: '設定'
    },
    github: {
      star: 'Github Stars',
      starTitle: '打開 Github 專案並點亮 Star'
    },
    // Mode
    mode: {
      title: '轉換模式',
      apk: '專案轉 APK',
      web: '網頁轉 APK',
      html: 'HTML 轉 APK',
      desktop: 'ZIP 轉桌面應用'
    },
    // Guide
    guide: {
      title: '使用指南',
      subtitle: '如何生成 APK',
      step1: '在 Google AI Studio 建立應用',
      step2: '匯出專案為 ZIP 檔',
      step3: '在此處上傳並建構 APK',
      openAiStudio: '開啟 AI Studio',
      tips: '提示：如應用包含相機、匯入/匯出（下載）等功能，請在 Google AI Studio 提示 Gemini：「該功能需要做 Capacitor 適配」。'
    },
    // 新手引导
    onboarding: {
      kicker: '第一次建構',
      title: '把網頁專案變成可安裝應用',
      subtitle: '依照下面三步走：上傳 ZIP，確認應用資訊，然後開始建構並下載 APK。',
      primaryAction: '開始第一個建構',
      requirementsAction: '查看打包要求',
      flowLabel: '首次建構流程',
      stepUploadTitle: '上傳專案 ZIP',
      stepUploadText: '使用匯出的網頁專案，或準備好的靜態 HTML 包。',
      stepConfigTitle: '確認應用資訊',
      stepConfigText: '設定應用名稱、包名、版本、圖示和可選簽名。',
      stepBuildTitle: '建構並下載',
      stepBuildText: '即時查看日誌，成功後下載生成產物。',
      materialsTitle: '開始前準備這些材料',
      materialZip: '專案 ZIP',
      materialName: '應用名稱',
      materialPackage: 'Android 包名',
      materialIcon: '512x512 圖示',
      previewLabel: '示例任務預覽',
      previewTitle: '示例應用任務',
      previewText: '你的建構任務會顯示在這裡，包含日誌和下載入口。',
      previewStatus: '待建立'
    },
    // Steps
    steps: {
      upload: '上傳專案',
      configure: '設定應用',
      build: '建構APK',
      buildDesktop: '建構桌面應用'
    },
    // Upload
    upload: {
      title: '專案檔案',
      subtitle: '上傳 Google AI Studio 匯出的 ZIP 包',
      dragDrop: '拖放 ZIP 檔案到此處，或點擊選擇',
      hint: '支援 React、Vue 等前端專案',
      desktopTitle: 'Electron 專案 ZIP',
      desktopSubtitle: '上傳 ZIP 專案並打包為 Windows 桌面應用',
      desktopDragDrop: '拖放 ZIP 檔案到此處，或點擊選擇',
      desktopHint: '支援包含 package.json 的前端專案或純靜態 HTML 資源',
      ready: '檔案已就緒',
      selectNew: '選擇新檔案'
    },
    web: {
      url: '網頁位址',
      urlPlaceholder: 'https://www.example.com',
      urlHint: '可不帶 http/https，系統會自動補全並測試',
      validUrlError: '請輸入有效的網址',
      urlUnreachable: '網址無法訪問，請確認是否可用',
      enableAds: '啟用 Topon 廣告（試驗版）',
      adConfig: '廣告設定',
      toponAppId: 'Topon App ID',
      toponAppKey: 'Topon App Key',
      placementId: '激勵視頻廣告位 ID',
      jsIntegration: 'JS 整合程式碼範例',
      copyCode: '複製程式碼',
      codeCopied: '已複製!'
    },
    html: {
      title: 'HTML 檔案',
      subtitle: '上傳入口 HTML 檔案',
      upload: '上傳 HTML',
      modeFile: '檔案',
      modeEdit: '編輯',
      editorTitle: 'HTML 編輯器',
      editorSave: '儲存',
      editorSaving: '上傳中...',
      editorLoading: '編輯器載入中...',
      editorSaved: '已儲存',
      editorUnsaved: '未儲存變更',
      editorEmpty: '請輸入 HTML 內容',
      saveBeforeBuild: '請先儲存 HTML 再建立建構任務',
      fixErrors: '請先修復 {count} 個語法錯誤',
      fullscreen: '大屏編輯',
      exitFullscreen: '退出大屏',
      editorModalOpen: '編輯器已在大屏視窗中開啟。',
      issues: '{count} 個問題',
      noIssues: '暫無問題',
      issueError: '錯誤',
      issueWarning: '警告',
      syntaxError: '語法錯誤',
      tagMismatch: '標籤不匹配：應為 </{expected}>，但找到 </{found}>',
      tagUnexpectedClose: '多餘的結束標籤：</{name}>',
      tagMissingClose: '缺少結束標籤：<{name}>',
      dragDrop: '拖拽 HTML 檔案到此處，或點擊選擇',
      hint: '必須包含入口 HTML 檔案',
      ready: 'HTML 已就緒',
      htmlRequired: '請上傳 HTML 檔案',
      reuseHtml: '使用上一版本的 HTML 檔案',
      preview: '預覽',
      previewTitle: 'APP 預覽',
      closePreview: '關閉',
      previewUnavailable: '暫無可預覽的 HTML 內容',
    },
    cdnLocalize: {
      title: 'CDN 外鏈本地化',
      scanning: '正在掃描外鏈資源...',
      detected: '檢測到 {total} 條外鏈，已選 {selected} 條。建議開啟本地化，避免 APP 首次離線啟動時樣式遺失。',
      noLinks: '目前未檢測到外鏈資源。匯入新檔案後可重新掃描。',
      enable: '啟用本地化',
      rescan: '重新掃描',
      selectLinks: '選擇外鏈',
      dialogTitle: '選擇需要本地化的外鏈資源',
      selectAll: '全選',
      clear: '清空',
      selectedCount: '已選 {selected} / {total}',
      empty: '未檢測到可本地化的外鏈',
      tip: '建議保持本地化開啟，避免 APP 首次離線啟動時樣式遺失。',
      done: '完成',
      occurrences: '{count} 次引用',
      fileCount: '{count} 個檔案',
      scanFailed: '外鏈掃描失敗，已切換為全部外鏈本地化。',
      rescanReuseConvert: '複用歷史任務時無法重新掃描，請重新上傳專案檔案。',
      rescanReuseHtml: '複用歷史任務時無法重新掃描，請重新上傳 HTML 檔案。',
      type: {
        other: '其他',
        css: '樣式',
        script: '腳本',
        font: '字體',
        image: '圖片',
        media: '媒體',
        mixed: '混合'
      }
    },
    // Config
    config: {
      title: '應用設定',
      updateTitle: '更新應用',
      subtitle: '設定應用基本資訊和圖示',
      updateSubtitle: '更新 "{name}"',
      cancelUpdate: '取消更新',
      appName: '應用名稱',
      appNamePlaceholder: '例如：我的應用',
      packageName: '套件名稱',
      packageNamePlaceholder: '例如：com.example.myapp',
      packageNameRule: '需符合 Android 套件名稱規範：小寫字母/數字/底線，點號分隔，每段以字母開頭（如 com.example.app）',
      versionName: '版本名稱',
      versionCode: '版本號',
      minVersion: '最低: {version}',
      outputFormat: '輸出格式',
      apk: 'APK (直接安裝)',
      signConfigHint: '若對已有應用做版本升級，建議上傳自帶簽名檔案。',
      aab: 'AAB (Google Play)',
      desktopInstallerMode: '桌面安裝器模式',
      desktopInstallerPortable: '便攜版（Portable）',
      desktopInstallerNsisWeb: 'Web 安裝器（NSIS-Web）',
      signConfig: '簽名設定 (選填)',
      keystoreAlias: '金鑰別名',
      keystorePassword: '金鑰庫密碼',
      keyPassword: '金鑰密碼',
      keystorePasswordRule: '金鑰庫密碼至少 6 個字元',
      keyPasswordRule: '金鑰密碼至少 6 個字元',
      keystoreUploadToggle: '使用自帶簽名檔案',
      keystoreUpload: '上傳簽名檔案',
      keystoreChoose: '選擇檔案',
      keystoreRemove: '移除',
      keystoreUploadWarning: '使用自己的簽名請注意提高應用版本，避免安裝衝突。',
      keystoreUploadInvalid: '僅支援 .jks 或 .keystore 檔案。',
      keystoreUploadSuccess: '簽名檔案上傳成功。',
      keystoreUploadFailed: '簽名檔案上傳失敗',
      keystoreUploadNotAllowed: '更新任務時不支援上傳簽名檔案。',
      keystoreUpgradePackageHint: '升級已有應用時請確保包名與之前完全一致。',
      // APK Style
      styleTitle: 'APK 樣式',
      orientation: '螢幕方向',
      orientationPortrait: '強制直屏',
      orientationLandscape: '強制橫屏',
      orientationAuto: '跟隨系統',
      doubleClickExit: '按兩下返回鍵退出應用',
      downloadMode: '匯出/下載方式',
      downloadModeSilent: '靜默匯出',
      downloadModePicker: '資源管理器',
      webFillMode: '頁面填充策略',
      webFillModeContain: '完整顯示（推薦）',
      webFillModeCover: '鋪滿裁切（遊戲場景）',
      statusBarTitle: '狀態欄設置',
      statusBarHidden: '隱藏狀態欄 (全屏)',
      statusBarColor: '狀態欄顏色',
      statusBarColorHiddenHint: '已啟用全螢幕隱藏狀態欄，顏色設定暫不生效。',
      statusBarBackground: '背景顏色',
      statusBarTransparent: '透明',
      statusBarWhite: '白底',
      statusBarStyle: '圖標風格',
      statusBarStyleDark: '深色圖標',
      statusBarStyleLight: '淺色圖標',
      webviewUserAgent: 'UA 標識',
      webviewUserAgentAndroid: '安卓（預設）',
      webviewUserAgentPc: 'PC',
      permissionsTitle: '應用權限',
      enablePermissions: '申請額外權限',
      permissionsHint: '勾選以配置 AndroidManifest.xml 權限',
      perm: {
        INTERNET: '存取網路',
        ACCESS_NETWORK_STATE: '檢視網路狀態',
        ACCESS_WIFI_STATE: '檢視 Wi-Fi 狀態',
        CAMERA: '使用相機',
        READ_EXTERNAL_STORAGE: '讀取儲存卡',
        WRITE_EXTERNAL_STORAGE: '寫入儲存卡',
        ACCESS_FINE_LOCATION: '精確位置 (GPS)',
        ACCESS_COARSE_LOCATION: '粗略位置',
        RECORD_AUDIO: '錄音',
        READ_PHONE_STATE: '讀取手機狀態',
        CALL_PHONE: '撥打電話',
        READ_CONTACTS: '讀取聯絡人',
        WRITE_CONTACTS: '寫入聯絡人',
        VIBRATE: '使用震動',
        WAKE_LOCK: '防止手機休眠',
        RECEIVE_BOOT_COMPLETED: '開機自動啟動',
        FOREGROUND_SERVICE: '前台服務',
        REQUEST_INSTALL_PACKAGES: '安裝應用程式',
        SYSTEM_ALERT_WINDOW: '懸浮視窗權限',
        BLUETOOTH: '使用藍牙',
        BLUETOOTH_ADMIN: '管理藍牙',
        NFC: '使用 NFC',
        READ_CALENDAR: '讀取行事曆',
        WRITE_CALENDAR: '寫入行事曆'
      },
      createTask: '建立建構任務',
      updateTask: '更新並重新建構',
      creating: 'AI風控審核中...',
      updateMode: '更新模式',
      updateHint: '正在更新已有應用，將複用原有簽名金鑰',
      quickGenerate: '一鍵生成',
      quickGenerateHint: '隱藏設定表單，使用系統預設自動產生',
      quickGenerateModeCustom: '自訂',
      quickGenerateModeQuick: '一鍵',
      quickGenerateEnabled: '已啟用一鍵生成',
      quickGenerateDesc: '已隱藏全部應用設定表單，將使用系統預設並自動遞增版本。',
      quickGenerateAuto: '系統自動遞增',
      quickGenerateAllPermissions: '全部申請'
    },
    // Icon
    icon: {
      title: '應用圖示',
      required: '(必填)',
      uploadHint: '點擊上傳',
      change: '更換',
      requirements: '要求: 1024×1024 PNG，支援自動裁切'
    },
    // Cropper
    cropper: {
      title: '裁切圖示',
      hint: '拖動選擇區域，輸出尺寸：1024 × 1024 像素',
      cancel: '取消',
      confirm: '確認裁切'
    },
    // Tasks
    tasks: {
      title: '建構任務',
      subtitle: '檢視和管理所有任務',
      total: '總任務',
      completed: '已完成',
      running: '執行中',
      queued: '排隊',
      waiting: '等待中',
      noTasks: '暫無建構任務',
      createFirst: '上傳專案檔案並設定資訊後建立第一個任務',
      version: 'v{version}',
      useConfig: '使用設定',
      viewLogs: '日誌',
      retry: '重試',
      start: '開始建構',
      download: '下載產物',
      downloadMenu: '下載選單',
      downloadSigned: '下載簽名密鑰',
      delete: '刪除',
      cancel: '取消',
      jump: '跳轉頁碼',
      go: '跳轉',
      newBadge: '新建',
      retryBadge: '重試'
    },
    // Status
    status: {
      pending: '等待中',
      processing: '建構中',
      success: '成功',
      failed: '失敗',
      queued: '排隊中（前方{count}個）'
    },
    // Logs
    logs: {
      title: '建構日誌',
      taskId: '任務ID',
      loading: '日誌載入中...',
      noLogs: '暫無日誌記錄',
      refreshLogs: '重新整理日誌',
      logCount: '共 {count} 條日誌',
      close: '關閉'
    },
    // Toast
    toast: {
      uploadSuccess: '檔案上傳成功',
      uploadFailed: '上傳失敗',
      uploadTooLarge: '目前檔案大小為 {size}，超過目前上傳限制 {limit}，請壓縮後重試。',
      taskCreated: '建構任務已建立',
      taskStarted: '建構任務已啟動',
      desktopModeDisabled: 'Electron 桌面模式已關閉',
      nativeModeDisabled: '原生 Android 打包模式已關閉',
      firstBuildHint: '首次建構可能需要約 15 分鐘，後續建構會更快。',
      taskRetried: '任務已重置，請重新開始',
      taskDeleted: '任務已刪除',
      deleteConfirm: '確定要刪除這個任務嗎？',
      iconRequired: '請上傳應用圖示',
      iconSuccess: '圖示設定成功',
      iconUploadFailed: '圖示上傳失敗',
      versionError: '版本必須大於之前的值',
      error: '操作失敗',
      configLoadFailed: '獲取配置失敗',
      configSaved: '配置已儲存',
      configSaveFailed: '儲存失敗',
      updateOpened: '已開啟更新下載連結',
      feedbackFileLimit: '附件最多 5 張且單張不超過 10MB',
      feedbackEmpty: '請填寫回饋內容',
      feedbackSent: '回饋已提交',
      feedbackFailed: '回饋提交失敗',
      feedbackCooldown: '提交過於頻繁，請稍後再試',
      feedbackDailyLimit: '今日回饋次數已達上限',
      startFailed: '啟動任務失敗',
      retryFailed: '重試任務失敗',
      cancelFailed: '取消任務失敗',
      deleteFailed: '刪除任務失敗',
      operationFailed: '操作失敗',
      cancelConfirm: '確定要取消這個任務嗎？',
      deleteConfirm: '確定要刪除這個任務嗎？'
    },
      donation: {
        title: '支持開發者',
        button: '支持作者',
        message: '如果你覺得好用，不妨請開發者喝一杯奶茶。',
        subMessage: '小小心意，非常感謝支持！',
        alipay: '支付寶',
        wechat: '微信',
        hide: '不再提示'
      },
      // Environment
    env: {
      missing: '建構環境缺失',
      missingList: '缺少',
      preparing: '正在準備環境...',
      fix: '立即修復',
      ready: '環境已就緒',
      failed: '環境安裝失敗',
      missingToast: '建構環境未就緒',
      port: '後端埠',
      python: 'Python',
      quickFixHint: '建議優先使用快速修復，手動填寫路徑可能導致版本衝突',
      manualSetup: '手動填寫路徑',
      manualHint: '如確有需要，請填寫下方路徑（仍建議先使用快速修復）',
      nodePath: 'Node.js 路徑',
      jdkPath: 'JDK 路徑',
      androidPath: 'Android SDK 路徑',
      pythonPath: 'Python 路徑'
    },
    announcement: {
      title: '公告',
      dismiss: '我知道了'
    },
    settings: {
      title: '\u56de\u5831Bug',
      toolchainSection: '工具鏈設定',
      toolchainRoot: '工具鏈存放路徑',
      toolchainRootPlaceholder: 'D:\\Convertapk\\resources\\toolchain',
      toolchainHint: '建議不要放在 Program Files 目錄下',
      npmRegistry: 'NPM Registry 鏡像',
      npmRegistryPlaceholder: 'https://registry.npmmirror.com',
      npmProxy: 'NPM Proxy 代理',
      npmProxyPlaceholder: 'http://127.0.0.1:7890',
      npmHttpsProxy: 'NPM HTTPS Proxy 代理',
      npmHttpsProxyPlaceholder: 'http://127.0.0.1:7890',
      dataRoot: '資料存放路徑',
      dataRootPlaceholder: 'D:\\ConvertAPK\\data',
      dataRootHint: '任務/快取/輸出資料存放路徑，留空使用預設。',
      selectDir: '選擇目錄',
      envSection: '環境路徑',
      nodePathPlaceholder: 'D:\\工具\\node',
      jdkPathPlaceholder: 'D:\\Java\\jdk-21',
      androidPathPlaceholder: 'D:\\Android\\Sdk',
      pythonPathPlaceholder: 'D:\\Python311\\python.exe',
      migrateToolchain: '遷移既有工具鏈到新路徑',
      updateSection: '用戶端更新',
      updateMode: '更新模式',
      updateSilent: '靜默更新',
      updatePrompt: '提示更新',
      updateNotify: '僅提醒',
      currentVersion: '目前版本：{version}',
      checkUpdate: '檢查更新',
      feedbackSection: '用戶回饋',
      feedbackDevice: '目前裝置：{cpu}（{cores} 核） | {ram} | {os}',
      recommendedSpec: '建議配置：4核+ CPU，8GB+ 記憶體',
      feedbackPlaceholder: '請描述你的問題或建議...',
      feedbackHint: '最多 5 張圖片，單張不超過 10MB',
      feedbackSubmitting: '提交中...',
      selectImages: '選擇圖片',
      noImagesSelected: '未選擇圖片',
      imagesSelected: '已選 {count} 張圖片',
      feedbackSubmit: '提交回饋',
      aboutSection: '關於工具',
      aboutDeveloper: '開發者：@Jmin',
      aboutContact: '信箱：lzm1150772572@gmail.com',
      cancel: '取消',
      save: '儲存',
      saving: '儲存中...'
    },
    updateDialog: {
      title: '新版本可用',
      versionLabel: '版本號',
      notesLabel: '更新說明',
      noNotes: '暫無更新說明',
      later: '稍後',
      download: '下載更新'
    },
    tip: {
      title: '感謝支持',
      subtitle: '建構完成：{name}。如果覺得好用，歡迎請我喝杯咖啡。',
      defaultApp: '你的應用',
      wechat: '微信',
      alipay: '支付寶',
      note: '打賞自願，可隨時關閉。',
      close: '關閉',
      thanks: '已打賞'
    },
    firstBuild: {
      title: '首次建構可能需要更長時間',
      body: '首次建構會下載工具鏈和相依，可能需要約 15 分鐘。後續建構通常更快。',
      ok: '知道了'
    },
    window: {
      closePrompt: '目前仍有任務執行中，是否關閉應用並中斷目前任務？'
    },
    // Theme
    theme: {
      light: '淺色',
      dark: '深色'
    },
    // Language
    language: {
      en: 'English',
      'zh-CN': '简体中文',
      'zh-TW': '繁體中文'
    }
  }
}

// 获取浏览器语言
messages.en.config.keystoreUpgradeVersionRule = 'For same-package upgrades, versionCode must be greater than {current}. Recommended: at least {next}.'
messages.en.config.keystoreUpgradeVersionHint = 'A signed build for {packageName} already exists. To upgrade-install, set versionCode to at least {next}.'
messages['zh-CN'].config.keystoreUpgradeVersionRule = '同包名升级安装时，versionCode 必须大于 {current}，建议至少填写 {next}。'
messages['zh-CN'].config.keystoreUpgradeVersionHint = '{packageName} 已有成功的签名构建，如需覆盖安装，请将 versionCode 设置为至少 {next}。'
messages['zh-TW'].config.keystoreUpgradeVersionRule = '同套件名稱升級安裝時，versionCode 必須大於 {current}，建議至少填寫 {next}。'
messages['zh-TW'].config.keystoreUpgradeVersionHint = '{packageName} 已有成功的簽名建構，如需覆蓋安裝，請將 versionCode 設為至少 {next}。'

messages.en.config.desktopPort = 'Desktop Local Port'
messages.en.config.desktopPortPlaceholder = 'e.g. 24567'
messages.en.config.desktopPortHint = 'Default random value avoids common ports; valid range: 1024-65535.'
messages.en.config.desktopPortRule = 'Desktop port must be an integer between 1024 and 65535.'
messages.en.config.desktopPortRandom = 'Random'
messages['zh-CN'].config.desktopPort = '桌面本地端口'
messages['zh-CN'].config.desktopPortPlaceholder = '例如：24567'
messages['zh-CN'].config.desktopPortHint = '默认随机值会避开常用端口；有效范围：1024-65535。'
messages['zh-CN'].config.desktopPortRule = '桌面端口必须是 1024-65535 的整数。'
messages['zh-CN'].config.desktopPortRandom = '随机'
messages['zh-TW'].config.desktopPort = '桌面本地埠號'
messages['zh-TW'].config.desktopPortPlaceholder = '例如：24567'
messages['zh-TW'].config.desktopPortHint = '預設隨機值會避開常用埠號；有效範圍：1024-65535。'
messages['zh-TW'].config.desktopPortRule = '桌面埠號必須是 1024-65535 的整數。'
messages['zh-TW'].config.desktopPortRandom = '隨機'

messages.en.auth = {
  entry: 'Login / Register',
  loginTitle: 'Welcome Back',
  registerTitle: 'Create Account',
  loginTab: 'Login',
  registerTab: 'Register',
  email: 'Email',
  emailPlaceholder: 'you@example.com',
  password: 'Password',
  passwordPlaceholder: 'At least 6 characters',
  confirmPassword: 'Confirm Password',
  confirmPasswordPlaceholder: 'Re-enter password',
  loginSubmit: 'Login',
  registerSubmit: 'Register',
  cancel: 'Cancel',
  submitting: 'Submitting...',
  logout: 'Logout',
  loginSuccess: 'Logged in successfully',
  registerSuccess: 'Registered successfully',
  logoutSuccess: 'Logged out',
  entryDisabled: 'Login and registration are disabled by admin',
  loginDisabled: 'Login is disabled by admin',
  registerDisabled: 'Registration is disabled by admin',
  errorGeneral: 'Operation failed, please try again',
  errorEmailFormat: 'Please enter a valid email',
  errorPasswordLength: 'Password must be at least 6 characters',
  errorPasswordConfirm: 'Passwords do not match',
  errorEmailExists: 'Email is already registered',
  errorCredential: 'Email or password is incorrect',
  errorClientBound: 'This client is already bound to another account',
  orDivider: 'or',
  githubSubmit: 'Continue with GitHub',
  githubRedirecting: 'Redirecting...',
  githubLoginSuccess: 'GitHub login successful',
  githubUnavailable: 'GitHub login is not configured yet',
  githubStateInvalid: 'GitHub login state is invalid, please retry',
  githubAccessDenied: 'GitHub login was canceled',
  githubCallbackFailed: 'GitHub login failed, please try again'
}

messages['zh-CN'].auth = {
  entry: '登录 / 注册',
  loginTitle: '欢迎回来',
  registerTitle: '创建账号',
  loginTab: '登录',
  registerTab: '注册',
  email: '邮箱',
  emailPlaceholder: 'you@example.com',
  password: '密码',
  passwordPlaceholder: '至少 6 位字符',
  confirmPassword: '确认密码',
  confirmPasswordPlaceholder: '再次输入密码',
  loginSubmit: '登录',
  registerSubmit: '注册',
  cancel: '取消',
  submitting: '提交中...',
  logout: '退出登录',
  loginSuccess: '登录成功',
  registerSuccess: '注册成功',
  logoutSuccess: '已退出登录',
  entryDisabled: '管理员已关闭登录与注册功能',
  loginDisabled: '管理员已关闭登录功能',
  registerDisabled: '管理员已关闭注册功能',
  errorGeneral: '操作失败，请稍后重试',
  errorEmailFormat: '请输入有效邮箱地址',
  errorPasswordLength: '密码至少需要 6 位字符',
  errorPasswordConfirm: '两次输入的密码不一致',
  errorEmailExists: '该邮箱已被注册',
  errorCredential: '邮箱或密码错误',
  errorClientBound: '当前客户端已绑定到其他账号'
}

messages['zh-TW'].auth = {
  entry: '登入 / 註冊',
  loginTitle: '歡迎回來',
  registerTitle: '建立帳號',
  loginTab: '登入',
  registerTab: '註冊',
  email: '信箱',
  emailPlaceholder: 'you@example.com',
  password: '密碼',
  passwordPlaceholder: '至少 6 位字元',
  confirmPassword: '確認密碼',
  confirmPasswordPlaceholder: '再次輸入密碼',
  loginSubmit: '登入',
  registerSubmit: '註冊',
  cancel: '取消',
  submitting: '提交中...',
  logout: '登出',
  loginSuccess: '登入成功',
  registerSuccess: '註冊成功',
  logoutSuccess: '已登出',
  entryDisabled: '管理員已關閉登入與註冊功能',
  loginDisabled: '管理員已關閉登入功能',
  registerDisabled: '管理員已關閉註冊功能',
  errorGeneral: '操作失敗，請稍後再試',
  errorEmailFormat: '請輸入有效信箱地址',
  errorPasswordLength: '密碼至少需要 6 位字元',
  errorPasswordConfirm: '兩次輸入的密碼不一致',
  errorEmailExists: '該信箱已被註冊',
  errorCredential: '信箱或密碼錯誤',
  errorClientBound: '目前客戶端已綁定到其他帳號'
}

messages['zh-CN'].auth.orDivider = '或'
messages['zh-CN'].auth.githubSubmit = '使用 GitHub 快捷登录'
messages['zh-CN'].auth.githubRedirecting = '正在跳转...'
messages['zh-CN'].auth.githubLoginSuccess = 'GitHub 登录成功'
messages['zh-CN'].auth.githubUnavailable = 'GitHub 登录暂未配置'
messages['zh-CN'].auth.githubStateInvalid = '登录状态已失效，请重试'
messages['zh-CN'].auth.githubAccessDenied = '你已取消 GitHub 授权'
messages['zh-CN'].auth.githubCallbackFailed = 'GitHub 登录失败，请重试'

messages['zh-TW'].auth.orDivider = '或'
messages['zh-TW'].auth.githubSubmit = '使用 GitHub 快速登入'
messages['zh-TW'].auth.githubRedirecting = '正在跳轉...'
messages['zh-TW'].auth.githubLoginSuccess = 'GitHub 登入成功'
messages['zh-TW'].auth.githubUnavailable = 'GitHub 登入尚未設定'
messages['zh-TW'].auth.githubStateInvalid = '登入狀態已失效，請重試'
messages['zh-TW'].auth.githubAccessDenied = '你已取消 GitHub 授權'
messages['zh-TW'].auth.githubCallbackFailed = 'GitHub 登入失敗，請重試'

messages.en.logs.aiTitle = 'AI Diagnosis'
messages.en.logs.aiLoading = 'Analyzing failed logs...'
messages.en.logs.aiEmpty = 'No diagnosis available yet'
messages.en.logs.aiSummary = 'Summary'
messages.en.logs.aiReason = 'Reason'
messages.en.logs.aiCauses = 'Possible Causes'
messages.en.logs.aiSolutions = 'Solutions'
messages.en.logs.aiProvider = 'Provider'
messages.en.logs.aiModel = 'Model'
messages.en.logs.aiConfidence = 'Confidence'
messages.en.logs.aiRerun = 'Rerun'
messages.en.logs.aiFetchFailed = 'Failed to fetch diagnosis'
messages.en.logs.aiRerunStarted = 'Diagnosis started'
messages.en.logs.aiRerunFailed = 'Failed to rerun diagnosis'

messages['zh-CN'].logs.aiTitle = '智能诊断'
messages['zh-CN'].logs.aiLoading = '正在分析失败日志，请稍候...'
messages['zh-CN'].logs.aiEmpty = '暂无可用诊断结果'
messages['zh-CN'].logs.aiSummary = '结论摘要'
messages['zh-CN'].logs.aiReason = '主要原因'
messages['zh-CN'].logs.aiCauses = '可能原因'
messages['zh-CN'].logs.aiSolutions = '解决思路'
messages['zh-CN'].logs.aiProvider = '诊断来源'
messages['zh-CN'].logs.aiModel = '模型'
messages['zh-CN'].logs.aiConfidence = '置信度'
messages['zh-CN'].logs.aiRerun = '重新诊断'
messages['zh-CN'].logs.aiFetchFailed = '获取诊断失败'
messages['zh-CN'].logs.aiRerunStarted = '已开始重新诊断'
messages['zh-CN'].logs.aiRerunFailed = '重新诊断失败'

messages['zh-TW'].logs.aiTitle = '智慧診斷'
messages['zh-TW'].logs.aiLoading = '正在分析失敗日誌，請稍候...'
messages['zh-TW'].logs.aiEmpty = '暫無可用診斷結果'
messages['zh-TW'].logs.aiSummary = '摘要'
messages['zh-TW'].logs.aiReason = '主要原因'
messages['zh-TW'].logs.aiCauses = '可能原因'
messages['zh-TW'].logs.aiSolutions = '解決思路'
messages['zh-TW'].logs.aiProvider = '診斷來源'
messages['zh-TW'].logs.aiModel = '模型'
messages['zh-TW'].logs.aiConfidence = '置信度'
messages['zh-TW'].logs.aiRerun = '重新診斷'
messages['zh-TW'].logs.aiFetchFailed = '取得診斷失敗'
messages['zh-TW'].logs.aiRerunStarted = '已開始重新診斷'
messages['zh-TW'].logs.aiRerunFailed = '重新診斷失敗'

messages.en.config.waitingRewardAd = 'Waiting for rewarded ad...'
messages['zh-CN'].config.waitingRewardAd = '等待激励广告播放...'
messages['zh-TW'].config.waitingRewardAd = '等待激勵廣告播放...'
messages.en.config.rewardedBuildButton = 'Watch ad voluntarily to get build credit'
messages['zh-CN'].config.rewardedBuildButton = '自愿观看广告以获得构建额度'
messages['zh-TW'].config.rewardedBuildButton = '自願觀看廣告以取得建構額度'
messages.en.tasks.rewardedStart = 'Watch ad voluntarily, then start build'
messages['zh-CN'].tasks.rewardedStart = '自愿观看广告后开始构建'
messages['zh-TW'].tasks.rewardedStart = '自願觀看廣告後開始建構'
messages.en.toast.rewardAdLoading = 'Rewarded ad is loading, please wait'
messages['zh-CN'].toast.rewardAdLoading = '激励广告加载中，请稍候'
messages['zh-TW'].toast.rewardAdLoading = '激勵廣告載入中，請稍候'
messages.en.toast.rewardAdIncomplete = 'The rewarded ad was not completed. Build has not started.'
messages['zh-CN'].toast.rewardAdIncomplete = '激励广告未播放完成，构建暂未启动'
messages['zh-TW'].toast.rewardAdIncomplete = '激勵廣告未播放完成，建構暫未啟動'

export function getBrowserLanguage() {
  const lang = navigator.language || navigator.userLanguage
  if (lang.startsWith('zh')) {
    return lang.includes('TW') || lang.includes('HK') ? 'zh-TW' : 'zh-CN'
  }
  return 'en'
}

// 从localStorage获取保存的语言
export function getSavedLanguage() {
  return localStorage.getItem('apk_builder_lang') || getBrowserLanguage()
}

// 保存语言设置
export function saveLanguage(lang) {
  localStorage.setItem('apk_builder_lang', lang)
}

// 从localStorage获取保存的主题
export function getSavedTheme() {
  return localStorage.getItem('apk_builder_theme') || 'light'
}

// 保存主题设置
export function saveTheme(theme) {
  localStorage.setItem('apk_builder_theme', theme)
}

// 翻译函数
export function createI18n(locale) {
  return {
    t(key, params = {}) {
      const keys = key.split('.')
      let value = messages[locale]
      for (const k of keys) {
        if (value && typeof value === 'object') {
          value = value[k]
        } else {
          return key
        }
      }
      if (typeof value === 'string') {
        // 替换参数
        return value.replace(/\{(\w+)\}/g, (_, name) => params[name] ?? `{${name}}`)
      }
      return key
    }
  }
}

messages.en.config.desktopRuntime = 'Desktop Engine'
messages.en.config.desktopRuntimeElectron = 'Electron'
messages.en.config.desktopRuntimeTauri = 'Tauri'
messages['zh-CN'].config.desktopRuntime = '桌面引擎'
messages['zh-CN'].config.desktopRuntimeElectron = 'Electron'
messages['zh-CN'].config.desktopRuntimeTauri = 'Tauri'
messages['zh-TW'].config.desktopRuntime = '桌面引擎'
messages['zh-TW'].config.desktopRuntimeElectron = 'Electron'
messages['zh-TW'].config.desktopRuntimeTauri = 'Tauri'
messages.en.upload.desktopTitle = 'Desktop App Project ZIP'
messages['zh-CN'].upload.desktopTitle = '桌面应用项目 ZIP'
messages['zh-TW'].upload.desktopTitle = '桌面應用專案 ZIP'
messages.en.mode.native = 'Native Android'
messages['zh-CN'].mode.native = '原生安卓打包'
messages['zh-TW'].mode.native = '原生安卓打包'
messages.en.upload.nativeTitle = 'Native Android Source ZIP'
messages.en.upload.nativeSubtitle = 'Upload a complete Gradle Android project with settings.gradle and gradlew'
messages.en.upload.nativeDragDrop = 'Drag & drop native Android source ZIP here, or click to select'
messages.en.upload.nativeHint = 'Requires an app module, AndroidManifest.xml, and Gradle Wrapper'
messages['zh-CN'].upload.nativeTitle = '原生 Android 源码 ZIP'
messages['zh-CN'].upload.nativeSubtitle = '上传完整 Gradle 工程源码包，需包含 settings.gradle 与 gradlew'
messages['zh-CN'].upload.nativeDragDrop = '拖放原生 Android 源码 ZIP，或点击选择'
messages['zh-CN'].upload.nativeHint = '需包含 app 模块、AndroidManifest.xml 和 Gradle Wrapper'
messages['zh-TW'].upload.nativeTitle = '原生 Android 原始碼 ZIP'
messages['zh-TW'].upload.nativeSubtitle = '上傳完整 Gradle 專案原始碼包，需包含 settings.gradle 與 gradlew'
messages['zh-TW'].upload.nativeDragDrop = '拖放原生 Android 原始碼 ZIP，或點擊選擇'
messages['zh-TW'].upload.nativeHint = '需包含 app 模組、AndroidManifest.xml 和 Gradle Wrapper'
messages.en.toast.desktopModeDisabled = 'Desktop app mode is disabled'
messages['zh-CN'].toast.desktopModeDisabled = '桌面应用模式已关闭'
messages['zh-TW'].toast.desktopModeDisabled = '桌面應用模式已關閉'
messages.en.toast.nativeModeDisabled = 'Native Android packaging mode is disabled'
messages['zh-CN'].toast.nativeModeDisabled = '原生 Android 打包模式已关闭'
messages['zh-TW'].toast.nativeModeDisabled = '原生 Android 打包模式已關閉'

messages.en.auth.loginMethodPassword = 'Password'
messages.en.auth.loginMethodSms = 'SMS Code'
messages.en.auth.phone = 'Phone Number'
messages.en.auth.phonePlaceholder = '+8613812345678'
messages.en.auth.smsCode = 'Verification Code'
messages.en.auth.smsCodePlaceholder = 'Enter 6-digit code'
messages.en.auth.sendSmsCode = 'Send Code'
messages.en.auth.sendSmsCodeRetry = 'Resend in {seconds}s'
messages.en.auth.sendSmsCodeSuccess = 'Verification code sent'
messages.en.auth.smsLoginSubmit = 'Login with SMS'
messages.en.auth.smsLoginSuccess = 'Logged in successfully'
messages.en.auth.smsLoginDisabled = 'SMS login is disabled by admin'
messages.en.auth.errorPhoneFormat = 'Please enter a valid phone number'
messages.en.auth.errorSmsCodeFormat = 'Please enter a valid 6-digit code'
messages.en.auth.errorSmsTooFrequent = 'Too many requests, please try again later'
messages.en.auth.errorSmsDailyLimit = 'Daily SMS limit reached, please try tomorrow'
messages.en.auth.errorSmsIncorrect = 'Verification code is incorrect'
messages.en.auth.errorSmsExpired = 'Verification code has expired'
messages.en.auth.errorSmsAttemptsExceeded = 'Too many failed attempts, please request a new code'

messages['zh-CN'].auth.loginMethodPassword = '密码登录'
messages['zh-CN'].auth.loginMethodSms = '短信登录'
messages['zh-CN'].auth.phone = '手机号'
messages['zh-CN'].auth.phonePlaceholder = '+8613812345678'
messages['zh-CN'].auth.smsCode = '验证码'
messages['zh-CN'].auth.smsCodePlaceholder = '请输入 6 位验证码'
messages['zh-CN'].auth.sendSmsCode = '发送验证码'
messages['zh-CN'].auth.sendSmsCodeRetry = '{seconds}s 后重发'
messages['zh-CN'].auth.sendSmsCodeSuccess = '验证码已发送'
messages['zh-CN'].auth.smsLoginSubmit = '短信登录'
messages['zh-CN'].auth.smsLoginSuccess = '登录成功'
messages['zh-CN'].auth.smsLoginDisabled = '管理员已关闭短信登录'
messages['zh-CN'].auth.errorPhoneFormat = '请输入有效手机号'
messages['zh-CN'].auth.errorSmsCodeFormat = '请输入有效的 6 位验证码'
messages['zh-CN'].auth.errorSmsTooFrequent = '请求过于频繁，请稍后再试'
messages['zh-CN'].auth.errorSmsDailyLimit = '今日短信发送次数已达上限'
messages['zh-CN'].auth.errorSmsIncorrect = '验证码错误'
messages['zh-CN'].auth.errorSmsExpired = '验证码已过期'
messages['zh-CN'].auth.errorSmsAttemptsExceeded = '验证码尝试次数过多，请重新获取'

messages['zh-TW'].auth.loginMethodPassword = '密碼登入'
messages['zh-TW'].auth.loginMethodSms = '簡訊登入'
messages['zh-TW'].auth.phone = '手機號'
messages['zh-TW'].auth.phonePlaceholder = '+8613812345678'
messages['zh-TW'].auth.smsCode = '驗證碼'
messages['zh-TW'].auth.smsCodePlaceholder = '請輸入 6 位驗證碼'
messages['zh-TW'].auth.sendSmsCode = '發送驗證碼'
messages['zh-TW'].auth.sendSmsCodeRetry = '{seconds}s 後重發'
messages['zh-TW'].auth.sendSmsCodeSuccess = '驗證碼已發送'
messages['zh-TW'].auth.smsLoginSubmit = '簡訊登入'
messages['zh-TW'].auth.smsLoginSuccess = '登入成功'
messages['zh-TW'].auth.smsLoginDisabled = '管理員已關閉簡訊登入'
messages['zh-TW'].auth.errorPhoneFormat = '請輸入有效手機號'
messages['zh-TW'].auth.errorSmsCodeFormat = '請輸入有效的 6 位驗證碼'
messages['zh-TW'].auth.errorSmsTooFrequent = '請求過於頻繁，請稍後再試'
messages['zh-TW'].auth.errorSmsDailyLimit = '今日簡訊發送次數已達上限'
messages['zh-TW'].auth.errorSmsIncorrect = '驗證碼錯誤'
messages['zh-TW'].auth.errorSmsExpired = '驗證碼已過期'
messages['zh-TW'].auth.errorSmsAttemptsExceeded = '驗證碼嘗試次數過多，請重新取得'

messages.en.config.taskComplianceTitle = 'Compliance Confirmation'
messages.en.config.taskComplianceAckLabel = 'I confirm this task will not create app stores/markets, similar distribution apps, download sites, downloader apps, or content scraper/downloaders, and does not involve phishing, impersonation, or malicious distribution.'
messages.en.config.taskUseCaseLabel = 'Intended Use'
messages.en.config.taskUseCasePlaceholder = 'Describe your legitimate use case'
messages.en.config.taskComplianceAckRequired = 'Please confirm the compliance statement before creating a task'
messages.en.config.taskUseCaseRequired = 'Please provide the intended use (at least {min} characters)'
messages.en.config.taskUseCaseTooLong = 'Intended use is too long (max {max} characters)'
messages.en.config.marketplaceBlocked = 'Task blocked by policy: suspected app marketplace/distribution behavior'
messages.en.config.prohibitedGenerationHint = 'Do not generate download sites, downloader apps, app stores, content scrapers, or unauthorized distribution tools.'
messages.en.config.prohibitedGenerationRule = 'The keyword "{keyword}" is prohibited. Download sites, downloader apps, content scrapers, and unauthorized distribution tools cannot be generated.'
messages.en.config.prohibitedGenerationBackendBlocked = 'Task blocked by policy: download sites, downloader apps, content scrapers, and unauthorized distribution tools cannot be generated.'
messages.en.config.clientFrozenByRiskDefaultReason = 'AI risk guard marked this client as high risk'
messages.en.config.clientFrozenByRiskUnknownUnfreezeTime = 'pending confirmation'
messages.en.config.clientFrozenByRisk = 'This client is frozen due to high risk: {reason}. Estimated unfreeze time: {unfreezeAt}. Sorry for the inconvenience.'

messages['zh-CN'].config.taskComplianceTitle = '合规确认'
messages['zh-CN'].config.taskComplianceAckLabel = '我确认本次任务不会制作应用商店/应用市场/分发平台、下载站、下载器或内容抓取下载类应用，且不用于钓鱼、仿冒、恶意分发等违法违规用途。'
messages['zh-CN'].config.taskUseCaseLabel = '用途说明'
messages['zh-CN'].config.taskUseCasePlaceholder = '请简要说明合法用途'
messages['zh-CN'].config.taskComplianceAckRequired = '创建任务前请先确认合规声明'
messages['zh-CN'].config.taskUseCaseRequired = '请填写用途说明（至少 {min} 个字）'
messages['zh-CN'].config.taskUseCaseTooLong = '用途说明过长（最多 {max} 个字）'
messages['zh-CN'].config.marketplaceBlocked = '任务已被风控拦截：疑似应用市场/分发平台场景'
messages['zh-CN'].config.prohibitedGenerationHint = '明确禁止生成“下载站”“下载器”、应用商店、内容抓取下载工具或未经授权的分发类应用。'
messages['zh-CN'].config.prohibitedGenerationRule = '命中禁止词“{keyword}”。平台禁止生成下载站、下载器、内容抓取下载工具或未经授权的分发类应用。'
messages['zh-CN'].config.prohibitedGenerationBackendBlocked = '任务已被风控拦截：禁止生成下载站、下载器、内容抓取下载工具或未经授权的分发类应用。'
messages['zh-CN'].config.clientFrozenByRiskDefaultReason = 'AI 风控判定当前客户端存在高风险'
messages['zh-CN'].config.clientFrozenByRiskUnknownUnfreezeTime = '待确认'
messages['zh-CN'].config.clientFrozenByRisk = '当前客户端已被冻结：{reason}。预计解冻时间：{unfreezeAt}。给你带来不便，我们深表歉意。'

messages['zh-TW'].config.taskComplianceTitle = '合規確認'
messages['zh-TW'].config.taskComplianceAckLabel = '我確認本次任務不會製作應用商店/應用市場/分發平台、下載站、下載器或內容抓取下載類應用，且不用於釣魚、仿冒、惡意分發等違規用途。'
messages['zh-TW'].config.taskUseCaseLabel = '用途說明'
messages['zh-TW'].config.taskUseCasePlaceholder = '請簡要說明合法用途'
messages['zh-TW'].config.taskComplianceAckRequired = '建立任務前請先確認合規聲明'
messages['zh-TW'].config.taskUseCaseRequired = '請填寫用途說明（至少 {min} 個字）'
messages['zh-TW'].config.taskUseCaseTooLong = '用途說明過長（最多 {max} 個字）'
messages['zh-TW'].config.marketplaceBlocked = '任務已被風控攔截：疑似應用市場/分發平台場景'
messages['zh-TW'].config.prohibitedGenerationHint = '明確禁止生成「下載站」「下載器」、應用商店、內容抓取下載工具或未經授權的分發類應用。'
messages['zh-TW'].config.prohibitedGenerationRule = '命中禁止詞「{keyword}」。平台禁止生成下載站、下載器、內容抓取下載工具或未經授權的分發類應用。'
messages['zh-TW'].config.prohibitedGenerationBackendBlocked = '任務已被風控攬截：禁止生成下載站、下載器、內容抓取下載工具或未經授權的分發類應用。'
messages['zh-TW'].config.clientFrozenByRiskDefaultReason = 'AI 風控判定目前客戶端存在高風險'
messages['zh-TW'].config.clientFrozenByRiskUnknownUnfreezeTime = '待確認'
messages['zh-TW'].config.clientFrozenByRisk = '目前客戶端已凍結：{reason}。預計解凍時間：{unfreezeAt}。造成不便，我們深感抱歉。'
messages.en.toast.riskReviewPending = 'High-risk task detected. Waiting for admin review before build can start.'
messages.en.toast.riskReviewRejected = 'This task was rejected in risk review. Please contact admin for release.'
messages.en.toast.aiRiskReviewing = 'AI risk review in progress, please wait...'
messages.en.toast.riskReviewPendingWithReason = 'High-risk task detected: {reason}. Waiting for admin review before build can start.'
messages['zh-CN'].toast.riskReviewPending = '检测到高风险任务，需管理员审核通过后才能启动构建'
messages['zh-CN'].toast.riskReviewRejected = '该任务已被风控审核驳回，请联系管理员放行'
messages['zh-CN'].toast.aiRiskReviewing = '正在进行 AI 风控审核，请稍候'
messages['zh-CN'].toast.riskReviewPendingWithReason = '检测到高风险任务：{reason}，待管理员审核后才能启动构建'
messages['zh-TW'].toast.riskReviewPending = '偵測到高風險任務，需管理員審核通過後才能啟動建構'
messages['zh-TW'].toast.riskReviewRejected = '此任務已被風控審核駁回，請聯繫管理員放行'
messages['zh-TW'].toast.aiRiskReviewing = '正在進行 AI 風控審核，請稍候'
messages['zh-TW'].toast.riskReviewPendingWithReason = '偵測到高風險任務：{reason}，待管理員審核後才能啟動建構'

messages.en.mode.apk = 'WEB / Native ZIP to APK'
messages.en.upload.title = 'Project or Native Android ZIP'
messages.en.upload.subtitle = 'Upload a web project ZIP, static HTML package, or native Android Gradle project'
messages.en.upload.dragDrop = 'Drag & drop project ZIP here, or click to select'
messages.en.upload.hint = 'Auto-detects package.json, index.html, and native Android Gradle projects'

messages['zh-CN'].mode.apk = 'WEB/原生 ZIP转APK'
messages['zh-CN'].upload.title = '项目或原生 Android ZIP'
messages['zh-CN'].upload.subtitle = '上传 Web 项目 ZIP、静态 HTML 包或原生 Android Gradle 工程'
messages['zh-CN'].upload.dragDrop = '拖放项目 ZIP 到此处，或点击选择'
messages['zh-CN'].upload.hint = '自动识别 package.json、index.html 与原生 Android Gradle 工程'

messages['zh-TW'].mode.apk = 'WEB/原生 ZIP轉APK'
messages['zh-TW'].upload.title = '專案或原生 Android ZIP'
messages['zh-TW'].upload.subtitle = '上傳 Web 專案 ZIP、靜態 HTML 包或原生 Android Gradle 專案'
messages['zh-TW'].upload.dragDrop = '拖放專案 ZIP 到此處，或點擊選擇'
messages['zh-TW'].upload.hint = '自動識別 package.json、index.html 與原生 Android Gradle 專案'

// 构建产物三天下载期提示
const outputRetentionMessages = {
  en: {
    tasks: {
      outputRetention: 'Download available for {days} days, expires at {date}.',
      outputRetentionExpired: 'The {days}-day download period has expired and the file was cleaned automatically.'
    },
    toast: {
      outputExpired: 'The {days}-day download period has expired. The file has been cleaned automatically.'
    }
  },
  'zh-CN': {
    tasks: {
      outputRetention: '生成成功后可下载 {days} 天，到期时间：{date}',
      outputRetentionExpired: '{days} 天下载期已结束，系统已自动清理该产物。'
    },
    toast: {
      outputExpired: '{days} 天下载期已结束，系统已自动清理该产物。'
    }
  },
  'zh-TW': {
    tasks: {
      outputRetention: '生成成功後可下載 {days} 天，到期時間：{date}',
      outputRetentionExpired: '{days} 天下載期已結束，系統已自動清理該產物。'
    },
    toast: {
      outputExpired: '{days} 天下載期已結束，系統已自動清理該產物。'
    }
  },
  ja: {
    tasks: {
      outputRetention: '生成後 {days} 日間ダウンロードできます。有効期限: {date}',
      outputRetentionExpired: '{days} 日間のダウンロード期間が終了し、ファイルは自動削除されました。'
    },
    toast: {
      outputExpired: '{days} 日間のダウンロード期間が終了し、ファイルは自動削除されました。'
    }
  },
  ko: {
    tasks: {
      outputRetention: '생성 후 {days}일 동안 다운로드할 수 있습니다. 만료 시간: {date}',
      outputRetentionExpired: '{days}일 다운로드 기간이 끝나 파일이 자동 정리되었습니다.'
    },
    toast: {
      outputExpired: '{days}일 다운로드 기간이 끝나 파일이 자동 정리되었습니다.'
    }
  }
}

Object.entries(outputRetentionMessages).forEach(([locale, sections]) => {
  messages[locale] = messages[locale] || {}
  Object.entries(sections).forEach(([section, values]) => {
    messages[locale][section] = messages[locale][section] || {}
    Object.assign(messages[locale][section], values)
  })
})