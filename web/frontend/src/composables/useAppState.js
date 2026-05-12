import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { EditorState, Compartment } from '@codemirror/state'
import {
  EditorView,
  keymap,
  lineNumbers,
  highlightActiveLine,
  highlightActiveLineGutter,
  highlightSpecialChars,
  drawSelection,
  dropCursor,
  rectangularSelection
} from '@codemirror/view'
import {
  defaultHighlightStyle,
  syntaxHighlighting,
  indentOnInput,
  bracketMatching,
  foldGutter,
  foldKeymap,
  syntaxTree,
  ensureSyntaxTree
} from '@codemirror/language'
import { html } from '@codemirror/lang-html'
import { defaultKeymap, history, historyKeymap, indentWithTab } from '@codemirror/commands'
import { autocompletion, completionKeymap, closeBrackets, closeBracketsKeymap } from '@codemirror/autocomplete'
import { lintGutter, setDiagnostics } from '@codemirror/lint'
import { searchKeymap, highlightSelectionMatches } from '@codemirror/search'
import * as api from '../api'
import { getSavedLanguage, saveLanguage, getSavedTheme, saveTheme, createI18n } from '../i18n'
import {
  jsTemplate,
  permissionsList,
  normalizePermissionForUi,
  normalizePermissionsForUi,
  defaultHtmlTemplate,
  isValidPackageName,
  isValidUrl,
  isValidHostName,
  isValidPort,
  isValidWebUrl,
  formatFileSize,
  formatDate,
  parseVersionParts,
  compareVersion,
  bumpPatchVersion
} from '../utils/appShared'

