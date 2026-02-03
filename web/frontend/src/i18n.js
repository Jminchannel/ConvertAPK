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
    // Mode
    mode: {
      title: 'Conversion Mode',
      apk: 'Project to APK',
      web: 'Website to APK'
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
    // Steps
    steps: {
      upload: 'Upload Project',
      configure: 'Configure App',
      build: 'Build APK'
    },
    // Upload
    upload: {
      title: 'Project File',
      subtitle: 'Upload ZIP exported from Google AI Studio',
      dragDrop: 'Drag & drop ZIP file here, or click to select',
      hint: 'Supports React, Vue and other frontend projects',
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
      statusBarTitle: 'Status Bar',
      statusBarHidden: 'Hide Status Bar (Fullscreen)',
      statusBarBackground: 'Background',
      statusBarTransparent: 'Transparent',
      statusBarWhite: 'White',
      statusBarStyle: 'Icon Style',
      statusBarStyleDark: 'Dark Icons',
      statusBarStyleLight: 'Light Icons',
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
      creating: 'Processing...',
      updateMode: 'Update Mode',
      updateHint: 'Updating existing app, will reuse signing key',
      quickGenerate: 'One-click Generate',
      quickGenerateHint: 'Hide the form and use system-generated defaults',
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
      start: 'Start Build',
      download: 'Download Product',
      downloadMenu: 'Download Menu',
      downloadSigned: 'Download Keystore',
      delete: 'Delete',
      confirmDelete: 'Delete this task?',
      waiting: 'Waiting',
      jump: 'Jump to',
      go: 'Go'
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
      noLogs: 'No log records',
      close: 'Close'
    },
    // Toast
    toast: {
      uploadSuccess: 'File uploaded successfully',
      uploadFailed: 'Upload failed',
      taskCreated: 'Build task created',
      taskStarted: 'Build task started',
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
        zipRequired: 'Please upload a ZIP file',
        iconSet: 'Icon updated',
        iconUploadFailed: 'Icon upload failed'
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
    // Mode
    mode: {
      title: '转换模式',
      apk: '项目转 APK',
      web: '网页转 APK'
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
    // Steps
    steps: {
      upload: '上传项目',
      configure: '配置应用',
      build: '构建APK'
    },
    // Upload
    upload: {
      title: '项目文件',
      subtitle: '上传 Google AI Studio 导出的 ZIP 包',
      dragDrop: '拖放 ZIP 文件到此处，或点击选择',
      hint: '支持 React、Vue 等前端项目',
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
      statusBarTitle: '状态栏设置',
      statusBarHidden: '隐藏状态栏 (全屏)',
      statusBarBackground: '背景颜色',
      statusBarTransparent: '透明',
      statusBarWhite: '白底',
      statusBarStyle: '图标风格',
      statusBarStyleDark: '深色图标',
      statusBarStyleLight: '浅色图标',
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
      creating: '处理中...',
      updateMode: '更新模式',
      updateHint: '正在更新已有应用，将复用原有签名密钥',
      quickGenerate: '一键生成',
      quickGenerateHint: '隐藏配置表单，使用系统默认生成配置',
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
      jump: '跳转页码',
      go: '跳转'
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
      noLogs: '暂无日志记录',
      close: '关闭'
    },
    // Toast
    toast: {
      uploadSuccess: '文件上传成功',
      uploadFailed: '上传失败',
      taskCreated: '构建任务已创建',
      taskStarted: '构建任务已启动',
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
        feedbackDailyLimit: '今日反馈次数已达上限'
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
    // Mode
    mode: {
      title: '轉換模式',
      apk: '專案轉 APK',
      web: '網頁轉 APK'
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
    // Steps
    steps: {
      upload: '上傳專案',
      configure: '設定應用',
      build: '建構APK'
    },
    // Upload
    upload: {
      title: '專案檔案',
      subtitle: '上傳 Google AI Studio 匯出的 ZIP 包',
      dragDrop: '拖放 ZIP 檔案到此處，或點擊選擇',
      hint: '支援 React、Vue 等前端專案',
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
      statusBarTitle: '狀態欄設置',
      statusBarHidden: '隱藏狀態欄 (全屏)',
      statusBarBackground: '背景顏色',
      statusBarTransparent: '透明',
      statusBarWhite: '白底',
      statusBarStyle: '圖標風格',
      statusBarStyleDark: '深色圖標',
      statusBarStyleLight: '淺色圖標',
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
      creating: '處理中...',
      updateMode: '更新模式',
      updateHint: '正在更新已有應用，將複用原有簽名金鑰',
      quickGenerate: '一鍵生成',
      quickGenerateHint: '隱藏設定表單，使用系統預設自動產生',
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
      jump: '跳轉頁碼',
      go: '跳轉'
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
      noLogs: '暫無日誌記錄',
      refreshLogs: '重新整理日誌',
      logCount: '共 {count} 條日誌',
      close: '關閉'
    },
    // Toast
    toast: {
      uploadSuccess: '檔案上傳成功',
      uploadFailed: '上傳失敗',
      taskCreated: '建構任務已建立',
      taskStarted: '建構任務已啟動',
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
        feedbackDailyLimit: '今日回饋次數已達上限'
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
  return localStorage.getItem('apk_builder_theme') || 'dark'
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