export const useAppState = () => {
  const alipayQr = new URL('../pics/支付宝.png', import.meta.url).href
  const wechatQr = new URL('../pics/微信.png', import.meta.url).href

  // Theme / Language
  const currentTheme = ref(getSavedTheme())
  const currentLang = ref(getSavedLanguage())
  const showLangMenu = ref(false)
  const openDownloadMenu = ref(null)
  const githubRepoUrl = ref('https://github.com/Jminchannel/ConvertAPK-Desktop')
  const githubStarCount = ref(null)
  const languages = [
    { code: 'en', label: 'English' },
    { code: 'zh-CN', label: '简体中文' },
    { code: 'zh-TW', label: '繁體中文' }
  ]
  const currentLangLabel = computed(() => {
    const lang = languages.find((l) => l.code === currentLang.value)
    return lang ? lang.label : 'Language'
  })
  const hasGithubStarCount = computed(() => Number.isFinite(githubStarCount.value) && githubStarCount.value >= 0)
  const githubStarCountText = computed(() => {
    const count = Number(githubStarCount.value)
    if (!Number.isFinite(count) || count < 0) return ''
    if (count < 1000) return String(count)
    if (count < 10000) return `${(count / 1000).toFixed(1).replace(/\.0$/, '')}k`
    if (count < 1000000) return `${Math.round(count / 1000)}k`
    return `${(count / 1000000).toFixed(1).replace(/\.0$/, '')}M`
  })

  const i18n = ref(createI18n(currentLang.value))
  const t = (key, params) => i18n.value.t(key, params)

  const applyTheme = (theme) => {
    if (theme === 'light') document.documentElement.classList.add('light-theme')
    else document.documentElement.classList.remove('light-theme')
  }

  const toggleTheme = () => {
    const newTheme = currentTheme.value === 'dark' ? 'light' : 'dark'
    currentTheme.value = newTheme
    saveTheme(newTheme)
    applyTheme(newTheme)
  }

  // 把 i18n 语言代码映射为符合 BCP 47 规范的 html lang 属性值
  const normalizeHtmlLang = (lang) => {
    if (lang === 'zh-CN' || lang === 'zh-TW') return lang
    return 'en'
  }

  const applyDocumentLang = (lang) => {
    if (typeof document !== 'undefined' && document.documentElement) {
      document.documentElement.lang = normalizeHtmlLang(lang)
    }
  }

  const changeLanguage = (lang) => {
    currentLang.value = lang
    saveLanguage(lang)
    i18n.value = createI18n(lang)
    // 同步 html[lang]，让屏幕阅读器发音正确
    applyDocumentLang(lang)
    showLangMenu.value = false
  }

  const toggleDownloadMenu = (taskId) => {
    openDownloadMenu.value = openDownloadMenu.value === taskId ? null : taskId
  }
  const closeDownloadMenu = () => {
    openDownloadMenu.value = null
  }

  const handleClickOutside = (e) => {
    if (!e.target.closest('.lang-switch')) showLangMenu.value = false
    if (!e.target.closest('.download-dropdown')) closeDownloadMenu()
  }

  // Modes & feature state
  const mode = ref('convert') // convert | web | html | desktop
  const featureFlags = ref({
    web_link_to_apk_enabled: false,
    zip_to_desktop_enabled: false,
    rewarded_build_ads_enabled: false,
    client_login_enabled: true,
    client_sms_login_enabled: false,
    client_register_enabled: true,
  })
  const isWebModeEnabled = computed(() => Boolean(featureFlags.value.web_link_to_apk_enabled))
  const isDesktopModeEnabled = computed(() => Boolean(featureFlags.value.zip_to_desktop_enabled))
  const isRewardedBuildAdsEnabled = computed(() => Boolean(featureFlags.value.rewarded_build_ads_enabled))
  const isClientLoginEnabled = computed(() => featureFlags.value.client_login_enabled !== false)
  const isClientSmsLoginEnabled = computed(() => featureFlags.value.client_sms_login_enabled === true)
  const isClientRegisterEnabled = computed(() => featureFlags.value.client_register_enabled !== false)
  const isAuthEntryEnabled = computed(() => isClientLoginEnabled.value || isClientRegisterEnabled.value)
  const desktopPortMin = 1024
  const desktopPortMax = 65535
  const desktopPortDefaultMin = 20000
  const desktopPortDefaultMax = 59999
  const desktopPopularPortSet = new Set([
    1080, 1433, 1521, 1883, 2049, 2375, 2376, 27017, 3000, 3306, 3389, 4000, 4200, 5000, 5001,
    5173, 5174, 5175, 5432, 5672, 5900, 6379, 7000, 7070, 8000, 8001, 8080, 8081, 8088, 8443,
    8888, 9000, 9001, 9002, 9090, 9200, 9300, 27018
  ])

  const generateDesktopPort = () => {
    for (let i = 0; i < 160; i += 1) {
      const candidate = Math.floor(Math.random() * (desktopPortDefaultMax - desktopPortDefaultMin + 1)) + desktopPortDefaultMin
      if (!desktopPopularPortSet.has(candidate)) {
        return candidate
      }
    }
    return 52001
  }

  const normalizeDesktopPort = (value) => {
    const port = Number(value)
    if (!Number.isInteger(port)) return generateDesktopPort()
    if (port < desktopPortMin || port > desktopPortMax) return generateDesktopPort()
    return port
  }
  const mainRef = ref(null)
  const mobilePageHeadRef = ref(null)
  const convertUploadSection = ref(null)
  const htmlUploadSection = ref(null)
  const webUrlSection = ref(null)
  const tasksSection = ref(null)
  const profileSection = ref(null)
  const webUrl = ref('')
  const enableAds = ref(false)
  const adConfig = ref({ appId: '', appKey: '', placementId: '' })
  const enablePermissions = ref(false)
  const useCustomKeystore = ref(false)
  const quickGenerate = ref(false)
  const quickGenerateStash = ref(null)
  const codeCopied = ref(false)
  const mobileTab = ref('build') // build | tasks | profile
  const isMobileShell = ref(false)
  const mobileSettingsLabel = computed(() => {
    if (currentLang.value === 'zh-CN') return '设置'
    if (currentLang.value === 'zh-TW') return '設定'
    return 'Settings'
  })
  const mobileTabTitle = computed(() => {
    if (mobileTab.value === 'tasks') return t('tasks.title')
    if (mobileTab.value === 'profile') return mobileSettingsLabel.value
    return t('config.title')
  })
  const mobileTabSubtitle = computed(() => {
    if (mobileTab.value === 'tasks') return t('tasks.subtitle')
    if (mobileTab.value === 'profile') return t('settings.feedbackSection')
    return mode.value === 'web' ? t('web.urlHint') : t('config.subtitle')
  })
  const siteContentByLang = {
    en: {
      nav: {
        help: 'Help',
        privacy: 'Privacy',
        terms: 'Terms',
        about: 'About'
      },
      trustTitle: 'Build Android packages with clear rules',
      trustSubtitle: 'ConvertAPK focuses on lawful packaging workflows: upload projects you own, configure signing clearly, and download only the artifacts produced by your own task.',
      guideTitle: 'Publisher-friendly resources',
      guideSubtitle: 'Original guides and policies keep the service understandable for users and safer for advertising review.',
      guideCards: [
        {
          title: 'Safe packaging guide',
          body: 'Learn which project files are supported, how signing works, and why unauthorized apps, cracked packages, and harmful software are not accepted.',
          href: '/help.html'
        },
        {
          title: 'Privacy and ads',
          body: 'Review how task files, logs, cookies, and advertising partners are handled before using the web service.',
          href: '/privacy.html'
        },
        {
          title: 'Service terms',
          body: 'Understand acceptable use, ownership requirements, prohibited content, and download responsibility.',
          href: '/terms.html'
        }
      ],
      footerNote: 'Use this service only for apps, websites, and assets you own or are authorized to package.',
      adLabel: 'Advertisement',
      adPreview: 'AdSense slot preview'
    },
    'zh-CN': {
      nav: {
        help: '帮助',
        privacy: '隐私',
        terms: '条款',
        about: '关于'
      },
      trustTitle: '在清晰规则下构建 Android 安装包',
      trustSubtitle: 'ConvertAPK 专注合法打包流程：上传你拥有或已获授权的项目，清楚配置签名，并只下载自己任务生成的产物。',
      guideTitle: '适合审核的内容与合规入口',
      guideSubtitle: '原创说明和公开政策能帮助用户理解服务，也能降低广告审核与后续投放风险。',
      guideCards: [
        {
          title: '安全打包指南',
          body: '了解支持的项目文件、签名流程，以及为什么不接受未授权应用、破解包和有害软件。',
          href: '/help.html'
        },
        {
          title: '隐私与广告',
          body: '使用网站前，可查看任务文件、日志、Cookie 与广告合作方数据的处理方式。',
          href: '/privacy.html'
        },
        {
          title: '服务条款',
          body: '了解可接受使用、权属要求、禁止内容以及下载产物的责任边界。',
          href: '/terms.html'
        }
      ],
      footerNote: '请仅将本服务用于你拥有或已获授权打包的应用、网站和素材。',
      adLabel: '广告',
      adPreview: 'AdSense 广告位预览'
    },
    'zh-TW': {
      nav: {
        help: '幫助',
        privacy: '隱私',
        terms: '條款',
        about: '關於'
      },
      trustTitle: '在清晰規則下建置 Android 安裝包',
      trustSubtitle: 'ConvertAPK 專注合法打包流程：上傳你擁有或已獲授權的專案，清楚設定簽名，並只下載自己任務產生的成品。',
      guideTitle: '適合審核的內容與合規入口',
      guideSubtitle: '原創說明和公開政策能幫助使用者理解服務，也能降低廣告審核與後續投放風險。',
      guideCards: [
        {
          title: '安全打包指南',
          body: '了解支援的專案檔案、簽名流程，以及為什麼不接受未授權應用、破解包和有害軟體。',
          href: '/help.html'
        },
        {
          title: '隱私與廣告',
          body: '使用網站前，可查看任務檔案、日誌、Cookie 與廣告合作方資料的處理方式。',
          href: '/privacy.html'
        },
        {
          title: '服務條款',
          body: '了解可接受使用、權屬要求、禁止內容以及下載成品的責任邊界。',
          href: '/terms.html'
        }
      ],
      footerNote: '請僅將本服務用於你擁有或已獲授權打包的應用、網站和素材。',
      adLabel: '廣告',
      adPreview: 'AdSense 廣告位預覽'
    }
  }
  const siteContent = computed(() => siteContentByLang[currentLang.value] || siteContentByLang.en)
  const mobileTabs = ['build', 'tasks', 'profile']
  const mobilePageAnimClass = ref('')
  const mobileSwipeOffsetX = ref(0)
  const mobileSwipeDragging = ref(false)
  const mobileSwipeTracking = ref(false)
  let mobileSwipeStartX = 0
  let mobileSwipeStartY = 0
  let mobileSwipeStartTime = 0
  let mobileSwipeAnimTimer = null

  const getMobileTabIndex = (tab) => mobileTabs.indexOf(tab)

  const setMobilePageTransition = (fromTab, toTab) => {
    if (!isMobileShell.value) return
    const fromIndex = getMobileTabIndex(fromTab)
    const toIndex = getMobileTabIndex(toTab)
    if (fromIndex < 0 || toIndex < 0 || fromIndex === toIndex) return
    mobilePageAnimClass.value = toIndex > fromIndex ? 'mobile-page-swipe-left' : 'mobile-page-swipe-right'
    if (mobileSwipeAnimTimer) clearTimeout(mobileSwipeAnimTimer)
    mobileSwipeAnimTimer = setTimeout(() => {
      mobilePageAnimClass.value = ''
      mobileSwipeAnimTimer = null
    }, 280)
  }

  const isMobileViewport = () => {
    if (typeof window === 'undefined') return false
    if (window.matchMedia) return window.matchMedia('(max-width: 640px)').matches
    return window.innerWidth <= 640
  }

  const updateMobileShell = () => {
    isMobileShell.value = isMobileViewport()
    if (!isMobileShell.value) {
      mobileTab.value = 'build'
      mobilePageAnimClass.value = ''
      mobileSwipeOffsetX.value = 0
      mobileSwipeDragging.value = false
      mobileSwipeTracking.value = false
      if (mobileSwipeAnimTimer) {
        clearTimeout(mobileSwipeAnimTimer)
        mobileSwipeAnimTimer = null
      }
    }
  }

  const shouldIgnoreMobileSwipeTarget = (target) => {
    if (!target || typeof target.closest !== 'function') return false
    return Boolean(
      target.closest(
        'input, textarea, select, [contenteditable="true"], .cm-editor, .html-editor-toolbar, .html-error-list, .download-dropdown, .lang-menu'
      )
    )
  }

  const scrollWithinMain = async (target, offsetTop = 12) => {
    if (!target) return
    await nextTick()
    if (mainRef.value) {
      const container = mainRef.value
      const containerRect = container.getBoundingClientRect()
      const targetRect = target.getBoundingClientRect()
      const offset = targetRect.top - containerRect.top + container.scrollTop - offsetTop
      container.scrollTo({ top: Math.max(0, offset), behavior: 'smooth' })
      return
    }
    target.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  const scrollToMobileHeadAnchor = async () => {
    if (!isMobileShell.value) return
    if (mobilePageHeadRef.value) {
      await scrollWithinMain(mobilePageHeadRef.value, 0)
      return
    }
    if (mainRef.value) {
      mainRef.value.scrollTo({ top: 0, behavior: 'smooth' })
    }
  }

  const scrollToProjectSection = async () => {
    if (!isMobileViewport()) return
    if (isMobileShell.value) {
      await scrollToMobileHeadAnchor()
      return
    }
    const target = mode.value === 'convert' || mode.value === 'desktop'
      ? convertUploadSection.value
      : (mode.value === 'html' ? htmlUploadSection.value : webUrlSection.value)
    await scrollWithinMain(target)
  }

  const switchMobileTab = async (tab, options = {}) => {
    if (tab !== 'build' && tab !== 'tasks' && tab !== 'profile') return
    const shouldAnimate = Boolean(options.animate)
    const previousTab = mobileTab.value
    if (shouldAnimate && previousTab !== tab) {
      setMobilePageTransition(previousTab, tab)
    } else if (previousTab !== tab) {
      mobilePageAnimClass.value = ''
      if (mobileSwipeAnimTimer) {
        clearTimeout(mobileSwipeAnimTimer)
        mobileSwipeAnimTimer = null
      }
    }
    mobileTab.value = tab
    showLangMenu.value = false
    closeDownloadMenu()
    if (!isMobileShell.value) return
    await scrollToMobileHeadAnchor()
  }

  const handleMobileSwipeStart = (event) => {
    if (!isMobileShell.value) return
    if (!event.touches || event.touches.length !== 1) return
    if (shouldIgnoreMobileSwipeTarget(event.target)) return
    const touch = event.touches[0]
    mobileSwipeTracking.value = true
    mobileSwipeDragging.value = false
    mobileSwipeOffsetX.value = 0
    mobileSwipeStartX = touch.clientX
    mobileSwipeStartY = touch.clientY
    mobileSwipeStartTime = Date.now()
  }

  const handleMobileSwipeMove = (event) => {
    if (!mobileSwipeTracking.value) return
    if (!event.touches || event.touches.length !== 1) return
    const touch = event.touches[0]
    const dx = touch.clientX - mobileSwipeStartX
    const dy = touch.clientY - mobileSwipeStartY

    if (!mobileSwipeDragging.value) {
      if (Math.abs(dx) < 8) return
      if (Math.abs(dy) > Math.abs(dx) * 0.9) {
        mobileSwipeTracking.value = false
        mobileSwipeOffsetX.value = 0
        return
      }
      mobileSwipeDragging.value = true
    }

    event.preventDefault()
    const currentIndex = getMobileTabIndex(mobileTab.value)
    const atFirst = currentIndex <= 0
    const atLast = currentIndex >= mobileTabs.length - 1
    let effectiveDx = dx
    if ((effectiveDx > 0 && atFirst) || (effectiveDx < 0 && atLast)) {
      effectiveDx *= 0.28
    }
    mobileSwipeOffsetX.value = Math.max(-120, Math.min(120, effectiveDx))
  }

  const finishMobileSwipe = (cancelled = false) => {
    if (!mobileSwipeTracking.value) {
      mobileSwipeDragging.value = false
      mobileSwipeOffsetX.value = 0
      return
    }
    const dx = mobileSwipeOffsetX.value
    const elapsed = Math.max(1, Date.now() - mobileSwipeStartTime)
    const velocity = Math.abs(dx) / elapsed
    const shouldSwitch = !cancelled && mobileSwipeDragging.value && (Math.abs(dx) >= 56 || velocity >= 0.45)

    if (shouldSwitch) {
      const currentIndex = getMobileTabIndex(mobileTab.value)
      const nextIndex = dx < 0 ? currentIndex + 1 : currentIndex - 1
      const nextTab = mobileTabs[nextIndex]
      if (nextTab) {
        switchMobileTab(nextTab, { animate: true })
      }
    }

    mobileSwipeTracking.value = false
    mobileSwipeDragging.value = false
    mobileSwipeOffsetX.value = 0
  }

  const handleMobileSwipeEnd = () => {
    finishMobileSwipe(false)
  }

  const handleMobileSwipeCancel = () => {
    finishMobileSwipe(true)
  }

  const mobileSwipeStyle = computed(() => {
    if (!isMobileShell.value) return null
    return {
      transform: `translate3d(${mobileSwipeOffsetX.value}px, 0, 0)`,
      transition: mobileSwipeDragging.value ? 'none' : 'transform 260ms cubic-bezier(0.22, 1, 0.36, 1)'
    }
  })

  const handleModeChange = (value) => {
    if (value === 'web' && !isWebModeEnabled.value) {
      showToast('Web（链接）转 APK 模式已关闭', 'error')
      return
    }
    if (value === 'desktop' && !isDesktopModeEnabled.value) {
      showToast(t('toast.desktopModeDisabled'), 'error')
      return
    }
    mode.value = value
    if (isMobileShell.value) {
      const previousTab = mobileTab.value
      mobileTab.value = 'build'
      if (previousTab !== 'build') {
        setMobilePageTransition(previousTab, 'build')
      }
    }
    resetForm()
    scrollToProjectSection()
  }


  const copyJsCode = () => {
    navigator.clipboard.writeText(jsTemplate).then(() => {
      codeCopied.value = true
      setTimeout(() => (codeCopied.value = false), 2000)
    })
  }


  // Task flow

  const currentStep = ref(1)
  const isDragging = ref(false)
  const isHtmlDragging = ref(false)
  const fileInput = ref(null)
  const htmlInput = ref(null)
  const htmlInputMode = ref('file')
  const htmlEditorContainer = ref(null)
  const htmlEditorModalContainer = ref(null)
  const htmlEditorInstance = ref(null)
  const htmlEditorReady = ref(false)
  const htmlEditorContent = ref(defaultHtmlTemplate)
  const htmlEditorDirty = ref(false)
  const htmlEditorMarkers = ref([])
  const htmlSavedContent = ref('')
  const htmlSavedUploadContent = ref('')
  const showHtmlEditorModal = ref(false)
  const showHtmlPreviewModal = ref(false)
  const htmlPreviewContent = ref('')
  const iconInput = ref(null)
  const keystoreInput = ref(null)
  const uploadedKeystore = ref(null)
  const keystoreUploadError = ref('')
  const uploadedFile = ref(null)
  const uploadedHtmlFile = ref(null)
  const uploadProgress = ref(0)
  const htmlUploadProgress = ref(0)
  const isCreating = ref(false)
  const cdnScanLoading = ref(false)
  const showCdnLocalizeModal = ref(false)
  const cdnLinkItems = ref([])
  const cdnSelectedUrls = ref([])
  const cdnLocalizeEnabled = ref(true)
  const hasCdnExternalLinks = computed(() => cdnLinkItems.value.length > 0)
  const cdnSelectedCount = computed(() => cdnSelectedUrls.value.length)
  const cdnAllSelected = computed(() => hasCdnExternalLinks.value && cdnSelectedUrls.value.length === cdnLinkItems.value.length)
  const cdnLocalizeAdvised = computed(() => (mode.value === 'convert' || mode.value === 'html') && hasCdnExternalLinks.value && !cdnLocalizeEnabled.value)
  const isHtmlUploading = computed(() => htmlUploadProgress.value > 0 && htmlUploadProgress.value < 100)
  const htmlEditorContentEmpty = computed(() => !htmlEditorContent.value.trim())
  const htmlErrorCount = computed(() => htmlEditorMarkers.value.filter((marker) => marker.severity === 'error').length)
  const hasSavedHtmlContent = computed(() => Boolean(htmlSavedContent.value))
  const canSaveEditorHtml = computed(() => !isHtmlUploading.value && !htmlEditorContentEmpty.value)
  const canUseSavedHtmlForBuild = computed(() => hasSavedHtmlContent.value && !htmlEditorDirty.value)

  const htmlEditorLoading = ref(false)
  const htmlEditorThemeCompartment = new Compartment()
  let isHtmlProgrammaticUpdate = false
  let htmlDiagnosticsHandle = null

  // Tasks & queue
  const tasks = ref([])
  const queueStatus = ref({ queue_size: 0, running_count: 0, max_concurrent: 1 })
  let pollInterval = null
  let githubStatsInterval = null
  let desktopOutputHeartbeatInterval = null
  let desktopOutputRefreshTimer = null
  let desktopOutputExitHandled = false
  const desktopOutputTabRegistryKey = 'apk_builder_desktop_output_tabs'
  const desktopOutputHeartbeatTtlMs = 90000
  const desktopOutputHeartbeatIntervalMs = 15000
  const desktopOutputTabId = (() => {
    if (typeof window !== 'undefined' && window.crypto && typeof window.crypto.randomUUID === 'function') {
      return window.crypto.randomUUID()
    }
    return `desktop_tab_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`
  })()

  // Settings
  const showSettings = ref(false)
  const announcements = ref([])
  const deviceInfo = ref({ cpu: '', ram: '', os: '', cores: '' })
  const feedbackContent = ref('')
  const feedbackImages = ref([])
  const feedbackFileInput = ref(null)
  const feedbackSubmitting = ref(false)
  const showDonation = ref(false)
  const donationHideChecked = ref(false)
  const donationAutoDisabled = ref(localStorage.getItem('apk_builder_donation_hide') === '1')
  const showComplianceNotice = ref(true)
  const taskComplianceAck = ref(false)
  const taskDeclaredUseCase = ref('')
  const taskDeclaredUseCaseMinLength = 6
  const taskDeclaredUseCaseMaxLength = 200
  const previousVersionName = ref('')
  const clientFreezeState = ref({
    frozen: false,
    reason: '',
    contact: '',
    source_task_id: '',
    frozen_at: '',
    cooldown_remaining_seconds: 0,
    cooldown_seconds: 600
  })

  const complianceNoticeByLang = {
    en: {
      title: 'User Service Agreement',
      effectiveDateLabel: 'Effective date',
      effectiveDate: '2026-04-10',
      intro:
        'Please read this agreement carefully before using the client and related services. By clicking "Agree and Continue", you confirm that you have read, understood, and accepted all terms.',
      sections: [
        {
          title: '1. Scope and Acceptance',
          lines: [
            'This agreement applies to all features provided by this client, including upload, packaging, build, download, and log viewing.',
            'If you do not agree with any term, please stop using the service immediately.'
          ]
        },
        {
          title: '2. Account and Security',
          lines: [
            'You are responsible for your account, verification code, device, and operation security.',
            'You must not lend, rent, sell, or share your account with others.'
          ]
        },
        {
          title: '3. Service Rules',
          lines: [
            'Services are provided on an "as is" basis and may be interrupted due to maintenance, upgrades, or force majeure.',
            'We may adjust features, usage limits, or service availability when necessary for compliance and security.'
          ]
        },
        {
          title: '4. User Conduct',
          lines: [
            'Do not publish illegal, infringing, fraudulent, malicious, or harmful content.',
            'You must ensure you have lawful rights or authorization for all uploaded materials.',
            'Do not attack, reverse-engineer, or abuse the platform in any way.'
          ]
        },
        {
          title: '5. Intellectual Property',
          lines: [
            'The software, interface, and related technical materials of this client are protected by law.',
            'You remain responsible for the legality and ownership of the content you upload or generate.'
          ]
        },
        {
          title: '6. Liability and Remedies',
          lines: [
            'If your violation causes claims, penalties, or losses, you shall bear corresponding legal liability.',
            'For suspected violations, we may suspend tasks, restrict features, or terminate service according to law.'
          ]
        },
        {
          title: '7. Updates and Disputes',
          lines: [
            'We may update this agreement and notify you by announcement, dialog, or system notice.',
            'Continued use after update means you accept the revised terms.'
          ]
        }
      ],
      legalReferences:
        'Contact email: 2952299066@qq.com. If you have any questions about this agreement, please contact us by email.',
      acceptButton: 'Agree and Continue',
      rejectButton: 'Decline and Exit'
    },
    'zh-CN': {
      title: '用户使用协议',
      effectiveDateLabel: '生效日期',
      effectiveDate: '2026-04-10',
      intro:
        '在你使用本客户端及相关服务前，请完整阅读并充分理解本协议。你点击“同意并继续”或实际使用本服务，即视为你与平台就本协议达成具有法律约束力的合意。',
      sections: [
        {
          title: '一、协议效力与适用范围',
          lines: [
            '本协议适用于本客户端提供的全部功能与服务，并对你与平台均具有法律约束力。',
            '你不同意本协议任何内容的，应立即停止使用并卸载客户端。'
          ]
        },
        {
          title: '二、账号义务与安全责任',
          lines: [
            '你必须提供真实、准确、合法的信息，并持续保持信息有效。',
            '你应妥善保管账号与设备，因账号被盗用、泄露或借用产生的一切后果由你自行承担。'
          ]
        },
        {
          title: '三、合规使用与禁止行为',
          lines: [
            '严禁制作、上传、传播违法违规、侵权、诈骗、恶意程序或危害网络安全的内容。',
            '严禁攻击、破解、逆向、绕过安全策略、批量滥用或以任何方式干扰平台正常运行。'
          ]
        },
        {
          title: '四、内容权利与授权保证',
          lines: [
            '你保证对上传、生成、发布内容享有合法权利或已取得充分授权，不得侵犯第三方合法权益。',
            '因内容侵权、违法或违约引发的投诉、索赔、处罚及损失，全部由你承担并赔偿。'
          ]
        },
        {
          title: '五、平台处置权',
          lines: [
            '对涉嫌违规或存在安全风险的行为，平台有权立即采取删除内容、中止任务、限制功能、封禁账号、终止服务等措施。',
            '平台有权保存并向监管、司法机关提供必要记录和证据，你不得以任何理由要求豁免责任。'
          ]
        },
        {
          title: '六、免责与责任限制',
          lines: [
            '本服务按“现状”提供，平台不对服务不中断、无错误、完全满足你需求作任何明示或默示担保。',
            '因不可抗力、网络故障、第三方原因、系统维护或你自身原因造成的损失，平台在法律允许范围内不承担责任。'
          ]
        },
        {
          title: '七、协议变更与争议解决',
          lines: [
            '平台有权根据业务与法律法规变化单方更新本协议，并通过公告、弹窗或系统通知方式发布。',
            '你在协议更新后继续使用服务的，视为无条件接受更新条款；争议适用中国大陆法律并提交平台所在地有管辖权法院处理。'
          ]
        }
      ],
      legalReferences:
        '联系方式：2952299066@qq.com。你可通过该邮箱联系平台。',
      acceptButton: '同意并继续',
      rejectButton: '拒绝并退出'
    },
    'zh-TW': {
      title: '使用者服務協議',
      effectiveDateLabel: '生效日期',
      effectiveDate: '2026-04-10',
      intro:
        '在你使用本客戶端及相關服務前，請完整閱讀並充分理解本協議。你點擊「同意並繼續」或實際使用本服務，即視為你與平台就本協議達成具法律約束力之合意。',
      sections: [
        {
          title: '一、協議效力與適用範圍',
          lines: [
            '本協議適用於本客戶端提供之全部功能與服務，對你與平台均具有法律約束力。',
            '你不同意本協議任何內容者，應立即停止使用並解除安裝客戶端。'
          ]
        },
        {
          title: '二、帳號義務與安全責任',
          lines: [
            '你必須提供真實、準確、合法之資訊，並持續保持資訊有效。',
            '你應妥善保管帳號與設備；因帳號遭盜用、洩漏或借用所生之一切後果，均由你自行承擔。'
          ]
        },
        {
          title: '三、合規使用與禁止行為',
          lines: [
            '嚴禁製作、上傳、傳播違法違規、侵權、詐騙、惡意程式或危害網路安全之內容。',
            '嚴禁攻擊、破解、逆向、繞過安全策略、批量濫用或以任何方式干擾平台正常運行。'
          ]
        },
        {
          title: '四、內容權利與授權保證',
          lines: [
            '你保證對上傳、生成、發布內容享有合法權利或已取得充分授權，不得侵害第三方合法權益。',
            '因內容侵權、違法或違約所生之投訴、索賠、處罰及損失，概由你承擔並賠償。'
          ]
        },
        {
          title: '五、平台處置權',
          lines: [
            '對涉嫌違規或存在安全風險之行為，平台有權立即採取刪除內容、中止任務、限制功能、封禁帳號、終止服務等措施。',
            '平台有權保存並向監管、司法機關提供必要紀錄與證據，你不得以任何理由主張免責。'
          ]
        },
        {
          title: '六、免責與責任限制',
          lines: [
            '本服務按「現狀」提供，平台不對服務不中斷、無錯誤或完全符合你需求作任何明示或默示擔保。',
            '因不可抗力、網路故障、第三方原因、系統維護或你自身原因造成之損失，平台於法律允許範圍內不承擔責任。'
          ]
        },
        {
          title: '七、協議變更與爭議解決',
          lines: [
            '平台有權因業務與法律法規變化單方更新本協議，並透過公告、彈窗或系統通知方式發布。',
            '你於協議更新後繼續使用服務者，視為無條件接受更新條款；爭議適用中國大陸法律並提交平台所在地有管轄權法院處理。'
          ]
        }
      ],
      legalReferences:
        '聯絡方式：2952299066@qq.com。你可透過該電子郵件聯絡平台。',
      acceptButton: '同意並繼續',
      rejectButton: '拒絕並退出'
    }
  }
  const complianceNotice = computed(() => {
    if (currentLang.value === 'zh-CN') return complianceNoticeByLang['zh-CN']
    if (currentLang.value === 'zh-TW') return complianceNoticeByLang['zh-TW']
    return complianceNoticeByLang.en
  })
  const normalizedTaskDeclaredUseCase = computed(() => String(taskDeclaredUseCase.value || '').trim().replace(/\s+/g, ' '))
  const taskComplianceError = computed(() => {
    if (clientFreezeState.value.frozen) {
      return t('config.clientFrozenByRisk', {
        reason: clientFreezeState.value.reason || t('config.clientFrozenByRiskDefaultReason')
      })
    }
    if (updatingTaskId.value) return ''
    if (!taskComplianceAck.value) return t('config.taskComplianceAckRequired')
    const useCaseLength = normalizedTaskDeclaredUseCase.value.length
    if (useCaseLength < taskDeclaredUseCaseMinLength) {
      return t('config.taskUseCaseRequired', { min: taskDeclaredUseCaseMinLength })
    }
    if (useCaseLength > taskDeclaredUseCaseMaxLength) return t('config.taskUseCaseTooLong', { max: taskDeclaredUseCaseMaxLength })
    return ''
  })

  // Logs
  const showLogs = ref(false)
  const taskLogs = ref([])
  const currentLogTaskId = ref(null)
  const logsContainer = ref(null)
  const taskDiagnosis = ref(null)
  const taskDiagnosisLoading = ref(false)
  const taskDiagnosisError = ref('')
  const diagnosisPollIntervalMs = 1500
  const diagnosisPollMaxRounds = 40
  let diagnosisPollTimer = null
  let diagnosisPollRounds = 0

  const stopDiagnosisPolling = () => {
    if (diagnosisPollTimer) {
      clearTimeout(diagnosisPollTimer)
      diagnosisPollTimer = null
    }
    diagnosisPollRounds = 0
  }

  const scheduleDiagnosisPolling = () => {
    if (diagnosisPollTimer || !showLogs.value) return
    if (diagnosisPollRounds >= diagnosisPollMaxRounds) {
      stopDiagnosisPolling()
      return
    }
    diagnosisPollTimer = setTimeout(async () => {
      diagnosisPollTimer = null
      diagnosisPollRounds += 1
      await refreshTaskDiagnosis(false, true)
    }, diagnosisPollIntervalMs)
  }

  // Update existing task
  const updatingTaskId = ref(null)
  const updatingTask = ref(null)

  // Icon / Cropper
  const appIcon = ref(null)
  const appIconFile = ref(null)
  const uploadedIcon = ref(null)
  const iconError = ref('')
  const showCropper = ref(false)
  const cropperRef = ref(null)
  const cropperImageSrc = ref('')
  const cropperStencilProps = {
    aspectRatio: 1
  }
  const cropperDefaultSize = ({ boundaries }) => {
    const size = Math.min(boundaries.width, boundaries.height) * 0.72
    return { width: size, height: size }
  }

  // Window controls (Electron)
  const isMaximized = ref(false)
  const windowControlsAvailable = computed(() => Boolean(window.windowControls))

  const minimizeWindow = () => window.windowControls?.minimize?.()
  const toggleMaximizeWindow = async () => {
    await window.windowControls?.toggleMaximize?.()
    if (window.windowControls?.isMaximized) {
      isMaximized.value = await window.windowControls.isMaximized()
    }
  }
  const closeWindow = () => window.windowControls?.close?.()

  // Config
  const config = ref({
    app_name: '',
    package_name: '',
    version_name: '1.0.0',
    version_code: 1,
    output_format: 'apk',
    desktop_runtime: 'tauri',
    desktop_installer_mode: 'portable',
    desktop_port: generateDesktopPort(),
    orientation: 'portrait',
    double_click_exit: true,
    status_bar_hidden: false,
    status_bar_style: 'light',
    status_bar_color: '#FFFFFF',
    webview_user_agent: 'android',
    download_mode: 'picker',
    web_fill_mode: 'contain',
    permissions: ['INTERNET', 'ACCESS_NETWORK_STATE'],
    keystore_alias: '',
    keystore_password: '',
    key_password: ''
  })

  const applyQuickGenerateDefaults = () => {
    // Quick generate uses backend defaults for icon & signing file; clear any user uploads.
    if (appIcon.value && !appIcon.value.startsWith('/api/') && appIconFile.value) URL.revokeObjectURL(appIcon.value)
    appIcon.value = null
    appIconFile.value = null
    uploadedIcon.value = null
    iconError.value = ''

    uploadedKeystore.value = null
    useCustomKeystore.value = false
    keystoreUploadError.value = ''
    if (keystoreInput.value) keystoreInput.value.value = ''

    enablePermissions.value = true
    config.value = {
      ...config.value,
      app_name: 'demo',
      package_name: 'com.convertapk.demo',
      // Backend will auto-increment these on each task creation.
      version_name: '1.0.0',
      version_code: 1,
      output_format: 'apk',
      desktop_runtime: 'tauri',
      desktop_installer_mode: 'portable',
      desktop_port: normalizeDesktopPort(config.value.desktop_port),
      orientation: 'portrait',
      double_click_exit: true,
      status_bar_hidden: true,
      status_bar_style: 'light',
      status_bar_color: '#FFFFFF',
      download_mode: 'picker',
      web_fill_mode: 'contain',
      permissions: [...permissionsList],
      keystore_alias: 'key0',
      keystore_password: '123456',
      key_password: '123456'
    }
  }

  const stashQuickGenerateState = () => {
    quickGenerateStash.value = {
      config: JSON.parse(JSON.stringify(config.value)),
      enablePermissions: enablePermissions.value,
      useCustomKeystore: useCustomKeystore.value,
      keystoreUploadError: keystoreUploadError.value,
      uploadedKeystore: uploadedKeystore.value ? { ...uploadedKeystore.value } : null,
      iconError: iconError.value,
      uploadedIcon: uploadedIcon.value ? { ...uploadedIcon.value } : null,
      appIcon: appIcon.value,
      appIconFile: appIconFile.value
    }
  }

  const restoreQuickGenerateState = () => {
    const stash = quickGenerateStash.value
    if (!stash) return

    enablePermissions.value = Boolean(stash.enablePermissions)
    useCustomKeystore.value = Boolean(stash.useCustomKeystore)
    keystoreUploadError.value = String(stash.keystoreUploadError || '')
    uploadedKeystore.value = stash.uploadedKeystore || null

    iconError.value = String(stash.iconError || '')
    uploadedIcon.value = stash.uploadedIcon || null

    // Restore icon preview
    if (appIcon.value && !appIcon.value.startsWith('/api/') && appIconFile.value) {
      try { URL.revokeObjectURL(appIcon.value) } catch {}
    }
    appIconFile.value = stash.appIconFile || null
    if (appIconFile.value) {
      appIcon.value = URL.createObjectURL(appIconFile.value)
    } else {
      appIcon.value = stash.appIcon || null
    }

    config.value = stash.config || config.value

    // File inputs cannot be restored; reset the native value for cleanliness.
    if (keystoreInput.value) keystoreInput.value.value = ''
  }

  const enterQuickGenerate = () => {
    if (quickGenerate.value) return
    if ((mode.value !== 'convert' && mode.value !== 'web' && mode.value !== 'html') || updatingTaskId.value) return
    stashQuickGenerateState()
    quickGenerate.value = true
    applyQuickGenerateDefaults()
  }

  const exitQuickGenerate = () => {
    if (!quickGenerate.value) return
    quickGenerate.value = false
    restoreQuickGenerateState()
    quickGenerateStash.value = null
  }

  // Toast
  const toast = ref({ show: false, type: 'success', message: '' })
  const showToast = (message, type = 'success') => {
    toast.value = { show: true, type, message }
    setTimeout(() => (toast.value.show = false), 3000)
  }

  // 自定义确认对话框：替代原生 confirm()
  // 同一时刻仅保留一个 pending 的 Promise，避免多重弹窗导致状态紊乱
  const confirmDialog = ref({
    visible: false,
    title: '',
    message: '',
    confirmText: '',
    cancelText: '',
    confirmType: 'primary'
  })
  let confirmDialogResolver = null

  // 返回 Promise<boolean>，true 表示用户确认，false 表示取消
  const openConfirmDialog = ({ title = '', message = '', confirmText = '', cancelText = '', confirmType = 'primary' } = {}) => {
    // 如果上一个对话框还没关闭，先视为取消以释放上一个 Promise
    if (confirmDialogResolver) {
      try { confirmDialogResolver(false) } catch (_) {}
      confirmDialogResolver = null
    }
    // 根据当前语言选择兜底按钮文案
    const lang = currentLang.value || 'en'
    const defaultOk = lang === 'zh-CN' ? '确定' : lang === 'zh-TW' ? '確定' : 'OK'
    const defaultCancel = lang === 'zh-CN' ? '取消' : lang === 'zh-TW' ? '取消' : 'Cancel'
    confirmDialog.value = {
      visible: true,
      title,
      message,
      confirmText: confirmText || defaultOk,
      cancelText: cancelText || defaultCancel,
      confirmType
    }
    return new Promise((resolve) => {
      confirmDialogResolver = resolve
    })
  }

  const closeConfirmDialog = (result) => {
    if (confirmDialogResolver) {
      const resolver = confirmDialogResolver
      confirmDialogResolver = null
      resolver(Boolean(result))
    }
    confirmDialog.value = { ...confirmDialog.value, visible: false }
  }

  // 从 axios 错误对象中提取可用于开发调试的细节（仅用于 console），不直接展示给用户
  // 避免把后端堆栈、敏感字段泄露到 UI；参见 AGENTS.md 第 7 节
  const extractErrorDetailForLog = (error) => {
    if (!error) return ''
    if (typeof error === 'string') return error
    const detail = error?.response?.data?.detail
    const msg = error?.message
    if (typeof detail === 'string' && detail) return detail
    if (detail && typeof detail === 'object') {
      try { return JSON.stringify(detail) } catch { return '' }
    }
    return typeof msg === 'string' ? msg : ''
  }

  // 统一的错误提示入口：始终使用 i18n 文案，后端错误细节仅在控制台输出
  const showErrorToast = (i18nKey, error) => {
    const fallback = i18nKey ? t(i18nKey) : t('toast.operationFailed')
    try {
      // 仅开发调试：避免生产用户看到后端堆栈/敏感信息
      // eslint-disable-next-line no-console
      console.warn('[showErrorToast]', i18nKey, extractErrorDetailForLog(error))
    } catch {
      // ignore console 错误
    }
    showToast(fallback, 'error')
  }
  const getErrorDetailPayload = (error) => error?.response?.data?.detail
  const getErrorDetailText = (error) => {
    const detail = getErrorDetailPayload(error)
    if (typeof detail === 'string') return detail.trim().toLowerCase()
    if (detail && typeof detail === 'object') {
      const code = String(detail?.code || '').trim().toLowerCase()
      const message = String(detail?.message || '').trim().toLowerCase()
      const reason = String(detail?.reason || '').trim().toLowerCase()
      const source = `${code} ${message} ${reason}`.trim()
      if (source) return source
    }
    return String(error?.message || '').trim().toLowerCase()
  }
  const normalizeFreezeState = (payload = {}) => {
    const freeze = payload?.freeze && typeof payload.freeze === 'object' ? payload.freeze : payload
    const frozen = Boolean(payload?.frozen ?? freeze?.frozen)
    const reason = String(freeze?.reason || '').trim()
    const contact = String(freeze?.contact || '').trim()
    const sourceTaskId = String(freeze?.source_task_id || '').trim()
    const frozenAt = String(freeze?.frozen_at || '').trim()
    const cooldownRemainingSeconds = Number(payload?.cooldown_remaining_seconds || freeze?.cooldown_remaining_seconds || 0)
    const cooldownSeconds = Number(payload?.cooldown_seconds || freeze?.cooldown_seconds || 600)
    return {
      frozen,
      reason,
      contact,
      source_task_id: sourceTaskId,
      frozen_at: frozenAt,
      cooldown_remaining_seconds: Number.isFinite(cooldownRemainingSeconds) ? Math.max(0, Math.round(cooldownRemainingSeconds)) : 0,
      cooldown_seconds: Number.isFinite(cooldownSeconds) && cooldownSeconds > 0 ? Math.round(cooldownSeconds) : 600
    }
  }
  const extractClientFrozenDetail = (error) => {
    const detail = getErrorDetailPayload(error)
    if (detail && typeof detail === 'object') {
      const code = String(detail?.code || '').trim().toLowerCase()
      const message = String(detail?.message || '').trim().toLowerCase()
      if (code === 'client_frozen_by_ai_risk' || message.includes('client is frozen by ai risk guard')) {
        return normalizeFreezeState(detail)
      }
    }
    const detailText = getErrorDetailText(error)
    if (detailText.includes('client is frozen by ai risk guard')) {
      return normalizeFreezeState({ frozen: true })
    }
    return null
  }
  const applyClientFreezeState = (payload) => {
    clientFreezeState.value = normalizeFreezeState(payload || {})
  }
  const resolveCreateTaskErrorMessage = (error) => {
    const freezeDetail = extractClientFrozenDetail(error)
    if (freezeDetail && freezeDetail.frozen) {
      applyClientFreezeState(freezeDetail)
      return t('config.clientFrozenByRisk', {
        reason: freezeDetail.reason || t('config.clientFrozenByRiskDefaultReason')
      })
    }
    const detail = getErrorDetailText(error)
    if (!detail) return ''
    if (detail.includes('compliance confirmation is required')) return t('config.taskComplianceAckRequired')
    if (detail.includes('declared use case is required')) {
      return t('config.taskUseCaseRequired', { min: taskDeclaredUseCaseMinLength })
    }
    if (detail.includes('declared use case is too long')) return t('config.taskUseCaseTooLong', { max: taskDeclaredUseCaseMaxLength })
    if (detail.includes('task blocked by policy')) return t('config.marketplaceBlocked')
    if (detail.includes('task is pending admin risk review')) return t('toast.riskReviewPending')
    if (detail.includes('task was rejected by admin risk review')) return t('toast.riskReviewRejected')
    return ''
  }

  const resolveStartTaskErrorMessage = (error) => {
    const freezeDetail = extractClientFrozenDetail(error)
    if (freezeDetail && freezeDetail.frozen) {
      applyClientFreezeState(freezeDetail)
      return t('config.clientFrozenByRisk', {
        reason: freezeDetail.reason || t('config.clientFrozenByRiskDefaultReason')
      })
    }
    const detail = getErrorDetailText(error)
    if (!detail) return ''
    if (detail.includes('task is pending admin risk review')) return t('toast.riskReviewPending')
    if (detail.includes('task was rejected by admin risk review')) return t('toast.riskReviewRejected')
    return ''
  }

  const extractRiskReviewReason = (taskLike) => {
    if (!taskLike || typeof taskLike !== 'object') return ''
    const aiReason = String(taskLike?.risk_scan?.ai_guard?.reason || '').replace(/\s+/g, ' ').trim()
    if (aiReason) return aiReason.slice(0, 180)
    const reviewNote = String(taskLike?.review_note || '').replace(/\s+/g, ' ').trim()
    if (reviewNote) return reviewNote.slice(0, 180)
    const fieldHits = Array.isArray(taskLike?.risk_scan?.field_hits) ? taskLike.risk_scan.field_hits : []
    if (fieldHits.length) {
      const top = fieldHits
        .slice(0, 3)
        .map((item) => {
          const field = String(item?.field || '').trim()
          const keyword = String(item?.keyword || '').trim()
          if (field && keyword) return `${field}: ${keyword}`
          return keyword || field
        })
        .filter(Boolean)
      if (top.length) return top.join(' | ').slice(0, 180)
    }
    const domainHits = Array.isArray(taskLike?.risk_scan?.domain_hits) ? taskLike.risk_scan.domain_hits : []
    if (domainHits.length) {
      const topDomains = domainHits
        .slice(0, 3)
        .map((item) => String(item?.domain || item?.keyword || '').trim())
        .filter(Boolean)
      if (topDomains.length) return topDomains.join(' | ').slice(0, 180)
    }
    return ''
  }

  const extractClientFreezeStateFromTask = (taskLike) => {
    if (!taskLike || typeof taskLike !== 'object') return null
    const alert = taskLike?.risk_scan?.compliance_alert
    if (!alert || typeof alert !== 'object') return null
    const code = String(alert?.code || '').trim().toLowerCase()
    if (code !== 'client_frozen_by_ai_risk') return null
    const reason = String(alert?.reason || extractRiskReviewReason(taskLike) || '').trim()
    return normalizeFreezeState({
      frozen: true,
      freeze: {
        reason,
        contact: String(alert?.contact || '').trim(),
        source_task_id: String(alert?.source_task_id || '').trim(),
        frozen_at: String(alert?.frozen_at || '').trim(),
      },
    })
  }

  const isRiskReviewPendingError = (error) => getErrorDetailText(error).includes('task is pending admin risk review')
  const isRiskReviewRejectedError = (error) => getErrorDetailText(error).includes('task was rejected by admin risk review')

  const showAuthModal = ref(false)
  const authMode = ref('login')
  const authLoginMethod = ref('password')
  const authSubmitting = ref(false)
  const githubAuthSubmitting = ref(false)
  const authSmsSending = ref(false)
  const authSmsCountdown = ref(0)
  const authSubmitButtonShake = ref(false)
  const authError = ref('')
  const authForm = ref({
    email: '',
    phone: '',
    code: '',
    password: '',
    confirmPassword: ''
  })
  const authUser = ref(null)
  const authEmailPattern = /^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$/
  const authSmsCodePattern = /^\d{6}$/
  let authShakeTimer = null
  let authSmsCountdownTimer = null

  const isLoggedIn = computed(() => Boolean(api.getAuthToken() && authUser.value?.id))
  const authDisplayName = computed(() => {
    const user = authUser.value || {}
    const githubLogin = String(user.github_login || '').trim()
    const email = String(user.email || '').trim()
    const phone = String(user.phone || '').trim()
    return githubLogin || email || phone || ''
  })

  const extractAuthErrorDetail = (errorLike) => {
    if (typeof errorLike === 'string') return errorLike.trim()
    return String(errorLike?.response?.data?.detail || errorLike?.message || '').trim()
  }

  const resolveAuthErrorMessage = (errorLike) => {
    const detail = extractAuthErrorDetail(errorLike).toLowerCase()
    if (!detail) return t('auth.errorGeneral')
    if (detail.includes('login is disabled by admin')) return t('auth.loginDisabled')
    if (detail.includes('register is disabled by admin')) return t('auth.registerDisabled')
    if (detail.includes('login_disabled')) return t('auth.loginDisabled')
    if (detail.includes('sms login is disabled by admin')) return t('auth.smsLoginDisabled')
    if (detail.includes('email format')) return t('auth.errorEmailFormat')
    if (detail.includes('phone format')) return t('auth.errorPhoneFormat')
    if (detail.includes('password must be at least')) return t('auth.errorPasswordLength')
    if (detail.includes('sms code format')) return t('auth.errorSmsCodeFormat')
    if (detail.includes('password mismatch')) return t('auth.errorPasswordConfirm')
    if (detail.includes('email already exists')) return t('auth.errorEmailExists')
    if (detail.includes('email or password is incorrect')) return t('auth.errorCredential')
    if (detail.includes('sms code is incorrect')) return t('auth.errorSmsIncorrect')
    if (detail.includes('sms code has expired')) return t('auth.errorSmsExpired')
    if (detail.includes('sms code attempts exceeded')) return t('auth.errorSmsAttemptsExceeded')
    if (detail.includes('sms send too frequently')) return t('auth.errorSmsTooFrequent')
    if (detail.includes('sms send daily limit reached')) return t('auth.errorSmsDailyLimit')
    if (detail.includes('sms send rate limited')) return t('auth.errorSmsTooFrequent')
    if (detail.includes('client_id has been bound')) return t('auth.errorClientBound')
    if (detail.includes('github oauth is not configured')) return t('auth.githubUnavailable')
    if (detail.includes('invalid_state')) return t('auth.githubStateInvalid')
    if (detail.includes('access_denied')) return t('auth.githubAccessDenied')
    if (detail.includes('missing_code')) return t('auth.githubCallbackFailed')
    if (detail.includes('missing_client_id')) return t('auth.githubCallbackFailed')
    if (detail.includes('github_login_failed')) return t('auth.githubCallbackFailed')
    return t('auth.errorGeneral')
  }

  const triggerAuthSubmitShake = () => {
    authSubmitButtonShake.value = false
    if (authShakeTimer) {
      clearTimeout(authShakeTimer)
      authShakeTimer = null
    }
    nextTick(() => {
      authSubmitButtonShake.value = true
      authShakeTimer = setTimeout(() => {
        authSubmitButtonShake.value = false
        authShakeTimer = null
      }, 520)
    })
  }

  const applyAuthError = (errorLike) => {
    authError.value = resolveAuthErrorMessage(errorLike)
    triggerAuthSubmitShake()
  }

  const stopAuthSmsCountdown = () => {
    if (authSmsCountdownTimer) {
      clearInterval(authSmsCountdownTimer)
      authSmsCountdownTimer = null
    }
    authSmsCountdown.value = 0
  }

  const startAuthSmsCountdown = (seconds = 60) => {
    const normalizedSeconds = Math.max(1, Math.round(Number(seconds) || 60))
    stopAuthSmsCountdown()
    authSmsCountdown.value = normalizedSeconds
    authSmsCountdownTimer = setInterval(() => {
      authSmsCountdown.value = Math.max(0, authSmsCountdown.value - 1)
      if (authSmsCountdown.value <= 0) {
        stopAuthSmsCountdown()
      }
    }, 1000)
  }

  const normalizeAuthPhone = (value) => {
    const raw = String(value || '').trim()
    if (!raw) return ''
    const compact = raw.replace(/[\s()\-]/g, '')
    if (compact.startsWith('+')) {
      const digits = compact.slice(1).replace(/\D/g, '')
      return digits ? `+${digits}` : ''
    }
    const digits = compact.replace(/\D/g, '')
    if (digits.length === 11 && digits.startsWith('1')) {
      return `+86${digits}`
    }
    if (digits.length >= 8 && digits.length <= 15) {
      return `+${digits}`
    }
    return ''
  }

  const resetAuthForm = (keepEmail = false, keepPhone = false) => {
    const nextEmail = keepEmail ? String(authForm.value.email || '').trim() : ''
    const nextPhone = keepPhone ? String(authForm.value.phone || '').trim() : ''
    authForm.value = {
      email: nextEmail,
      phone: nextPhone,
      code: '',
      password: '',
      confirmPassword: ''
    }
  }

  const openAuthModal = (mode = 'login') => {
    const targetMode = mode === 'register' ? 'register' : 'login'
    if (!isAuthEntryEnabled.value) {
      showToast(t('auth.entryDisabled'), 'error')
      return
    }
    if (targetMode === 'register' && !isClientRegisterEnabled.value) {
      if (!isClientLoginEnabled.value) {
        showToast(t('auth.entryDisabled'), 'error')
        return
      }
      showToast(t('auth.registerDisabled'), 'error')
      authMode.value = 'login'
    } else if (targetMode === 'login' && !isClientLoginEnabled.value) {
      if (!isClientRegisterEnabled.value) {
        showToast(t('auth.entryDisabled'), 'error')
        return
      }
      showToast(t('auth.loginDisabled'), 'error')
      authMode.value = 'register'
    } else {
      authMode.value = targetMode
    }
    authError.value = ''
    authSubmitButtonShake.value = false
    if (authMode.value === 'login') {
      authForm.value.confirmPassword = ''
      if (authLoginMethod.value === 'sms' && !isClientSmsLoginEnabled.value) {
        authLoginMethod.value = 'password'
      }
    } else {
      authLoginMethod.value = 'password'
    }
    showAuthModal.value = true
  }

  const closeAuthModal = () => {
    showAuthModal.value = false
    authError.value = ''
    authSubmitButtonShake.value = false
    authSubmitting.value = false
    githubAuthSubmitting.value = false
    authSmsSending.value = false
    stopAuthSmsCountdown()
    resetAuthForm(true, true)
  }

  const switchAuthMode = (mode = 'login') => {
    if (authSubmitting.value || githubAuthSubmitting.value) return
    const targetMode = mode === 'register' ? 'register' : 'login'
    if (targetMode === 'register' && !isClientRegisterEnabled.value) {
      showToast(t('auth.registerDisabled'), 'error')
      return
    }
    if (targetMode === 'login' && !isClientLoginEnabled.value) {
      showToast(t('auth.loginDisabled'), 'error')
      return
    }
    authMode.value = targetMode
    authError.value = ''
    authSubmitButtonShake.value = false
    if (authMode.value === 'login') {
      authForm.value.confirmPassword = ''
      if (authLoginMethod.value === 'sms' && !isClientSmsLoginEnabled.value) {
        authLoginMethod.value = 'password'
      }
    } else {
      authLoginMethod.value = 'password'
      authSmsSending.value = false
      stopAuthSmsCountdown()
    }
  }

  const switchAuthLoginMethod = (method = 'password') => {
    if (authSubmitting.value || githubAuthSubmitting.value || authSmsSending.value) return
    if (method === 'sms') {
      if (!isClientSmsLoginEnabled.value) {
        applyAuthError('sms login is disabled by admin')
        return
      }
      authLoginMethod.value = 'sms'
      authForm.value.email = ''
      authForm.value.password = ''
      authForm.value.confirmPassword = ''
      authError.value = ''
      authSubmitButtonShake.value = false
      return
    }
    authLoginMethod.value = 'password'
    authForm.value.phone = ''
    authForm.value.code = ''
    authError.value = ''
    authSubmitButtonShake.value = false
    authSmsSending.value = false
    stopAuthSmsCountdown()
  }

  const validateAuthForm = () => {
    if (authMode.value === 'login' && !isClientLoginEnabled.value) {
      applyAuthError('login is disabled by admin')
      return null
    }
    if (authMode.value === 'register' && !isClientRegisterEnabled.value) {
      applyAuthError('register is disabled by admin')
      return null
    }
    if (authMode.value === 'login' && authLoginMethod.value === 'sms') {
      if (!isClientSmsLoginEnabled.value) {
        applyAuthError('sms login is disabled by admin')
        return null
      }
      const phone = normalizeAuthPhone(authForm.value.phone)
      const code = String(authForm.value.code || '').trim()
      if (!phone) {
        applyAuthError('phone format is invalid')
        return null
      }
      if (!authSmsCodePattern.test(code)) {
        applyAuthError('sms code format is invalid')
        return null
      }
      return { loginType: 'sms', phone, code }
    }

    const email = String(authForm.value.email || '').trim().toLowerCase()
    const password = String(authForm.value.password || '')
    const confirmPassword = String(authForm.value.confirmPassword || '')
    if (!authEmailPattern.test(email)) {
      applyAuthError('email format is invalid')
      return null
    }
    if (password.length < 6) {
      applyAuthError('password must be at least 6 characters')
      return null
    }
    if (authMode.value === 'register' && password !== confirmPassword) {
      applyAuthError('password mismatch')
      return null
    }
    return { loginType: 'password', email, password }
  }

  const syncAuthUser = async ({ silent = false } = {}) => {
    const token = api.getAuthToken()
    if (!token) {
      authUser.value = null
      return false
    }
    try {
      const result = await api.getAuthMe(api.getClientId())
      if (result?.authenticated && result?.user) {
        authUser.value = result.user
        return true
      }
      authUser.value = null
      api.clearAuthToken()
      return false
    } catch (error) {
      if (error?.response?.status === 401) {
        authUser.value = null
        api.clearAuthToken()
        return false
      }
      if (!silent) {
        showToast(t('auth.errorGeneral'), 'error')
      }
      return false
    }
  }

  const sendAuthSmsCode = async () => {
    if (authMode.value !== 'login' || authLoginMethod.value !== 'sms') return
    if (!isClientSmsLoginEnabled.value) {
      applyAuthError('sms login is disabled by admin')
      return
    }
    if (authSmsSending.value || authSmsCountdown.value > 0) return
    const phone = normalizeAuthPhone(authForm.value.phone)
    if (!phone) {
      applyAuthError('phone format is invalid')
      return
    }
    authForm.value.phone = phone
    authSmsSending.value = true
    authError.value = ''
    try {
      const result = await api.sendSmsLoginCode({
        phone,
        clientId: api.getClientId()
      })
      const resendAfter = Math.max(1, Number(result?.resend_after || 60))
      startAuthSmsCountdown(resendAfter)
      showToast(t('auth.sendSmsCodeSuccess'), 'success')
    } catch (error) {
      applyAuthError(error)
    } finally {
      authSmsSending.value = false
    }
  }

  const submitAuthForm = async () => {
    if (authSubmitting.value || githubAuthSubmitting.value) return
    const normalized = validateAuthForm()
    if (!normalized) return
    authSubmitting.value = true
    authError.value = ''
    try {
      const clientId = api.getClientId()
      const result = authMode.value === 'register'
        ? await api.registerAccount({
          email: normalized.email,
          password: normalized.password,
          clientId
        })
        : (normalized.loginType === 'sms'
          ? await api.loginBySmsCode({
            phone: normalized.phone,
            code: normalized.code,
            clientId
          })
          : await api.loginAccount({
            email: normalized.email,
            password: normalized.password,
            clientId
          }))
      authUser.value = result?.user || null
      closeAuthModal()
      showToast(
        authMode.value === 'register'
          ? t('auth.registerSuccess')
          : (normalized.loginType === 'sms' ? t('auth.smsLoginSuccess') : t('auth.loginSuccess')),
        'success'
      )
      await refreshTasks()
    } catch (error) {
      applyAuthError(error)
    } finally {
      authSubmitting.value = false
    }
  }

  const consumeGithubCallbackHash = () => {
    if (typeof window === 'undefined') return { handled: false, success: false, error: '' }
    const rawHash = String(window.location.hash || '').replace(/^#/, '').trim()
    if (!rawHash) return { handled: false, success: false, error: '' }
    const hashParams = new URLSearchParams(rawHash)
    const provider = String(hashParams.get('auth_provider') || '').trim().toLowerCase()
    const callbackToken = String(hashParams.get('auth_token') || '').trim()
    const callbackError = String(hashParams.get('auth_error') || '').trim()
    if (provider !== 'github' && !callbackToken && !callbackError) {
      return { handled: false, success: false, error: '' }
    }
    if (typeof window.history?.replaceState === 'function') {
      const cleanUrl = `${window.location.pathname}${window.location.search}`
      window.history.replaceState(null, '', cleanUrl)
    }
    if (callbackToken) {
      api.setAuthToken(callbackToken)
      return { handled: true, success: true, error: '' }
    }
    return { handled: true, success: false, error: callbackError }
  }

  const startGithubAuth = async () => {
    if (authSubmitting.value || githubAuthSubmitting.value || authSmsSending.value) return
    if (!isClientLoginEnabled.value) {
      applyAuthError('login is disabled by admin')
      return
    }
    githubAuthSubmitting.value = true
    authError.value = ''
    try {
      const returnUrl = typeof window === 'undefined'
        ? ''
        : `${window.location.origin}${window.location.pathname}${window.location.search}`
      const result = await api.getGithubAuthAuthorize({
        clientId: api.getClientId(),
        returnUrl
      })
      const authorizeUrl = String(result?.authorize_url || '').trim()
      if (!authorizeUrl) {
        throw new Error('github authorize url is empty')
      }
      window.location.href = authorizeUrl
    } catch (error) {
      applyAuthError(error)
    } finally {
      githubAuthSubmitting.value = false
    }
  }

  const logoutCurrentUser = async () => {
    try {
      await api.logoutAccount()
    } catch {
      // ignore
    } finally {
      authUser.value = null
      closeAuthModal()
      showToast(t('auth.logoutSuccess'), 'success')
      await refreshTasks()
    }
  }






  const webUrlError = computed(() => {
    if (!webUrl.value) return ''
    return isValidWebUrl(webUrl.value) ? '' : t('web.validUrlError')
  })

  const packageNameError = computed(() => {
    if (!config.value.package_name) return ''
    return isValidPackageName(config.value.package_name) ? '' : t('config.packageNameRule')
  })

  const desktopPortError = computed(() => {
    if (mode.value !== 'desktop') return ''
    if (config.value.desktop_runtime === 'tauri') return ''
    const port = Number(config.value.desktop_port)
    if (!Number.isInteger(port)) return t('config.desktopPortRule')
    if (port < desktopPortMin || port > desktopPortMax) return t('config.desktopPortRule')
    return ''
  })

  const assignRandomDesktopPort = () => {
    config.value.desktop_port = generateDesktopPort()
  }

  const keystorePasswordError = computed(() => {
    const value = String(config.value.keystore_password || '')
    if (!value) return ''
    return value.length >= 6 ? '' : t('config.keystorePasswordRule')
  })

  const keyPasswordError = computed(() => {
    const value = String(config.value.key_password || '')
    if (!value) return ''
    return value.length >= 6 ? '' : t('config.keyPasswordRule')
  })

  const isKeystoreUploaded = computed(() => Boolean(uploadedKeystore.value))
  const latestSamePackageTask = computed(() => {
    const packageName = String(config.value.package_name || '').trim()
    if (!packageName) return null
    const candidates = tasks.value.filter((task) => {
      if (!task || task.status !== 'success') return false
      if (updatingTaskId.value && task.id === updatingTaskId.value) return false
      return String(task.config?.package_name || '').trim() === packageName
    })
    if (!candidates.length) return null
    return candidates.sort((left, right) => {
      const leftVersion = Number(left.config?.version_code || 0)
      const rightVersion = Number(right.config?.version_code || 0)
      if (rightVersion !== leftVersion) return rightVersion - leftVersion
      return new Date(right.updated_at || 0).getTime() - new Date(left.updated_at || 0).getTime()
    })[0]
  })
  const keystoreUpgradeVersionError = computed(() => {
    if (!isKeystoreUploaded.value || updatingTaskId.value) return ''
    const latestTask = latestSamePackageTask.value
    if (!latestTask) return ''
    const latestVersionCode = Number(latestTask.config?.version_code || 0)
    const currentVersionCode = Number(config.value.version_code || 0)
    if (!Number.isFinite(latestVersionCode) || latestVersionCode < 1) return ''
    if (Number.isFinite(currentVersionCode) && currentVersionCode > latestVersionCode) return ''
    return t('config.keystoreUpgradeVersionRule', {
      current: latestVersionCode,
      next: latestVersionCode + 1
    })
  })
  const keystoreUpgradeVersionHint = computed(() => {
    if (!isKeystoreUploaded.value || updatingTaskId.value || keystoreUpgradeVersionError.value) return ''
    const latestTask = latestSamePackageTask.value
    if (!latestTask) return ''
    const latestVersionCode = Number(latestTask.config?.version_code || 0)
    if (!Number.isFinite(latestVersionCode) || latestVersionCode < 1) return ''
    return t('config.keystoreUpgradeVersionHint', {
      packageName: String(config.value.package_name || '').trim(),
      next: latestVersionCode + 1
    })
  })

  const canCreateTask = computed(() => {
    if (clientFreezeState.value.frozen) {
      return false
    }
    if (mode.value === 'web' && !isWebModeEnabled.value) {
      return false
    }
    if (mode.value === 'desktop' && !isDesktopModeEnabled.value) {
      return false
    }
    const shouldCheckKeystore = !isKeystoreUploaded.value
    const requireTaskCompliance = !updatingTaskId.value
    const complianceReady = requireTaskCompliance
      ? taskComplianceAck.value && !taskComplianceError.value
      : true
    const hasIcon = quickGenerate.value && (mode.value === 'convert' || mode.value === 'web' || mode.value === 'html') && !updatingTaskId.value
      ? true
      : (appIcon.value || uploadedIcon.value)
    const common =
      config.value.app_name &&
      config.value.package_name &&
      !packageNameError.value &&
      !desktopPortError.value &&
      !keystoreUpgradeVersionError.value &&
      (!shouldCheckKeystore || (!keystorePasswordError.value && !keyPasswordError.value)) &&
      complianceReady &&
      hasIcon

    if (mode.value === 'convert' || mode.value === 'desktop') {
      return common && uploadedFile.value
    }
    if (mode.value === 'html') {
      const htmlReady =
        htmlInputMode.value === 'edit'
          ? canUseSavedHtmlForBuild.value
          : Boolean(uploadedHtmlFile.value)
      return common && htmlReady
    }
    const basicWeb = common && webUrl.value && !webUrlError.value
    if (enableAds.value) {
      return basicWeb && adConfig.value.appId && adConfig.value.appKey && adConfig.value.placementId
    }
    return basicWeb
  })

  watch(() => mode.value, (value) => {
    if (value !== 'convert' && value !== 'web' && value !== 'html' && quickGenerate.value) {
      exitQuickGenerate()
    }
  })

  watch([() => mode.value, () => htmlInputMode.value], async ([nextMode, nextInputMode]) => {
    if (nextMode === 'html' && nextInputMode === 'edit') {
      if (!htmlEditorInstance.value) {
        htmlEditorLoading.value = true
        try {
          await nextTick()
          await waitForFrame()
          const targetContainer = showHtmlEditorModal.value ? htmlEditorModalContainer.value : htmlEditorContainer.value
          mountHtmlEditor(targetContainer)
        } finally {
          htmlEditorLoading.value = false
        }
      }
      htmlEditorInstance.value?.requestMeasure()
    }
  })

  const applyHtmlEditorTheme = () => {
    if (!htmlEditorInstance.value) return
    htmlEditorInstance.value.dispatch({
      effects: htmlEditorThemeCompartment.reconfigure(getHtmlEditorTheme())
    })
  }

  watch(currentTheme, () => {
    applyHtmlEditorTheme()
  })

  watch(showHtmlEditorModal, async (isOpen) => {
    if (htmlInputMode.value !== 'edit') return
    htmlEditorLoading.value = true
    try {
      await nextTick()
      await waitForFrame()
      const targetContainer = isOpen ? htmlEditorModalContainer.value : htmlEditorContainer.value
      mountHtmlEditor(targetContainer)
    } finally {
      htmlEditorLoading.value = false
    }
  })

  const resolveWebUrl = async (input) => {
    const raw = String(input || '').trim()
    if (!raw) return ''
    const hasScheme = /^https?:\/\//i.test(raw)
    const candidates = hasScheme ? [raw] : [`https://${raw}`, `http://${raw}`]
    for (const candidate of candidates) {
      try {
        const result = await api.probeUrl(candidate)
        if (result?.ok) return candidate
      } catch (_) {
        // ignore and try next
      }
    }
    return ''
  }

  const getTaskTime = (task) => task.updated_at || task.created_at
  const sortedTasks = computed(() => tasks.value)
  const taskPageSize = 10
  const currentTaskPage = ref(1)
  const totalTaskPages = computed(() => Math.max(1, Math.ceil(sortedTasks.value.length / taskPageSize)))
  const pagedTasks = computed(() => {
    const start = (currentTaskPage.value - 1) * taskPageSize
    return sortedTasks.value.slice(start, start + taskPageSize)
  })
  const taskPageNumbers = computed(() => {
    const total = totalTaskPages.value
    const current = currentTaskPage.value
    if (total <= 7) {
      return Array.from({ length: total }, (_, index) => ({
        key: `page-${index + 1}`,
        type: 'page',
        value: index + 1
      }))
    }

    const items = [
      { key: 'page-1', type: 'page', value: 1 }
    ]
    let start = Math.max(2, current - 1)
    let end = Math.min(total - 1, current + 1)

    if (current <= 3) end = 4
    if (current >= total - 2) start = total - 3

    if (start > 2) {
      items.push({ key: 'ellipsis-left', type: 'ellipsis', value: '...' })
    }

    for (let page = start; page <= end; page += 1) {
      items.push({ key: `page-${page}`, type: 'page', value: page })
    }

    if (end < total - 1) {
      items.push({ key: 'ellipsis-right', type: 'ellipsis', value: '...' })
    }

    items.push({ key: `page-${total}`, type: 'page', value: total })
    return items
  })
  const goToTaskPage = (page) => {
    const clamped = Math.max(1, Math.min(totalTaskPages.value, Number(page || 1)))
    currentTaskPage.value = clamped
  }
  const taskStats = computed(() => {
    const total = tasks.value.length
    let success = 0
    for (const task of tasks.value) {
      if (task.status === 'success') success += 1
    }
    return { total, success }
  })

  const dismissedAnnouncementId = ref(localStorage.getItem('apk_builder_announcement_id'))
  const activeAnnouncement = ref(null)
  const resolveActiveAnnouncement = () => {
    const dismissedId = dismissedAnnouncementId.value
    activeAnnouncement.value = announcements.value.find((item) => String(item.id) !== dismissedId) || null
  }

  // Helpers
  const getStatusText = (status) => {
    const map = { pending: t('status.pending'), processing: t('status.processing'), success: t('status.success'), failed: t('status.failed') }
    return map[status] || status
  }
  const getTaskIcon = (status) => {
    const map = { pending: '⏳', processing: '⚙️', success: '✅', failed: '❌' }
    return map[status] || '📦'
  }
  const getDownloadUrl = (taskId) => api.getDownloadUrl(taskId)
  const getKeystoreUrl = (taskId) => api.getKeystoreUrl(taskId)
  const nativeAdRequesting = ref(false)

  const hasAndroidAdBridge = () => {
    if (typeof window === 'undefined') return false
    return (
      typeof window.sendToApp === 'function' ||
      Boolean(window.AdBridge && typeof window.AdBridge.playAd === 'function')
    )
  }

  const shouldGateDownloadWithNativeAd = () => {
    if (!isMobileShell.value) return false
    return hasAndroidAdBridge()
  }

  const shouldGateBuildStartWithNativeAd = () => isRewardedBuildAdsEnabled.value && hasAndroidAdBridge()

  const parseNativeAdResult = (payload) => {
    if (typeof payload === 'string') {
      try {
        payload = JSON.parse(payload)
      } catch {
        return { code: 10002, message: '广告结果解析失败' }
      }
    }
    if (!payload || typeof payload !== 'object') {
      return { code: 10002, message: '广告结果无效' }
    }
    const code = Number(payload.code)
    const message = typeof payload.message === 'string' ? payload.message : ''
    return {
      code: Number.isFinite(code) ? code : 10002,
      message
    }
  }

  const restoreAdCallback = (key, previous) => {
    if (typeof previous === 'function') {
      window[key] = previous
      return
    }
    try {
      delete window[key]
    } catch {
      window[key] = undefined
    }
  }

  const requestNativeRewardAd = (timeoutMs = 15000) => new Promise((resolve) => {
    if (!hasAndroidAdBridge()) {
      resolve({ code: 10004, message: '当前环境不支持原生广告' })
      return
    }

    let finished = false
    const prevPlayAdBack = window.playAdBack
    const prevNativeAdCallback = window.__nativeAdCallback
    const timer = setTimeout(() => {
      finish({ code: 10005, message: '广告响应超时' })
    }, timeoutMs)

    const cleanup = () => {
      clearTimeout(timer)
      restoreAdCallback('playAdBack', prevPlayAdBack)
      restoreAdCallback('__nativeAdCallback', prevNativeAdCallback)
    }

    const finish = (payload) => {
      if (finished) return
      finished = true
      cleanup()
      resolve(parseNativeAdResult(payload))
    }

    const handleAdCallback = (payload) => {
      const result = parseNativeAdResult(payload)
      // 10000 仅表示开始播放，不是最终结果
      if (result.code === 10000) return
      finish(result)
    }

    window.playAdBack = handleAdCallback
    window.__nativeAdCallback = handleAdCallback

    try {
      if (typeof window.sendToApp === 'function') {
        window.sendToApp('playAd', '')
        return
      }
      if (window.AdBridge && typeof window.AdBridge.playAd === 'function') {
        window.AdBridge.playAd()
        return
      }
      finish({ code: 10004, message: '当前环境不支持原生广告' })
    } catch (error) {
      finish({ code: 10002, message: error?.message || '广告调用失败' })
    }
  })

  const requestRewardAdBeforeBuild = async () => {
    if (!shouldGateBuildStartWithNativeAd()) return true
    if (nativeAdRequesting.value) {
      showToast(t('toast.rewardAdLoading'), 'error')
      return false
    }

    nativeAdRequesting.value = true
    try {
      const result = await requestNativeRewardAd()
      if (result.code !== 10001) {
        showToast(result.message || t('toast.rewardAdIncomplete'), 'error')
        return false
      }
      return true
    } finally {
      nativeAdRequesting.value = false
    }
  }

  const triggerTaskDownload = (url) => {
    if (!url || typeof document === 'undefined') return
    const link = document.createElement('a')
    link.href = url
    link.rel = 'noopener'
    link.style.display = 'none'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }

  const getDesktopOutputRegistry = () => {
    if (typeof localStorage === 'undefined') return {}
    try {
      const raw = localStorage.getItem(desktopOutputTabRegistryKey)
      const parsed = raw ? JSON.parse(raw) : {}
      return parsed && typeof parsed === 'object' ? parsed : {}
    } catch (error) {
      return {}
    }
  }

  const saveDesktopOutputRegistry = (registry) => {
    if (typeof localStorage === 'undefined') return
    try {
      localStorage.setItem(desktopOutputTabRegistryKey, JSON.stringify(registry || {}))
    } catch (error) {
      // 忽略本地存储异常
    }
  }

  const pruneDesktopOutputRegistry = (registry) => {
    const now = Date.now()
    const nextRegistry = {}
    Object.entries(registry || {}).forEach(([tabId, timestamp]) => {
      const numericTimestamp = Number(timestamp)
      if (Number.isFinite(numericTimestamp) && now - numericTimestamp <= desktopOutputHeartbeatTtlMs) {
        nextRegistry[tabId] = numericTimestamp
      }
    })
    return nextRegistry
  }

  const touchDesktopOutputTab = () => {
    const registry = pruneDesktopOutputRegistry(getDesktopOutputRegistry())
    registry[desktopOutputTabId] = Date.now()
    saveDesktopOutputRegistry(registry)
  }

  const removeDesktopOutputTab = () => {
    const registry = pruneDesktopOutputRegistry(getDesktopOutputRegistry())
    delete registry[desktopOutputTabId]
    saveDesktopOutputRegistry(registry)
    return registry
  }

  const startDesktopOutputHeartbeat = () => {
    desktopOutputExitHandled = false
    touchDesktopOutputTab()
    if (desktopOutputHeartbeatInterval) {
      clearInterval(desktopOutputHeartbeatInterval)
    }
    desktopOutputHeartbeatInterval = setInterval(() => {
      touchDesktopOutputTab()
    }, desktopOutputHeartbeatIntervalMs)
  }

  const stopDesktopOutputHeartbeat = () => {
    if (desktopOutputHeartbeatInterval) {
      clearInterval(desktopOutputHeartbeatInterval)
      desktopOutputHeartbeatInterval = null
    }
    removeDesktopOutputTab()
  }

  const releaseDesktopOutputsOnPageExit = () => {
    if (desktopOutputExitHandled) return
    desktopOutputExitHandled = true
    const registry = removeDesktopOutputTab()
    if (Object.keys(registry).length > 0) return
    api.sendReleaseDesktopOutputsBeacon()
  }

  const scheduleDesktopTaskRefresh = () => {
    if (desktopOutputRefreshTimer) {
      clearTimeout(desktopOutputRefreshTimer)
    }
    desktopOutputRefreshTimer = setTimeout(async () => {
      desktopOutputRefreshTimer = null
      await refreshTasks()
    }, 1500)
  }
  const downloadTaskArtifact = async (taskId, artifactType = 'apk') => {
    const task = tasks.value.find((item) => item.id === taskId)
    const isDesktopArtifact = artifactType !== 'signed' && String(task?.mode || '') === 'desktop'
    const url = artifactType === 'signed' ? getKeystoreUrl(taskId) : getDownloadUrl(taskId)
    closeDownloadMenu()
    if (!url) return
    if (isDesktopArtifact && task?.desktop_output_expires_at) {
      const expiresAt = new Date(task.desktop_output_expires_at).getTime()
      if (Number.isFinite(expiresAt) && expiresAt <= Date.now()) {
        showToast('EXE 下载已过期（生成成功后仅保留 30 分钟）', 'error')
        scheduleDesktopTaskRefresh()
        return
      }
    }

    const triggerDownload = () => {
      triggerTaskDownload(url)
      if (isDesktopArtifact) {
        scheduleDesktopTaskRefresh()
      }
    }

    if (!shouldGateDownloadWithNativeAd()) {
      triggerDownload()
      return
    }

    if (nativeAdRequesting.value) {
      showToast('广告加载中，请稍候', 'error')
      return
    }

    nativeAdRequesting.value = true
    try {
      const result = await requestNativeRewardAd()
      if (result.code !== 10001) {
        showToast(result.message || '广告未完成，暂不可下载', 'error')
        return
      }
      triggerDownload()
    } finally {
      nativeAdRequesting.value = false
    }
  }
  const isQueuedTask = (task) => {
    if (task?.status === 'pending') return true
    if (task?.status !== 'processing') return false
    return String(task?.message || '').includes('排队')
  }
  const isCancelableTask = (task) => task?.status === 'pending' || task?.status === 'processing'

  const resetCdnLocalizationState = (enabled = false) => {
    cdnLinkItems.value = []
    cdnSelectedUrls.value = []
    cdnLocalizeEnabled.value = Boolean(enabled)
    cdnScanLoading.value = false
    showCdnLocalizeModal.value = false
  }

  const normalizeCdnLinkItems = (items) => {
    const source = Array.isArray(items) ? items : []
    const dedupMap = new Map()
    for (const raw of source) {
      const url = String(raw?.url || '').trim()
      if (!url || dedupMap.has(url)) continue
      dedupMap.set(url, {
        url,
        type: String(raw?.type || 'other'),
        occurrences: Number(raw?.occurrences || 0),
        file_count: Number(raw?.file_count || 0),
        files: Array.isArray(raw?.files) ? raw.files.map((file) => String(file || '')).filter(Boolean).slice(0, 8) : []
      })
    }
    return Array.from(dedupMap.values())
  }

  const selectAllCdnLinks = () => {
    cdnSelectedUrls.value = cdnLinkItems.value.map((item) => item.url)
    cdnLocalizeEnabled.value = cdnSelectedUrls.value.length > 0
  }

  const clearCdnLinkSelection = () => {
    cdnSelectedUrls.value = []
    cdnLocalizeEnabled.value = false
  }

  const isCdnLinkSelected = (url) => cdnSelectedUrls.value.includes(url)

  const getCdnTypeLabel = (rawType) => {
    const normalizedType = String(rawType || 'other').trim().toLowerCase() || 'other'
    const key = `cdnLocalize.type.${normalizedType}`
    const translated = t(key)
    return translated === key ? normalizedType : translated
  }

  const toggleCdnLinkSelection = (url, checked) => {
    const targetUrl = String(url || '').trim()
    if (!targetUrl) return
    const selectedSet = new Set(cdnSelectedUrls.value)
    if (checked) selectedSet.add(targetUrl)
    else selectedSet.delete(targetUrl)
    cdnSelectedUrls.value = Array.from(selectedSet)
    if (cdnSelectedUrls.value.length <= 0) {
      cdnLocalizeEnabled.value = false
    } else if (!cdnLocalizeEnabled.value) {
      cdnLocalizeEnabled.value = true
    }
  }

  const handleCdnLocalizeEnabledChange = () => {
    if (!cdnLocalizeEnabled.value) return
    if (hasCdnExternalLinks.value && cdnSelectedUrls.value.length <= 0) {
      selectAllCdnLinks()
    }
  }

  const openCdnLocalizeModal = () => {
    if (!hasCdnExternalLinks.value) return
    showCdnLocalizeModal.value = true
  }

  const closeCdnLocalizeModal = () => {
    showCdnLocalizeModal.value = false
  }

  const scanUploadedExternalLinks = async (payload, options = {}) => {
    const scanPayload = payload && typeof payload === 'object' ? payload : {}
    const shouldOpenModal = options.openModal !== false
    const rawMode = String(scanPayload.mode || '').trim().toLowerCase()
    if (rawMode !== 'convert' && rawMode !== 'html') return null
    cdnScanLoading.value = true
    try {
      const result = await api.scanExternalLinks(scanPayload)
      const items = normalizeCdnLinkItems(result?.items)
      cdnLinkItems.value = items
      if (items.length > 0) {
        cdnSelectedUrls.value = items.map((item) => item.url)
        cdnLocalizeEnabled.value = true
        if (shouldOpenModal) showCdnLocalizeModal.value = true
      } else {
        cdnSelectedUrls.value = []
        cdnLocalizeEnabled.value = false
        showCdnLocalizeModal.value = false
      }
      return { ...result, items }
    } catch (_) {
      cdnLinkItems.value = []
      cdnSelectedUrls.value = []
      cdnLocalizeEnabled.value = true
      showCdnLocalizeModal.value = false
      showToast(t('cdnLocalize.scanFailed'), 'error')
      return null
    } finally {
      cdnScanLoading.value = false
    }
  }

  const rescanExternalLinks = async (options = {}) => {
    if (mode.value === 'convert' && uploadedFile.value?.filename) {
      if (uploadedFile.value?.reused) {
        showToast(t('cdnLocalize.rescanReuseConvert'), 'error')
        return null
      }
      return await scanUploadedExternalLinks({ mode: 'convert', filename: uploadedFile.value.filename }, options)
    }
    if (mode.value === 'html' && uploadedHtmlFile.value?.filename) {
      if (uploadedHtmlFile.value?.reused) {
        showToast(t('cdnLocalize.rescanReuseHtml'), 'error')
        return null
      }
      return await scanUploadedExternalLinks({ mode: 'html', html_filename: uploadedHtmlFile.value.filename }, options)
    }
    return null
  }

  // Upload
  const triggerFileInput = () => fileInput.value?.click?.()
  const handleFileSelect = async (event) => {
    const file = event.target.files[0]
    if (file) await uploadFile(file)
  }
  const handleDrop = async (event) => {
    isDragging.value = false
    const file = event.dataTransfer.files[0]
    if (file && file.name.endsWith('.zip')) await uploadFile(file)
    else showToast('请上传 ZIP 文件', 'error')
  }
  const uploadFile = async (file) => {
    try {
      resetCdnLocalizationState(false)
      uploadProgress.value = 0
      const result = await api.uploadFile(file, (progress) => (uploadProgress.value = progress))
      uploadedFile.value = result
      currentStep.value = 2
      if (mode.value === 'convert') {
        await scanUploadedExternalLinks({ mode: 'convert', filename: result.filename }, { openModal: true })
      }
      showToast(t('toast.uploadSuccess'), 'success')
    } catch (error) {
      showErrorToast('toast.uploadFailed', error)
    }
  }

  const handleHtmlSelect = async (event) => {
    const file = event.target.files[0]
    if (!file) return
    const previewContent = await syncHtmlEditorContent(file)
    await uploadHtml(file, { previewContent })
    htmlEditorDirty.value = false
  }
  const handleHtmlDrop = async (event) => {
    isHtmlDragging.value = false
    const file = event.dataTransfer.files[0]
    if (file && /\.(html|htm)$/i.test(file.name)) {
      const previewContent = await syncHtmlEditorContent(file)
      await uploadHtml(file, { previewContent })
      htmlEditorDirty.value = false
    } else {
      showToast(t('html.htmlRequired'), 'error')
    }
  }

  const openHtmlPreview = (content) => {
    const normalizedContent = String(content || '')
    if (!normalizedContent.trim()) {
      showToast(t('html.previewUnavailable'), 'error')
      return
    }
    htmlPreviewContent.value = normalizedContent
    showHtmlPreviewModal.value = true
  }

  const closeHtmlPreviewModal = () => {
    showHtmlPreviewModal.value = false
  }

  const resolvePreviewContent = () => {
    if (htmlInputMode.value === 'file') {
      if (!uploadedHtmlFile.value) return ''
      return htmlEditorContent.value || htmlSavedContent.value || ''
    }
    if (hasSavedHtmlContent.value && !htmlEditorDirty.value) {
      return htmlSavedContent.value
    }
    return htmlEditorContent.value || htmlSavedContent.value || ''
  }

  const previewCurrentHtml = () => {
    const content = resolvePreviewContent()
    if (!content.trim()) {
      if (htmlInputMode.value === 'file') {
        showToast(t('html.htmlRequired'), 'error')
      } else {
        showToast(t('html.previewUnavailable'), 'error')
      }
      return
    }
    openHtmlPreview(content)
  }

  const uploadHtml = async (file, options = {}) => {
    const shouldOpenPreview = options.openPreview !== false
    const shouldOpenCdnModal = options.openCdnModal !== false
    const previewContent = typeof options.previewContent === 'string' ? options.previewContent : ''
    const savedFromEditor = options.savedFromEditor === true
    const silentSuccess = options.silentSuccess === true
    try {
      resetCdnLocalizationState(false)
      htmlUploadProgress.value = 0
      const result = await api.uploadHtml(file, (progress) => (htmlUploadProgress.value = progress))
      uploadedHtmlFile.value = result
      if (savedFromEditor) {
        htmlSavedUploadContent.value = previewContent || htmlSavedContent.value || ''
      } else {
        htmlSavedUploadContent.value = ''
      }
      currentStep.value = 2
      const scanResult = await scanUploadedExternalLinks(
        { mode: 'html', html_filename: result.filename },
        { openModal: shouldOpenCdnModal }
      )
      if (!silentSuccess) {
        showToast(t('toast.uploadSuccess'), 'success')
      }
      if (shouldOpenPreview) {
        const shouldSkipPreview = shouldOpenCdnModal && (scanResult?.items?.length || 0) > 0
        if (!shouldSkipPreview) {
          const content = previewContent || htmlEditorContent.value || htmlSavedContent.value || ''
          openHtmlPreview(content)
        }
      }
      return result
    } catch (error) {
      if (savedFromEditor) {
        htmlSavedUploadContent.value = ''
      }
      showErrorToast('toast.uploadFailed', error)
      return null
    }
  }

  const waitForFrame = () =>
    new Promise((resolve) => {
      if (typeof requestAnimationFrame === 'function') {
        requestAnimationFrame(() => resolve())
      } else {
        setTimeout(resolve, 0)
      }
    })

  const htmlEditorLightTheme = EditorView.theme(
    {
      '&': { backgroundColor: 'transparent', color: 'var(--text-main)' },
      '.cm-content': {
        fontFamily: 'JetBrains Mono, Fira Code, Menlo, Monaco, Consolas, "Courier New", monospace',
        fontSize: '13px',
        lineHeight: '1.6'
      },
      '.cm-gutters': { backgroundColor: 'transparent', border: 'none', color: 'var(--text-sub)' },
      '.cm-activeLine': { backgroundColor: 'rgba(59, 130, 246, 0.08)' },
      '.cm-activeLineGutter': { backgroundColor: 'rgba(59, 130, 246, 0.12)' }
    },
    { dark: false }
  )

  const htmlEditorDarkTheme = EditorView.theme(
    {
      '&': { backgroundColor: 'transparent', color: '#e2e8f0' },
      '.cm-gutters': { backgroundColor: 'transparent', border: 'none', color: '#94a3b8' }
    },
    { dark: true }
  )

  const getHtmlEditorTheme = () => (currentTheme.value === 'dark' ? htmlEditorDarkTheme : htmlEditorLightTheme)

  const createHtmlEditorState = (content) => {
    const updateListener = EditorView.updateListener.of((update) => {
      if (update.docChanged && !isHtmlProgrammaticUpdate) {
        htmlEditorContent.value = update.state.doc.toString()
        htmlEditorDirty.value = true
        scheduleHtmlDiagnostics(update.view)
      }
    })

    return EditorState.create({
      doc: content,
      extensions: [
        htmlEditorThemeCompartment.of(getHtmlEditorTheme()),
        lineNumbers(),
        highlightActiveLineGutter(),
        highlightSpecialChars(),
        history(),
        foldGutter(),
        drawSelection(),
        dropCursor(),
        rectangularSelection(),
        EditorState.allowMultipleSelections.of(true),
        indentOnInput(),
        bracketMatching(),
        closeBrackets(),
        autocompletion(),
        highlightActiveLine(),
        highlightSelectionMatches(),
        syntaxHighlighting(defaultHighlightStyle, { fallback: true }),
        html({ autoCloseTags: true, matchClosingTags: true }),
        lintGutter(),
        keymap.of([
          ...defaultKeymap,
          ...historyKeymap,
          ...foldKeymap,
          ...completionKeymap,
          ...closeBracketsKeymap,
          ...searchKeymap,
          indentWithTab
        ]),
        updateListener,
        EditorView.lineWrapping
      ]
    })
  }

  const computeHtmlDiagnostics = (state) => {
    const diagnostics = []
    const seen = new Set()
    const syntaxDiagnostics = []
    const pushDiagnostic = (diagnostic) => {
      const key = `${diagnostic.from}-${diagnostic.to}-${diagnostic.message}`
      if (seen.has(key)) return
      seen.add(key)
      diagnostics.push(diagnostic)
    }
    const tree = ensureSyntaxTree(state, state.doc.length, 200)
    if (tree) {
      tree.iterate({
        enter: (node) => {
          if (!node.type.isError) return
          const from = node.from
          const to = Math.max(node.to, from + 1)
          if (syntaxDiagnostics.length === 0) {
            syntaxDiagnostics.push({
              from,
              to,
              severity: 'error',
              message: t('html.syntaxError')
            })
          }
        }
      })
    }

    const text = state.doc.toString()
    const commentRanges = []
    let commentStart = text.indexOf('<!--')
    while (commentStart !== -1) {
      const commentEnd = text.indexOf('-->', commentStart + 4)
      if (commentEnd === -1) {
        commentRanges.push([commentStart, text.length])
        break
      }
      commentRanges.push([commentStart, commentEnd + 3])
      commentStart = text.indexOf('<!--', commentEnd + 3)
    }

    const voidTags = new Set([
      'area',
      'base',
      'br',
      'col',
      'embed',
      'hr',
      'img',
      'input',
      'link',
      'meta',
      'param',
      'source',
      'track',
      'wbr'
    ])

    const tagRegex = /<\/?([a-zA-Z][\w:-]*)(\s[^<>]*?)?>/g
    const stack = []
    let commentIndex = 0
    let match
    while ((match = tagRegex.exec(text)) !== null) {
      const fullTag = match[0]
      const tagName = match[1]?.toLowerCase() || ''
      const start = match.index
      const end = start + fullTag.length
      while (commentIndex < commentRanges.length && start >= commentRanges[commentIndex][1]) {
        commentIndex += 1
      }
      if (commentIndex < commentRanges.length) {
        const [cStart, cEnd] = commentRanges[commentIndex]
        if (start >= cStart && start < cEnd) continue
      }

      const isClosing = fullTag.startsWith('</')
      const isSelfClosing = /\/\s*>$/.test(fullTag) || voidTags.has(tagName)
      if (!tagName) continue

      if (!isClosing) {
        if (!isSelfClosing) {
          stack.push({ name: tagName, from: start, to: end })
        }
        continue
      }

      if (stack.length === 0) {
        pushDiagnostic({
          from: start,
          to: end,
          severity: 'error',
          message: t('html.tagUnexpectedClose', { name: tagName })
        })
        continue
      }

      const last = stack[stack.length - 1]
      if (last.name === tagName) {
        stack.pop()
        continue
      }

      const matchIndex = stack.map((item) => item.name).lastIndexOf(tagName)
      if (matchIndex !== -1) {
        for (let i = stack.length - 1; i > matchIndex; i -= 1) {
          const item = stack[i]
          pushDiagnostic({
            from: item.from,
            to: item.to,
            severity: 'error',
            message: t('html.tagMissingClose', { name: item.name })
          })
        }
        stack.splice(matchIndex + 1)
        stack.pop()
        continue
      }

      pushDiagnostic({
        from: start,
        to: end,
        severity: 'error',
        message: t('html.tagUnexpectedClose', { name: tagName })
      })
    }

    if (stack.length) {
      stack.reverse().forEach((item) => {
        pushDiagnostic({
          from: item.from,
          to: item.to,
          severity: 'error',
          message: t('html.tagMissingClose', { name: item.name })
        })
      })
    }

    if (!diagnostics.length && syntaxDiagnostics.length) {
      pushDiagnostic(syntaxDiagnostics[0])
    }

    return diagnostics
  }

  const computeHtmlDiagnosticsForContent = (content) => {
    const tempState = EditorState.create({
      doc: content,
      extensions: [html()]
    })
    return computeHtmlDiagnostics(tempState)
  }

  const refreshHtmlMarkers = (state, diagnostics) => {
    htmlEditorMarkers.value = diagnostics
      .map((diagnostic) => {
        const line = state.doc.lineAt(diagnostic.from)
        return {
          from: diagnostic.from,
          to: diagnostic.to,
          severity: diagnostic.severity,
          message: diagnostic.message,
          startLineNumber: line.number,
          startColumn: diagnostic.from - line.from + 1
        }
      })
      .sort((a, b) => {
        if (a.startLineNumber !== b.startLineNumber) return a.startLineNumber - b.startLineNumber
        return a.startColumn - b.startColumn
      })
  }

  const applyHtmlDiagnostics = (view) => {
    if (!view || !htmlEditorInstance.value || htmlEditorInstance.value !== view) return
    const diagnostics = computeHtmlDiagnostics(view.state)
    view.dispatch(setDiagnostics(view.state, diagnostics))
    refreshHtmlMarkers(view.state, diagnostics)
  }

  const scheduleHtmlDiagnostics = (view) => {
    if (!view) return
    if (htmlDiagnosticsHandle) {
      if (typeof cancelAnimationFrame === 'function') {
        cancelAnimationFrame(htmlDiagnosticsHandle)
      } else {
        clearTimeout(htmlDiagnosticsHandle)
      }
    }
    if (typeof requestAnimationFrame === 'function') {
      htmlDiagnosticsHandle = requestAnimationFrame(() => {
        htmlDiagnosticsHandle = null
        applyHtmlDiagnostics(view)
      })
    } else {
      htmlDiagnosticsHandle = setTimeout(() => {
        htmlDiagnosticsHandle = null
        applyHtmlDiagnostics(view)
      }, 0)
    }
  }

  const setHtmlEditorContent = (content, markDirty = false) => {
    isHtmlProgrammaticUpdate = true
    htmlEditorContent.value = content
    if (htmlEditorInstance.value) {
      const view = htmlEditorInstance.value
      view.dispatch({
        changes: { from: 0, to: view.state.doc.length, insert: content }
      })
      scheduleHtmlDiagnostics(view)
    }
    htmlEditorDirty.value = markDirty
    isHtmlProgrammaticUpdate = false
  }

  const destroyHtmlEditor = () => {
    if (htmlEditorInstance.value) {
      htmlEditorInstance.value.destroy()
      htmlEditorInstance.value = null
    }
    htmlEditorReady.value = false
  }

  const mountHtmlEditor = (container) => {
    if (!container) return
    if (htmlEditorInstance.value) {
      const currentParent = htmlEditorInstance.value.dom?.parentElement
      if (currentParent === container) {
        htmlEditorInstance.value.requestMeasure()
        return
      }
      destroyHtmlEditor()
    }
    const content = htmlEditorContent.value || defaultHtmlTemplate
    if (!htmlEditorContent.value) {
      htmlEditorContent.value = content
    }
    const state = createHtmlEditorState(content)
    htmlEditorInstance.value = new EditorView({
      state,
      parent: container
    })
    htmlEditorReady.value = true
    scheduleHtmlDiagnostics(htmlEditorInstance.value)
  }

  const setHtmlInputMode = async (value) => {
    htmlInputMode.value = value
    if (value === 'edit') {
      htmlEditorLoading.value = true
      try {
      await nextTick()
      await waitForFrame()
      const targetContainer = showHtmlEditorModal.value ? htmlEditorModalContainer.value : htmlEditorContainer.value
      mountHtmlEditor(targetContainer)
      } finally {
        htmlEditorLoading.value = false
      }
    } else {
      htmlEditorLoading.value = false
    }
  }

  const syncHtmlEditorContent = async (file) => {
    try {
      const content = await file.text()
      setHtmlEditorContent(content, false)
      return content
    } catch {
      return ''
    }
  }

  const openHtmlEditorModal = async () => {
    showHtmlEditorModal.value = true
    htmlEditorLoading.value = true
    try {
      await nextTick()
      await waitForFrame()
      mountHtmlEditor(htmlEditorModalContainer.value)
    } finally {
      htmlEditorLoading.value = false
    }
  }

  const closeHtmlEditorModal = async () => {
    showHtmlEditorModal.value = false
    htmlEditorLoading.value = true
    try {
      await nextTick()
      await waitForFrame()
      if (htmlInputMode.value === 'edit') {
        mountHtmlEditor(htmlEditorContainer.value)
      } else {
        destroyHtmlEditor()
      }
    } finally {
      htmlEditorLoading.value = false
    }
  }

  const saveEditorHtml = async () => {
    if (htmlEditorContentEmpty.value) {
      showToast(t('html.editorEmpty'), 'error')
      return
    }
    let diagnostics = []
    if (htmlEditorInstance.value) {
      const view = htmlEditorInstance.value
      diagnostics = computeHtmlDiagnostics(view.state)
      refreshHtmlMarkers(view.state, diagnostics)
      view.dispatch(setDiagnostics(view.state, diagnostics))
    } else {
      const tempState = EditorState.create({
        doc: htmlEditorContent.value,
        extensions: [html()]
      })
      diagnostics = computeHtmlDiagnostics(tempState)
      refreshHtmlMarkers(tempState, diagnostics)
    }
    if (diagnostics.length) {
      showToast(t('html.fixErrors', { count: diagnostics.length }), 'error')
      return
    }
    htmlSavedContent.value = htmlEditorContent.value
    htmlEditorDirty.value = false
    const file = new File([htmlSavedContent.value], 'index.html', { type: 'text/html' })
    const uploadResult = await uploadHtml(file, {
      openPreview: false,
      openCdnModal: true,
      previewContent: htmlSavedContent.value,
      savedFromEditor: true,
      silentSuccess: true
    })
    if (!uploadResult) return
    if (currentStep.value < 2) currentStep.value = 2
    showToast(t('html.editorSaved'), 'success')
  }

  const revealHtmlMarker = (marker) => {
    if (!htmlEditorInstance.value) return
    const view = htmlEditorInstance.value
    view.dispatch({
      selection: { anchor: marker.from },
      scrollIntoView: true
    })
    view.focus()
  }

  const isHtmlErrorMarker = (marker) => marker.severity === 'error'
  const htmlMarkerLabel = (marker) => (isHtmlErrorMarker(marker) ? t('html.issueError') : t('html.issueWarning'))

  const triggerKeystoreInput = () => {
    if (isKeystoreUploaded.value || updatingTaskId.value) return
    keystoreInput.value?.click?.()
  }

  const handleKeystoreSelect = async (event) => {
    if (updatingTaskId.value) {
      showToast(t('config.keystoreUploadNotAllowed'), 'error')
      return
    }
    const file = event.target.files[0]
    if (!file) return
    keystoreUploadError.value = ''
    const name = (file.name || '').toLowerCase()
    if (!(name.endsWith('.jks') || name.endsWith('.keystore'))) {
      keystoreUploadError.value = t('config.keystoreUploadInvalid')
      showToast(keystoreUploadError.value, 'error')
      if (keystoreInput.value) keystoreInput.value.value = ''
      return
    }
    try {
      const result = await api.uploadKeystore(file)
      uploadedKeystore.value = result
      useCustomKeystore.value = true
      showToast(t('config.keystoreUploadSuccess'), 'success')
    } catch (error) {
      keystoreUploadError.value = t('config.keystoreUploadFailed')
      // 后端错误细节仅用于 console 调试，UI 显示本地化文案
      try { console.warn('[uploadKeystore]', extractErrorDetailForLog(error)) } catch {}
      showToast(keystoreUploadError.value, 'error')
    }
  }

  const clearKeystoreUpload = () => {
    uploadedKeystore.value = null
    useCustomKeystore.value = false
    keystoreUploadError.value = ''
    if (keystoreInput.value) keystoreInput.value.value = ''
  }

  // Icon cropper flow
  const handleIconSelect = async (event) => {
    const file = event.target.files[0]
    if (!file) return
    iconError.value = ''
    if (file.type !== 'image/png') {
      iconError.value = '请上传 PNG 格式的图片'
      return
    }
    cropperImageSrc.value = URL.createObjectURL(file)
    showCropper.value = true
  }
  const closeCropper = () => {
    showCropper.value = false
    if (cropperImageSrc.value) {
      URL.revokeObjectURL(cropperImageSrc.value)
      cropperImageSrc.value = ''
    }
    if (iconInput.value) iconInput.value.value = ''
  }
  const cropImage = async () => {
    if (!cropperRef.value) return
    const { canvas } = cropperRef.value.getResult()
    if (!canvas) return
    const outputCanvas = document.createElement('canvas')
    outputCanvas.width = 1024
    outputCanvas.height = 1024
    const ctx = outputCanvas.getContext('2d')
    ctx.drawImage(canvas, 0, 0, 1024, 1024)
    outputCanvas.toBlob(async (blob) => {
      if (!blob) return
      const croppedFile = new File([blob], 'logo.png', { type: 'image/png' })
      appIconFile.value = croppedFile
      if (appIcon.value && !appIcon.value.startsWith('/api/')) URL.revokeObjectURL(appIcon.value)
      appIcon.value = URL.createObjectURL(blob)
      try {
        const result = await api.uploadIcon(croppedFile)
        uploadedIcon.value = result
        showToast(t('toast.iconSet'), 'success')
      } catch (error) {
        showErrorToast('toast.iconUploadFailed', error)
      }
      closeCropper()
    }, 'image/png', 1.0)
  }

  // Tasks
  const refreshTasks = async () => {
    try {
      const [tasksResult, queueResult] = await Promise.allSettled([
        api.getTasks(),
        api.getQueueStatus()
      ])
      if (tasksResult.status === 'fulfilled') {
        tasks.value = Array.isArray(tasksResult.value) ? tasksResult.value : []
      }
      if (queueResult.status === 'fulfilled') {
        queueStatus.value = queueResult.value
      }
    } catch (e) {
      // ignore
    }
  }
  const startPolling = () => {
    if (pollInterval) return
    pollInterval = setInterval(async () => {
      await refreshTasks()
      const hasProcessing = tasks.value.some((t) => t.status === 'processing')
      if (!hasProcessing) stopPolling()
    }, 2000)
  }
  const stopPolling = () => {
    if (pollInterval) {
      clearInterval(pollInterval)
      pollInterval = null
    }
  }

  const startTaskDirectly = async (taskId, options = {}) => {
    try {
      if (options.showRiskReviewingNotice !== false) {
        showToast(t('toast.aiRiskReviewing'), 'warning')
      }
      await api.startTask(taskId)
      if (options.notify !== false) {
        showToast(t('toast.taskStarted'), 'success')
      }
      await refreshTasks()
      startPolling()
    } catch (error) {
      if (isRiskReviewPendingError(error)) {
        let reason = ''
        try {
          const latestTask = await api.getTask(taskId)
          reason = extractRiskReviewReason(latestTask)
        } catch {
          reason = ''
        }
        if (reason) {
          showToast(t('toast.riskReviewPendingWithReason', { reason }), 'warning')
        } else {
          showToast(t('toast.riskReviewPending'), 'warning')
        }
        await refreshTasks()
        return
      }
      if (isRiskReviewRejectedError(error)) {
        showToast(t('toast.riskReviewRejected'), 'error')
        await refreshTasks()
        return
      }
      const mappedMessage = resolveStartTaskErrorMessage(error)
      if (mappedMessage) {
        showToast(mappedMessage, 'error')
      } else {
        showErrorToast('toast.startFailed', error)
      }
    }
  }

  const startTask = async (taskId) => {
    const canStartBuild = await requestRewardAdBeforeBuild()
    if (!canStartBuild) return
    await startTaskDirectly(taskId)
  }
  const retryTask = async (taskId) => {
    try {
      await api.retryTask(taskId)
      showToast(t('toast.taskRetried'), 'success')
      await refreshTasks()
    } catch (error) {
      showErrorToast('toast.retryFailed', error)
    }
  }
  const cancelTask = async (taskId) => {
    // 使用自定义确认对话框替代原生 confirm()，保证 UI 一致 + i18n
    const ok = await openConfirmDialog({
      message: t('toast.cancelConfirm'),
      confirmType: 'danger'
    })
    if (!ok) return
    try {
      await api.cancelTask(taskId)
      showToast(t('toast.taskCanceled') || t('toast.taskDeleted'), 'success')
      await refreshTasks()
    } catch (error) {
      showErrorToast('toast.cancelFailed', error)
    }
  }
  const deleteTask = async (taskId) => {
    const ok = await openConfirmDialog({
      message: t('toast.deleteConfirm'),
      confirmType: 'danger'
    })
    if (!ok) return
    try {
      await api.deleteTask(taskId)
      showToast(t('toast.taskDeleted'), 'success')
      await refreshTasks()
    } catch (error) {
      showErrorToast('toast.deleteFailed', error)
    }
  }

  const useTaskConfig = (task) => {
    updatingTaskId.value = task.id
    updatingTask.value = task
    quickGenerate.value = false
    quickGenerateStash.value = null

    const taskMode = task.mode || 'convert'
    if (taskMode === 'web' && !isWebModeEnabled.value) {
      mode.value = 'convert'
      webUrl.value = ''
    } else if (taskMode === 'desktop' && !isDesktopModeEnabled.value) {
      mode.value = 'convert'
      webUrl.value = ''
    } else {
      mode.value = taskMode
      webUrl.value = task.web_url || ''
    }
    enableAds.value = false
    adConfig.value = { appId: '', appKey: '', placementId: '' }
    const isCdnCapableMode = mode.value === 'convert' || mode.value === 'html'
    const taskCdnUrls = Array.isArray(task.cdn_localize_urls)
      ? task.cdn_localize_urls.map((item) => String(item || '').trim()).filter(Boolean)
      : []
    const taskCdnSelectAll = Boolean(task.cdn_localize_select_all)
    cdnLocalizeEnabled.value = isCdnCapableMode ? Boolean(task.cdn_localize_enabled) : false
    cdnSelectedUrls.value = isCdnCapableMode && cdnLocalizeEnabled.value
      ? (taskCdnSelectAll ? [] : taskCdnUrls)
      : []
    cdnLinkItems.value = isCdnCapableMode
      ? taskCdnUrls.map((url) => ({ url, type: 'other', occurrences: 0, file_count: 0, files: [] }))
      : []
    showCdnLocalizeModal.value = false
    cdnScanLoading.value = false

    const normalizedPermissions = normalizePermissionsForUi(task.config?.permissions || [])
    previousVersionName.value = task.config.version_name || '1.0.0'

    config.value = {
      ...config.value,
      app_name: task.config.app_name,
      package_name: task.config.package_name,
      version_name: bumpPatchVersion(task.config.version_name || '1.0.0'),
      version_code: (task.config.version_code || 1) + 1,
      output_format: task.config.output_format ?? 'apk',
      desktop_runtime: task.config.desktop_runtime ?? 'tauri',
      desktop_installer_mode: task.config.desktop_installer_mode ?? 'portable',
      desktop_port: normalizeDesktopPort(task.config.desktop_port),
      orientation: task.config.orientation ?? 'portrait',
      double_click_exit: task.config.double_click_exit ?? true,
      status_bar_hidden: task.config.status_bar_hidden ?? false,
      status_bar_style: task.config.status_bar_style ?? 'light',
      status_bar_color: task.config.status_bar_color ?? '#FFFFFF',
      webview_user_agent: task.config.webview_user_agent ?? 'android',
      download_mode: task.config.download_mode ?? 'picker',
      web_fill_mode: task.config.web_fill_mode ?? 'contain',
      permissions: normalizedPermissions.length ? normalizedPermissions : ['INTERNET', 'ACCESS_NETWORK_STATE'],
      keystore_alias: task.config.keystore_alias || '',
      keystore_password: task.config.keystore_password || '',
      key_password: task.config.key_password || ''
    }

    enablePermissions.value = normalizedPermissions.length > 0

    if (task.icon_filename) {
      uploadedIcon.value = { filename: task.icon_filename, reused: true }
      appIcon.value = api.getIconUrl(task.id)
    } else {
      uploadedIcon.value = null
    uploadedKeystore.value = null
    useCustomKeystore.value = false
    keystoreUploadError.value = ''
    if (keystoreInput.value) keystoreInput.value.value = ''
      appIcon.value = null
    }
    uploadedKeystore.value = null
    keystoreUploadError.value = ''
    if (keystoreInput.value) keystoreInput.value.value = ''

    uploadedFile.value = null
    uploadProgress.value = 0
    uploadedHtmlFile.value = null
    htmlUploadProgress.value = 0
    htmlInputMode.value = 'file'
    htmlEditorLoading.value = false
    htmlEditorDirty.value = false
    htmlEditorMarkers.value = []
    showHtmlEditorModal.value = false
    showHtmlPreviewModal.value = false
    htmlPreviewContent.value = ''
    htmlSavedContent.value = ''
    htmlSavedUploadContent.value = ''
    setHtmlEditorContent(defaultHtmlTemplate, false)

    if (mode.value === 'convert' || mode.value === 'desktop') {
      uploadedFile.value = { filename: 'project.zip', reused: true, original_name: '使用上一版本的项目文件', size: 0 }
      uploadProgress.value = 100
    } else if (mode.value === 'html') {
      uploadedHtmlFile.value = { filename: 'index.html', reused: true, original_name: t('html.reuseHtml'), size: 0 }
      htmlUploadProgress.value = 100
    }
    currentStep.value = 1
  }

  const ensureHtmlFileForTask = async () => {
    if (mode.value !== 'html') return null
    if (htmlInputMode.value === 'file') {
      if (!uploadedHtmlFile.value) {
        showToast(t('html.htmlRequired'), 'error')
        return null
      }
      htmlSavedUploadContent.value = ''
      return uploadedHtmlFile.value.filename
    }

    if (!hasSavedHtmlContent.value || htmlEditorDirty.value) {
      showToast(t('html.saveBeforeBuild'), 'error')
      return null
    }

    const diagnostics = computeHtmlDiagnosticsForContent(htmlSavedContent.value)
    if (diagnostics.length) {
      if (htmlEditorInstance.value) {
        refreshHtmlMarkers(htmlEditorInstance.value.state, diagnostics)
      }
      showToast(t('html.fixErrors', { count: diagnostics.length }), 'error')
      return null
    }

    if (
      uploadedHtmlFile.value?.filename &&
      !uploadedHtmlFile.value?.reused &&
      htmlSavedUploadContent.value &&
      htmlSavedUploadContent.value === htmlSavedContent.value
    ) {
      return uploadedHtmlFile.value.filename
    }

    const file = new File([htmlSavedContent.value], 'index.html', { type: 'text/html' })
    const result = await uploadHtml(file, {
      openPreview: false,
      openCdnModal: false,
      previewContent: htmlSavedContent.value,
      savedFromEditor: true,
      silentSuccess: true
    })
    if (!result) return null
    uploadedHtmlFile.value = result
    return result.filename
  }

  const buildCdnLocalizePayload = () => {
    if (mode.value !== 'convert' && mode.value !== 'html') {
      return { cdn_localize_enabled: false, cdn_localize_select_all: false, cdn_localize_urls: [] }
    }
    const normalizedUrls = Array.from(
      new Set(
        (Array.isArray(cdnSelectedUrls.value) ? cdnSelectedUrls.value : [])
          .map((item) => String(item || '').trim())
          .filter(Boolean)
      )
    )
    const enabled = Boolean(cdnLocalizeEnabled.value)
    const selectAll = Boolean(
      enabled &&
      hasCdnExternalLinks.value &&
      normalizedUrls.length > 0 &&
      normalizedUrls.length === cdnLinkItems.value.length
    )
    return {
      cdn_localize_enabled: enabled,
      cdn_localize_select_all: selectAll,
      cdn_localize_urls: enabled ? (selectAll ? [] : normalizedUrls) : []
    }
  }

  // Create/Update task
  const createTask = async () => {
    if (keystoreUpgradeVersionError.value) {
      showToast(keystoreUpgradeVersionError.value, 'error')
      return
    }
    if (!updatingTaskId.value) {
      if (!taskComplianceAck.value) {
        showToast(t('config.taskComplianceAckRequired'), 'error')
        return
      }
      if (taskComplianceError.value) {
        showToast(taskComplianceError.value, 'error')
        return
      }
    }
    if (!canCreateTask.value) {
      if (clientFreezeState.value.frozen) {
        showToast(
          t('config.clientFrozenByRisk', {
            reason: clientFreezeState.value.reason || t('config.clientFrozenByRiskDefaultReason')
          }),
          'error'
        )
      }
      return
    }
    if (mode.value === 'web' && !isWebModeEnabled.value) {
      showToast('Web（链接）转 APK 模式已关闭', 'error')
      return
    }
    if (mode.value === 'desktop' && !isDesktopModeEnabled.value) {
      showToast(t('toast.desktopModeDisabled'), 'error')
      return
    }
    if (packageNameError.value) {
      showToast(packageNameError.value, 'error')
      return
    }
    if (desktopPortError.value) {
      showToast(desktopPortError.value, 'error')
      return
    }
    if (!isKeystoreUploaded.value && keystorePasswordError.value) {
      showToast(keystorePasswordError.value, 'error')
      return
    }
    if (!isKeystoreUploaded.value && keyPasswordError.value) {
      showToast(keyPasswordError.value, 'error')
      return
    }
    isCreating.value = true
    try {
      let normalizedWebUrl = webUrl.value
      if (mode.value === 'web') {
        normalizedWebUrl = await resolveWebUrl(webUrl.value)
        if (!normalizedWebUrl) {
          showToast(t('web.urlUnreachable'), 'error')
          return
        }
        if (normalizedWebUrl !== webUrl.value) {
          webUrl.value = normalizedWebUrl
        }
      }

      const isQuickGenerate = quickGenerate.value && (mode.value === 'convert' || mode.value === 'web' || mode.value === 'html') && !updatingTaskId.value

    if (updatingTaskId.value) {
        if (compareVersion(config.value.version_name, previousVersionName.value) < 0) {
          showToast(t('toast.versionError'), 'error')
          return
        }
        if (mode.value === 'html') {
          const htmlFilename = await ensureHtmlFileForTask()
          if (!htmlFilename) return
        }
        const updateData = {
          filename: uploadedFile.value?.reused ? null : uploadedFile.value?.filename || null,
          html_filename: uploadedHtmlFile.value?.reused ? null : uploadedHtmlFile.value?.filename || null,
          icon_filename: uploadedIcon.value?.reused ? null : uploadedIcon.value?.filename || null,
          version_name: config.value.version_name,
          version_code: config.value.version_code,
          output_format: config.value.output_format,
          desktop_runtime: config.value.desktop_runtime,
          desktop_installer_mode: config.value.desktop_installer_mode,
          desktop_port: config.value.desktop_port,
          orientation: config.value.orientation,
          double_click_exit: config.value.double_click_exit,
          status_bar_hidden: config.value.status_bar_hidden,
          status_bar_style: config.value.status_bar_style,
          status_bar_color: config.value.status_bar_color,
          webview_user_agent: config.value.webview_user_agent,
          download_mode: config.value.download_mode,
          web_fill_mode: config.value.web_fill_mode,
          permissions: enablePermissions.value ? config.value.permissions : [],
          ...buildCdnLocalizePayload()
        }
        await api.updateTask(updatingTaskId.value, updateData)
        currentStep.value = 3
        showToast(`"${config.value.app_name}" 已更新至 v${config.value.version_name}`, 'success')
      } else {
        let htmlFilename = null
        if (mode.value === 'html') {
          htmlFilename = await ensureHtmlFileForTask()
          if (!htmlFilename) return
        }
        const taskData = {
          quick_generate: isQuickGenerate,
          mode: mode.value,
          compliance_ack: Boolean(taskComplianceAck.value),
          declared_use_case: normalizedTaskDeclaredUseCase.value,
          web_url: mode.value === 'web' ? normalizedWebUrl : null,
          ad_config: mode.value === 'web' && enableAds.value ? adConfig.value : null,
          filename: (mode.value === 'convert' || mode.value === 'desktop') ? uploadedFile.value.filename : null,
          html_filename: mode.value === 'html' ? htmlFilename : null,
          icon_filename: isQuickGenerate ? null : (uploadedIcon.value?.filename || null),
          keystore_filename: isQuickGenerate ? null : (uploadedKeystore.value?.filename || null),
          ...buildCdnLocalizePayload(),
          config: {
            app_name: config.value.app_name,
            package_name: config.value.package_name.trim(),
            version_name: config.value.version_name,
            version_code: config.value.version_code,
            output_format: config.value.output_format,
            desktop_runtime: config.value.desktop_runtime,
            desktop_installer_mode: config.value.desktop_installer_mode,
            desktop_port: config.value.desktop_port,
            orientation: config.value.orientation,
            double_click_exit: config.value.double_click_exit,
            status_bar_hidden: config.value.status_bar_hidden,
            status_bar_style: config.value.status_bar_style,
            status_bar_color: config.value.status_bar_color,
            webview_user_agent: config.value.webview_user_agent,
            download_mode: config.value.download_mode,
            web_fill_mode: config.value.web_fill_mode,
            permissions: enablePermissions.value ? config.value.permissions : [],
            keystore_alias: config.value.keystore_alias || null,
            keystore_password: config.value.keystore_password || null,
            key_password: config.value.key_password || null
          }
        }
        const created = await api.createTask(taskData)
        currentStep.value = 3
        showToast(t('toast.taskCreated'), 'success')
        const freezeState = extractClientFreezeStateFromTask(created)
        if (freezeState?.frozen) {
          applyClientFreezeState(freezeState)
          showToast(
            t('config.clientFrozenByRisk', {
              reason: freezeState.reason || t('config.clientFrozenByRiskDefaultReason')
            }),
            'warning'
          )
        }
        const reviewRequired = Boolean(created?.review_required)
        const reviewStatus = String(created?.review_status || '').trim().toLowerCase()
        const requiresManualReview = reviewRequired && reviewStatus !== 'approved'
        if (requiresManualReview) {
          const reason = extractRiskReviewReason(created)
          if (reason) {
            showToast(t('toast.riskReviewPendingWithReason', { reason }), 'warning')
          } else {
            showToast(t('toast.riskReviewPending'), 'warning')
          }
          await refreshTasks()
        } else {
          const canStartBuild = await requestRewardAdBeforeBuild()
          if (canStartBuild) {
            await startTaskDirectly(created.id, { notify: false })
          } else {
            await refreshTasks()
          }
        }
      }
      resetForm({ preserveQuickGenerate: isQuickGenerate })
      await refreshTasks()
    } catch (error) {
      const mappedMessage = resolveCreateTaskErrorMessage(error)
      if (mappedMessage) {
        showToast(mappedMessage, 'error')
      } else {
        showErrorToast('toast.operationFailed', error)
      }
    } finally {
      isCreating.value = false
    }
  }

  const resetForm = (options = {}) => {
    const preserveQuickGenerate = Boolean(options.preserveQuickGenerate)
    webUrl.value = ''
    enableAds.value = false
    enablePermissions.value = false
    adConfig.value = { appId: '', appKey: '', placementId: '' }
    resetCdnLocalizationState(false)
    uploadedFile.value = null
    uploadProgress.value = 0
    uploadedHtmlFile.value = null
    htmlUploadProgress.value = 0
    htmlInputMode.value = 'file'
    htmlEditorLoading.value = false
    htmlEditorDirty.value = false
    htmlEditorMarkers.value = []
    showHtmlEditorModal.value = false
    showHtmlPreviewModal.value = false
    htmlPreviewContent.value = ''
    htmlSavedContent.value = ''
    htmlSavedUploadContent.value = ''
    setHtmlEditorContent(defaultHtmlTemplate, false)
    if (htmlInput.value) htmlInput.value.value = ''
    if (appIcon.value && !appIcon.value.startsWith('/api/')) URL.revokeObjectURL(appIcon.value)
    appIcon.value = null
    appIconFile.value = null
    uploadedIcon.value = null
    uploadedKeystore.value = null
    useCustomKeystore.value = false
    keystoreUploadError.value = ''
    if (keystoreInput.value) keystoreInput.value.value = ''
    iconError.value = ''
    updatingTaskId.value = null
    updatingTask.value = null
    if (!preserveQuickGenerate) {
      quickGenerate.value = false
      quickGenerateStash.value = null
    }
    taskComplianceAck.value = false
    taskDeclaredUseCase.value = ''
    previousVersionName.value = ''
    config.value = {
      app_name: '',
      package_name: '',
      version_name: '1.0.0',
      version_code: 1,
      output_format: 'apk',
      desktop_runtime: 'tauri',
      desktop_installer_mode: 'portable',
      desktop_port: generateDesktopPort(),
      orientation: 'portrait',
      double_click_exit: true,
      status_bar_hidden: false,
      status_bar_style: 'light',
      status_bar_color: '#FFFFFF',
      webview_user_agent: 'android',
      download_mode: 'picker',
      web_fill_mode: 'contain',
      permissions: ['INTERNET', 'ACCESS_NETWORK_STATE'],
      keystore_alias: '',
      keystore_password: '',
      key_password: ''
    }
    if (preserveQuickGenerate && quickGenerate.value && (mode.value === 'convert' || mode.value === 'web' || mode.value === 'html')) {
      applyQuickGenerateDefaults()
    }
    currentStep.value = 1
  }

  // Logs
  const getCurrentLogTask = () => tasks.value.find((item) => item.id === currentLogTaskId.value) || null
  const refreshTaskDiagnosis = async (refresh = false, fromPolling = false) => {
    const task = getCurrentLogTask()
    if (!task || task.status !== 'failed') {
      stopDiagnosisPolling()
      taskDiagnosis.value = null
      taskDiagnosisError.value = ''
      taskDiagnosisLoading.value = false
      return
    }
    if (!fromPolling) {
      taskDiagnosisLoading.value = true
      taskDiagnosisError.value = ''
    }
    try {
      const result = await api.getTaskDiagnosis(task.id, refresh)
      taskDiagnosis.value = result?.diagnosis || null
      const diagnosisStatus = String(taskDiagnosis.value?.status || '').trim().toLowerCase()
      if (diagnosisStatus === 'running') {
        scheduleDiagnosisPolling()
      } else {
        stopDiagnosisPolling()
      }
    } catch (error) {
      stopDiagnosisPolling()
      taskDiagnosis.value = null
      taskDiagnosisError.value = t('logs.aiFetchFailed')
    } finally {
      if (!fromPolling) {
        taskDiagnosisLoading.value = false
      }
    }
  }
  const rerunTaskDiagnosis = async () => {
    const task = getCurrentLogTask()
    if (!task || task.status !== 'failed') return
    stopDiagnosisPolling()
    taskDiagnosisLoading.value = true
    taskDiagnosisError.value = ''
    try {
      const result = await api.rerunTaskDiagnosis(task.id)
      taskDiagnosis.value = result?.diagnosis || null
      showToast(t('logs.aiRerunStarted'), 'success')
      const diagnosisStatus = String(taskDiagnosis.value?.status || '').trim().toLowerCase()
      if (diagnosisStatus === 'running') {
        scheduleDiagnosisPolling()
      } else {
        await refreshTaskDiagnosis(false)
      }
    } catch (error) {
      stopDiagnosisPolling()
      taskDiagnosisError.value = t('logs.aiRerunFailed')
      showToast(t('logs.aiRerunFailed'), 'error')
    } finally {
      taskDiagnosisLoading.value = false
    }
  }
  const viewLogs = async (taskId) => {
    currentLogTaskId.value = taskId
    showLogs.value = true
    await refreshLogs()
  }
  const closeLogs = () => {
    stopDiagnosisPolling()
    showLogs.value = false
    currentLogTaskId.value = null
    taskLogs.value = []
    taskDiagnosis.value = null
    taskDiagnosisLoading.value = false
    taskDiagnosisError.value = ''
  }
  const refreshLogs = async () => {
    if (!currentLogTaskId.value) return
    try {
      const result = await api.getTaskLogs(currentLogTaskId.value, 500)
      taskLogs.value = result.logs || []
      setTimeout(() => {
        if (logsContainer.value) logsContainer.value.scrollTop = logsContainer.value.scrollHeight
      }, 50)
    } catch {
      taskLogs.value = []
    }
    await refreshTaskDiagnosis(false)
  }

  // Settings
  const openSettings = () => {
    showSettings.value = true
  }

  const closeSettings = () => (showSettings.value = false)
  const refreshClientFreezeStatus = async () => {
    try {
      const result = await api.getClientFreezeStatus()
      applyClientFreezeState(result || {})
    } catch {
      // ignore
    }
  }
  const fetchAdminFeatures = async () => {
    try {
      const result = await api.getAdminFeatures()
      featureFlags.value = {
        web_link_to_apk_enabled: Boolean(result?.web_link_to_apk_enabled),
        zip_to_desktop_enabled: Boolean(result?.zip_to_desktop_enabled),
        rewarded_build_ads_enabled: Boolean(result?.rewarded_build_ads_enabled),
        client_login_enabled: result?.client_login_enabled === undefined ? true : Boolean(result?.client_login_enabled),
        client_sms_login_enabled: result?.client_sms_login_enabled === true,
        client_register_enabled: result?.client_register_enabled === undefined ? true : Boolean(result?.client_register_enabled),
      }
    } catch {
      featureFlags.value = {
        web_link_to_apk_enabled: false,
        zip_to_desktop_enabled: false,
        rewarded_build_ads_enabled: false,
        client_login_enabled: true,
        client_sms_login_enabled: false,
        client_register_enabled: true,
      }
    }
    if (!isWebModeEnabled.value && mode.value === 'web') {
      mode.value = 'convert'
    }
    if (!isDesktopModeEnabled.value && mode.value === 'desktop') {
      mode.value = 'convert'
    }
    if (!isAuthEntryEnabled.value) {
      if (showAuthModal.value) {
        closeAuthModal()
      }
      return
    }
    if (authMode.value === 'register' && !isClientRegisterEnabled.value && isClientLoginEnabled.value) {
      authMode.value = 'login'
    }
    if (authMode.value === 'login' && !isClientLoginEnabled.value && isClientRegisterEnabled.value) {
      authMode.value = 'register'
    }
    if (authMode.value === 'login' && authLoginMethod.value === 'sms' && !isClientSmsLoginEnabled.value) {
      authLoginMethod.value = 'password'
      authSmsSending.value = false
      stopAuthSmsCountdown()
    }
    await refreshClientFreezeStatus()
  }
  const fetchAnnouncements = async () => {
    try {
      const result = await api.getAdminAnnouncements()
      announcements.value = Array.isArray(result) ? result : (result?.items || [])
      resolveActiveAnnouncement()
    } catch {
      announcements.value = []
      resolveActiveAnnouncement()
    }
  }

  const dismissAnnouncement = () => {
    if (activeAnnouncement.value) {
      const id = String(activeAnnouncement.value.id)
      localStorage.setItem('apk_builder_announcement_id', id)
      dismissedAnnouncementId.value = id
      resolveActiveAnnouncement()
    }
  }

  const loadSystemInfo = async () => {
    try {
      const result = await api.getSystemInfo()
      deviceInfo.value = result || deviceInfo.value
    } catch {
      // ignore
    }
  }

  const refreshGithubRepoStats = async () => {
    try {
      const result = await api.getGithubRepoStats()
      if (typeof result?.repo_url === 'string' && /^https?:\/\//.test(result.repo_url)) {
        githubRepoUrl.value = result.repo_url
      }
      const stars = Number(result?.stars)
      if (Number.isFinite(stars) && stars >= 0) {
        githubStarCount.value = stars
      }
    } catch {
      // ignore
    }
  }

  const handleDocumentVisibilityChange = () => {
    if (document.hidden) return
    refreshGithubRepoStats()
  }

  const triggerFeedbackFileSelect = () => {
    feedbackFileInput.value?.click?.()
  }

  const handleFeedbackFiles = (event) => {
    const files = Array.from(event.target.files || [])
    const maxSize = 10 * 1024 * 1024
    const filtered = files.filter((file) => file.size <= maxSize).slice(0, 5)
    if (filtered.length < files.length) {
      showToast(t('toast.feedbackFileLimit'), 'error')
    }
    feedbackImages.value = filtered
  }

  const submitFeedback = async () => {
    if (!feedbackContent.value) {
      showToast(t('toast.feedbackEmpty'), 'error')
      return
    }
    feedbackSubmitting.value = true
    try {
      await api.submitFeedback({
        client_id: api.getClientId(),
        content: feedbackContent.value,
        device_info: { ...deviceInfo.value },
        images: feedbackImages.value
      })
      feedbackContent.value = ''
      feedbackImages.value = []
      showToast(t('toast.feedbackSent'), 'success')
    } catch (error) {
      showToast(t('toast.feedbackFailed'), 'error')
    } finally {
      feedbackSubmitting.value = false
    }
  }

  const refreshAll = async () => {
    await refreshTasks()
    await fetchAnnouncements()
    await loadSystemInfo()
    refreshGithubRepoStats()
  }

  const openDonation = (fromAuto) => {
    if (fromAuto && donationAutoDisabled.value) return
    donationHideChecked.value = false
    showDonation.value = true
  }
  const closeDonation = () => {
    if (donationHideChecked.value) {
      localStorage.setItem('apk_builder_donation_hide', '1')
      donationAutoDisabled.value = true
    }
    showDonation.value = false
  }
  const acceptComplianceNotice = () => {
    showComplianceNotice.value = false
  }
  const rejectComplianceNotice = () => {
    if (window.windowControls?.close) {
      window.windowControls.close()
      return
    }
    window.location.replace('about:blank')
  }
  const taskStatusCache = ref(new Map())
  const taskStatusReady = ref(false)
  const shouldAutoShowDonation = () => Math.random() < 0.1
  watch(
    tasks,
    (next) => {
      const prev = taskStatusCache.value
      const updates = new Map(prev)
      let newSuccess = null
      for (const task of next) {
        const prevStatus = prev.get(task.id)
        updates.set(task.id, task.status)
        if (taskStatusReady.value && task.status === 'success' && prevStatus !== 'success') {
          newSuccess = task
          break
        }
      }
      taskStatusCache.value = updates
      if (taskStatusReady.value && newSuccess && !showDonation.value && shouldAutoShowDonation()) {
        openDonation(true)
      }
      taskStatusReady.value = true
    },
    { deep: true }
  )

  watch(useCustomKeystore, (next) => {
    if (!next) {
      clearKeystoreUpload()
    }
  })

  watch(sortedTasks, () => {
    if (currentTaskPage.value > totalTaskPages.value) {
      goToTaskPage(totalTaskPages.value)
    }
  })

  // 全局 ESC 键：按最上层弹窗的优先级关闭对话框
  // 顺序由"最顶层/最新打开的"到"最底层"
  const handleGlobalEscape = (event) => {
    if (event.key !== 'Escape') return
    // 合规弹窗需要用户显式点接受/拒绝，不支持 ESC 关闭
    if (showComplianceNotice.value) return
    if (confirmDialog.value.visible) {
      event.preventDefault()
      closeConfirmDialog(false)
      return
    }
    const dialogs = [
      { open: showCropper, close: closeCropper },
      { open: showLogs, close: closeLogs },
      { open: showHtmlPreviewModal, close: closeHtmlPreviewModal },
      { open: showCdnLocalizeModal, close: closeCdnLocalizeModal },
      { open: showHtmlEditorModal, close: closeHtmlEditorModal },
      { open: showAuthModal, close: closeAuthModal },
      { open: showDonation, close: closeDonation },
      { open: showSettings, close: closeSettings }
    ]
    for (const d of dialogs) {
      if (d.open && d.open.value) {
        event.preventDefault()
        try { d.close() } catch (_) { /* ignore */ }
        return
      }
    }
  }

  onMounted(async () => {
    updateMobileShell()
    applyTheme(currentTheme.value)
    // 首次加载时应用保存的语言到 html[lang]，便于辅助技术发音
    applyDocumentLang(currentLang.value)
    showComplianceNotice.value = true
    document.addEventListener('click', handleClickOutside)
    document.addEventListener('visibilitychange', handleDocumentVisibilityChange)
    document.addEventListener('keydown', handleGlobalEscape)
    window.addEventListener('resize', updateMobileShell)
    window.addEventListener('pagehide', releaseDesktopOutputsOnPageExit)
    window.addEventListener('beforeunload', releaseDesktopOutputsOnPageExit)
    startDesktopOutputHeartbeat()
    const githubCallbackResult = consumeGithubCallbackHash()
    const authReady = await syncAuthUser({ silent: true })
    if (githubCallbackResult.handled) {
      if (githubCallbackResult.success && authReady) {
        showToast(t('auth.githubLoginSuccess'), 'success')
      } else if (githubCallbackResult.error) {
        showToast(resolveAuthErrorMessage(githubCallbackResult.error), 'error')
      }
    }
    await fetchAdminFeatures()
    await refreshTasks()
    await fetchAnnouncements()
    await loadSystemInfo()
    refreshGithubRepoStats()
    githubStatsInterval = setInterval(() => {
      refreshGithubRepoStats()
    }, 10 * 60 * 1000)
    if (window.windowControls?.isMaximized) {
      try {
        isMaximized.value = await window.windowControls.isMaximized()
      } catch {
        // ignore
      }
    }
  })

  onUnmounted(() => {
    stopPolling()
    stopDiagnosisPolling()
    document.removeEventListener('click', handleClickOutside)
    document.removeEventListener('visibilitychange', handleDocumentVisibilityChange)
    document.removeEventListener('keydown', handleGlobalEscape)
    window.removeEventListener('resize', updateMobileShell)
    window.removeEventListener('pagehide', releaseDesktopOutputsOnPageExit)
    window.removeEventListener('beforeunload', releaseDesktopOutputsOnPageExit)
    stopDesktopOutputHeartbeat()
    if (githubStatsInterval) {
      clearInterval(githubStatsInterval)
      githubStatsInterval = null
    }
    if (desktopOutputRefreshTimer) {
      clearTimeout(desktopOutputRefreshTimer)
      desktopOutputRefreshTimer = null
    }
    if (mobileSwipeAnimTimer) {
      clearTimeout(mobileSwipeAnimTimer)
      mobileSwipeAnimTimer = null
    }
    if (authShakeTimer) {
      clearTimeout(authShakeTimer)
      authShakeTimer = null
    }
    stopAuthSmsCountdown()
    mobileSwipeTracking.value = false
    mobileSwipeDragging.value = false
    mobileSwipeOffsetX.value = 0
    if (appIcon.value && !appIcon.value.startsWith('/api/')) URL.revokeObjectURL(appIcon.value)
    if (cropperImageSrc.value) URL.revokeObjectURL(cropperImageSrc.value)
    if (htmlDiagnosticsHandle) {
      if (typeof cancelAnimationFrame === 'function') {
        cancelAnimationFrame(htmlDiagnosticsHandle)
      } else {
        clearTimeout(htmlDiagnosticsHandle)
      }
      htmlDiagnosticsHandle = null
    }
    if (htmlEditorInstance.value) {
      htmlEditorInstance.value.destroy()
      htmlEditorInstance.value = null
    }
    showHtmlPreviewModal.value = false
    htmlPreviewContent.value = ''
  })

  return {
    alipayQr,
    wechatQr,
    currentTheme,
    currentLang,
    showLangMenu,
    openDownloadMenu,
    githubRepoUrl,
    githubStarCount,
    hasGithubStarCount,
    githubStarCountText,
    languages,
    currentLangLabel,
    i18n,
    t,
    applyTheme,
    toggleTheme,
    changeLanguage,
    toggleDownloadMenu,
    closeDownloadMenu,
    handleClickOutside,
    showAuthModal,
    authMode,
    authLoginMethod,
    authSubmitting,
    githubAuthSubmitting,
    authSmsSending,
    authSmsCountdown,
    authSubmitButtonShake,
    authError,
    authForm,
    isLoggedIn,
    authDisplayName,
    isAuthEntryEnabled,
    isClientLoginEnabled,
    isClientSmsLoginEnabled,
    isClientRegisterEnabled,
    openAuthModal,
    closeAuthModal,
    switchAuthMode,
    switchAuthLoginMethod,
    submitAuthForm,
    sendAuthSmsCode,
    startGithubAuth,
    logoutCurrentUser,
    mode,
    isWebModeEnabled,
    isDesktopModeEnabled,
    isRewardedBuildAdsEnabled,
    mainRef,
    mobilePageHeadRef,
    convertUploadSection,
    htmlUploadSection,
    webUrlSection,
    tasksSection,
    profileSection,
    webUrl,
    enableAds,
    adConfig,
    enablePermissions,
    useCustomKeystore,
    quickGenerate,
    quickGenerateStash,
    codeCopied,
    mobileTab,
    isMobileShell,
    mobileSettingsLabel,
    mobileTabTitle,
    mobileTabSubtitle,
    siteContent,
    mobilePageAnimClass,
    mobileSwipeStyle,
    mobileSwipeDragging,
    isMobileViewport,
    switchMobileTab,
    handleMobileSwipeStart,
    handleMobileSwipeMove,
    handleMobileSwipeEnd,
    handleMobileSwipeCancel,
    scrollToProjectSection,
    handleModeChange,
    jsTemplate,
    copyJsCode,
    permissionsList,
    normalizePermissionForUi,
    normalizePermissionsForUi,
    defaultHtmlTemplate,
    currentStep,
    isDragging,
    isHtmlDragging,
    fileInput,
    htmlInput,
    htmlInputMode,
    htmlEditorContainer,
    htmlEditorModalContainer,
    htmlEditorInstance,
    htmlEditorReady,
    htmlEditorContent,
    htmlEditorDirty,
    htmlEditorMarkers,
    htmlSavedContent,
    showHtmlEditorModal,
    showHtmlPreviewModal,
    htmlPreviewContent,
    iconInput,
    keystoreInput,
    uploadedKeystore,
    keystoreUploadError,
    latestSamePackageTask,
    keystoreUpgradeVersionError,
    keystoreUpgradeVersionHint,
    uploadedFile,
    uploadedHtmlFile,
    uploadProgress,
    htmlUploadProgress,
    isCreating,
    cdnScanLoading,
    showCdnLocalizeModal,
    cdnLinkItems,
    cdnSelectedUrls,
    cdnLocalizeEnabled,
    hasCdnExternalLinks,
    cdnSelectedCount,
    cdnAllSelected,
    cdnLocalizeAdvised,
    isHtmlUploading,
    htmlEditorContentEmpty,
    htmlErrorCount,
    hasSavedHtmlContent,
    canSaveEditorHtml,
    canUseSavedHtmlForBuild,
    htmlEditorLoading,
    htmlEditorThemeCompartment,
    isHtmlProgrammaticUpdate,
    htmlDiagnosticsHandle,
    tasks,
    queueStatus,
    pollInterval,
    showSettings,
    announcements,
    deviceInfo,
    feedbackContent,
    feedbackImages,
    feedbackFileInput,
    feedbackSubmitting,
    showDonation,
    donationHideChecked,
    donationAutoDisabled,
    showComplianceNotice,
    taskComplianceAck,
    taskDeclaredUseCase,
    taskDeclaredUseCaseMinLength,
    taskDeclaredUseCaseMaxLength,
    normalizedTaskDeclaredUseCase,
    taskComplianceError,
    complianceNotice,
    previousVersionName,
    showLogs,
    taskLogs,
    taskDiagnosis,
    taskDiagnosisLoading,
    taskDiagnosisError,
    currentLogTaskId,
    logsContainer,
    updatingTaskId,
    updatingTask,
    appIcon,
    appIconFile,
    uploadedIcon,
    iconError,
    showCropper,
    cropperRef,
    cropperImageSrc,
    cropperStencilProps,
    cropperDefaultSize,
    isMaximized,
    windowControlsAvailable,
    minimizeWindow,
    toggleMaximizeWindow,
    closeWindow,
    config,
    applyQuickGenerateDefaults,
    stashQuickGenerateState,
    restoreQuickGenerateState,
    enterQuickGenerate,
    exitQuickGenerate,
    toast,
    showToast,
    // 自定义确认对话框
    confirmDialog,
    openConfirmDialog,
    closeConfirmDialog,
    isValidPackageName,
    isValidUrl,
    isValidHostName,
    isValidPort,
    isValidWebUrl,
    webUrlError,
    packageNameError,
    desktopPortError,
    keystorePasswordError,
    keyPasswordError,
    isKeystoreUploaded,
    canCreateTask,
    applyHtmlEditorTheme,
    resolveWebUrl,
    getTaskTime,
    sortedTasks,
    taskPageSize,
    currentTaskPage,
    totalTaskPages,
    pagedTasks,
    taskPageNumbers,
    goToTaskPage,
    taskStats,
    nativeAdRequesting,
    dismissedAnnouncementId,
    activeAnnouncement,
    resolveActiveAnnouncement,
    formatFileSize,
    formatDate,
    parseVersionParts,
    compareVersion,
    bumpPatchVersion,
    getStatusText,
    getTaskIcon,
    assignRandomDesktopPort,
    getDownloadUrl,
    getKeystoreUrl,
    downloadTaskArtifact,
    isQueuedTask,
    isCancelableTask,
    resetCdnLocalizationState,
    selectAllCdnLinks,
    clearCdnLinkSelection,
    isCdnLinkSelected,
    getCdnTypeLabel,
    toggleCdnLinkSelection,
    handleCdnLocalizeEnabledChange,
    openCdnLocalizeModal,
    closeCdnLocalizeModal,
    scanUploadedExternalLinks,
    rescanExternalLinks,
    triggerFileInput,
    handleFileSelect,
    handleDrop,
    uploadFile,
    handleHtmlSelect,
    handleHtmlDrop,
    uploadHtml,
    waitForFrame,
    htmlEditorLightTheme,
    htmlEditorDarkTheme,
    getHtmlEditorTheme,
    createHtmlEditorState,
    computeHtmlDiagnostics,
    computeHtmlDiagnosticsForContent,
    refreshHtmlMarkers,
    applyHtmlDiagnostics,
    scheduleHtmlDiagnostics,
    setHtmlEditorContent,
    destroyHtmlEditor,
    mountHtmlEditor,
    setHtmlInputMode,
    syncHtmlEditorContent,
    openHtmlEditorModal,
    closeHtmlEditorModal,
    openHtmlPreview,
    closeHtmlPreviewModal,
    previewCurrentHtml,
    saveEditorHtml,
    revealHtmlMarker,
    isHtmlErrorMarker,
    htmlMarkerLabel,
    triggerKeystoreInput,
    handleKeystoreSelect,
    clearKeystoreUpload,
    handleIconSelect,
    closeCropper,
    cropImage,
    refreshTasks,
    startPolling,
    stopPolling,
    startTask,
    retryTask,
    cancelTask,
    deleteTask,
    useTaskConfig,
    ensureHtmlFileForTask,
    createTask,
    resetForm,
    viewLogs,
    closeLogs,
    refreshLogs,
    rerunTaskDiagnosis,
    openSettings,
    closeSettings,
    fetchAnnouncements,
    dismissAnnouncement,
    loadSystemInfo,
    triggerFeedbackFileSelect,
    handleFeedbackFiles,
    submitFeedback,
    refreshAll,
    openDonation,
    closeDonation,
    acceptComplianceNotice,
    rejectComplianceNotice,
    taskStatusCache,
    taskStatusReady,
    shouldAutoShowDonation,
  }
}
