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
import {
  canSubmitInitialFeedback,
  createFeedbackInboxGuard,
  enqueueUnreadAdminMessages,
  readFeedbackTickets,
  revokeFeedbackPreviewUrls,
  sanitizeFeedbackReplyContent,
  saveFeedbackTicket,
  selectAdminMessageText,
  selectFeedbackReplyImages,
  shouldDismissFeedbackQueueMessage
} from '../utils/feedbackConversation'

export const useAppState = () => {
  const alipayQr = new URL('../pics/支付宝.png', import.meta.url).href
  const wechatQr = new URL('../pics/微信.png', import.meta.url).href

  // Theme / Language
  const currentTheme = ref(getSavedTheme())
  const currentLang = ref(getSavedLanguage())
  const showLangMenu = ref(false)
  const appBootLoading = ref(true)
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

  // 模式与功能开关状态
  const mode = ref('convert') // convert | web | html | desktop；原生 Android 由后端自动识别
  const featureFlags = ref({
    web_link_to_apk_enabled: false,
    zip_to_desktop_enabled: false,
    native_android_packaging_enabled: false,
    rewarded_build_ads_enabled: false,
    donation_popup_probability: 10,
    donation_popup_message: '',
    compliance_notice_enabled: false,
    compliance_notice_title: 'User Agreement and Terms of Service',
    compliance_notice_effective_date: '2026-05-13',
    compliance_notice_content: '',
    compliance_notice_accept_button: 'Agree and Continue',
    compliance_notice_reject_button: 'Decline and Exit',
    client_login_enabled: true,
    client_sms_login_enabled: false,
    client_register_enabled: true,
    upload_max_size_mb: 200,
  })
  const buildQuotaContext = ref({
    build_code_enabled: false,
    build_quota_mode: 'free_unlimited',
    effective_build_quota_mode: 'free_unlimited',
    free_build_quota_default: 0,
    quota_require_login: false,
    subject_type: '',
    subject_id: '',
    remaining_balance: null,
    consumed_total: null,
    is_unlimited: true
  })
  const buildCodeInput = ref('')
  const buildCodeRedeeming = ref(false)
  const isWebModeEnabled = computed(() => Boolean(featureFlags.value.web_link_to_apk_enabled))
  const isDesktopModeEnabled = computed(() => Boolean(featureFlags.value.zip_to_desktop_enabled))
  const isRewardedBuildAdsEnabled = computed(() => Boolean(featureFlags.value.rewarded_build_ads_enabled))
  const isClientLoginEnabled = computed(() => featureFlags.value.client_login_enabled !== false)
  const isClientSmsLoginEnabled = computed(() => featureFlags.value.client_sms_login_enabled === true)
  const isClientRegisterEnabled = computed(() => featureFlags.value.client_register_enabled !== false)
  const isAuthEntryEnabled = computed(() => isClientLoginEnabled.value || isClientRegisterEnabled.value)
  const isBuildQuotaUnlimited = computed(() => Boolean(buildQuotaContext.value.is_unlimited))
  const buildPaymentPlans = ref([])
  const buildPaymentPlansLoading = ref(false)
  const buildPaymentPlansError = ref('')
  const buildPaymentAlipayConfigured = ref(false)
  const showBuildPaymentModal = ref(false)
  const buildPaymentCreating = ref(false)
  const buildPaymentPolling = ref(false)
  const buildPaymentOrder = ref(null)
  let buildPaymentPollTimer = null
  const isBuildPaymentModeEnabled = computed(() => {
    if (isBuildQuotaUnlimited.value) return false
    const mode = String(buildQuotaContext.value.effective_build_quota_mode || buildQuotaContext.value.build_quota_mode || '').trim().toLowerCase()
    return ['free_quota', 'code_only', 'free_plus_code'].includes(mode)
  })
  const normalizeUploadMaxSizeMb = (value) => {
    const num = Number(value)
    if (!Number.isFinite(num)) return 200
    if (num < 1) return 1
    if (num > 10240) return 10240
    return Math.round(num)
  }
  const normalizeDonationPopupProbability = (value) => {
    const num = Number(value)
    if (!Number.isFinite(num)) return 10
    if (num < 0) return 0
    if (num > 100) return 100
    return Math.round(num)
  }
  const donationPopupProbability = computed(() => normalizeDonationPopupProbability(featureFlags.value.donation_popup_probability))
  const donationPopupMessage = computed(() => {
    const text = String(featureFlags.value.donation_popup_message || '').replace(/\r\n/g, '\n').replace(/\r/g, '\n').trim()
    return text
  })
  const complianceNoticeEnabled = computed(() => featureFlags.value.compliance_notice_enabled === true)
  const normalizeComplianceNoticeText = (value, maxLength, fallback = '') => {
    const text = String(value || '').replace(/\r\n/g, '\n').replace(/\r/g, '\n').trim()
    if (!text) return fallback
    return text.slice(0, maxLength)
  }
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
  const quickGenerateSupportedModes = new Set(['convert', 'web', 'html'])
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

  const getProjectEntrySection = () => {
    if (mode.value === 'convert' || mode.value === 'desktop') return convertUploadSection.value
    if (mode.value === 'html') return htmlUploadSection.value
    return webUrlSection.value
  }

  const scrollToProjectSection = async ({ includeDesktop = false } = {}) => {
    if (!includeDesktop && !isMobileViewport()) return
    if (isMobileShell.value) {
      await scrollToMobileHeadAnchor()
      return
    }
    await scrollWithinMain(getProjectEntrySection())
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

  const openFirstTaskGuide = async () => {
    if (isMobileShell.value && mobileTab.value !== 'build') {
      await switchMobileTab('build', { animate: true })
    } else if (mobileTab.value !== 'build') {
      mobileTab.value = 'build'
    }
    await nextTick()
    await scrollToProjectSection({ includeDesktop: true })
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
    mode.value = value === 'native' ? 'convert' : value
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
  const feedbackInboxGuard = createFeedbackInboxGuard()
  const feedbackTickets = ref(readFeedbackTickets())
  const feedbackMessages = ref([])
  const feedbackReplyQueue = ref([])
  const activeFeedbackTicketId = ref(null)
  const showFeedbackConversation = ref(false)
  const feedbackReplyContent = ref('')
  const feedbackReplyImages = ref([])
  const feedbackReplyFileInput = ref(null)
  const feedbackReplySubmitting = ref(false)
  const feedbackAttachmentPreviews = ref({})
  const activeFeedbackReply = computed(() => feedbackReplyQueue.value[0] || null)
  const activeFeedbackTicket = computed(() => feedbackTickets.value.find((ticket) => ticket.feedback_id === activeFeedbackTicketId.value) || null)
  const activeFeedbackConversationMessages = computed(() => feedbackMessages.value
    .filter((message) => message.feedback_id === activeFeedbackTicketId.value)
    .sort((left, right) => String(left.created_at || '').localeCompare(String(right.created_at || ''))))
  const showDonation = ref(false)
  const donationHideChecked = ref(false)
  const donationAutoDisabled = ref(localStorage.getItem('apk_builder_donation_hide') === '1')
  const donationDialogPrimaryText = computed(() => {
    const customText = donationPopupMessage.value
    if (!customText) return t('donation.message')
    const [firstLine] = customText.split('\n')
    return String(firstLine || '').trim() || t('donation.message')
  })
  const donationDialogSecondaryText = computed(() => {
    const customText = donationPopupMessage.value
    if (!customText) return t('donation.subMessage')
    const lines = customText
      .split('\n')
      .map((line) => String(line || '').trim())
      .filter((line) => line)
    if (lines.length <= 1) return ''
    return lines.slice(1).join(' ')
  })
  const showComplianceNotice = ref(false)
  const taskComplianceAck = ref(false)
  const previousVersionName = ref('')
  const clientFreezeState = ref({
    frozen: false,
    reason: '',
    contact: '',
    source_task_id: '',
    frozen_at: '',
    freeze_expires_at: '',
    freeze_remaining_seconds: 0,
    freeze_seconds: 600,
    cooldown_remaining_seconds: 0,
    cooldown_seconds: 600
  })

  const complianceNoticeByLang = {
    en: {
      title: 'User Agreement and Terms of Service',
      effectiveDateLabel: 'Effective date',
      effectiveDate: '2026-05-13',
      intro:
        'Please read this agreement carefully before using the client and related services. By clicking "Agree and Continue", you confirm that you have read, understood, and accepted all terms.',
      sections: [
        {
          title: '1. Scope and Acceptance',
          lines: [
            'This agreement applies to upload, packaging, build, download, log viewing, and all related functions.',
            'If you do not agree with any term, please stop using the service immediately.'
          ]
        },
        {
          title: '2. Lawful Use and Authorization',
          lines: [
            'You must ensure all uploaded code, assets, names, package identifiers, and domains are lawful and authorized.',
            'You must not submit content that violates laws, regulations, third-party rights, or platform security policies.'
          ]
        },
        {
          title: '3. Prohibited App Categories',
          lines: [
            'The platform strictly prohibits building or distributing apps related to: fake finance and loans, fake government or authority channels, fake customer service and support, gambling and betting.',
            'The platform strictly prohibits pyramid schemes and referral fraud, phishing login and credential theft, remote control abuse, spyware, trojans, cracking tools, piracy, and unauthorized distribution.',
            'The platform strictly prohibits creating unlicensed app stores, fake application marketplaces, or deceptive app distribution centers.'
          ]
        },
        {
          title: '4. Automated Risk Control and Blocking',
          lines: [
            'Your app metadata, package identifiers, use-case statement, source files, HTML content, external links, and permission combinations may be scanned by rules and AI models.',
            'If high-risk indicators are detected, the platform may block task creation or build execution immediately and record the reason for compliance review.'
          ]
        },
        {
          title: '5. Consequences of Violations',
          lines: [
            'For confirmed or strongly suspected violations, we may suspend tasks, freeze the client_id, restrict features, reject builds, terminate service, and preserve evidence.',
            'For serious cases, we may report relevant records to regulators or law enforcement according to applicable laws.'
          ]
        },
        {
          title: '6. False Positive Appeal and Unfreeze',
          lines: [
            'If your task is blocked by mistake, submit an appeal through the feedback channel with app purpose, ownership or authorization proof, domain ownership proof, and key code explanations.',
            'Appeals are usually reviewed within 1 to 3 business days. After approval, risk tags can be corrected and frozen client_id can be unfrozen by administrators.'
          ]
        },
        {
          title: '7. Updates and Contact',
          lines: [
            'We may update this agreement based on legal, policy, or security requirements and notify users by announcement, dialog, or system notice.',
            'Continued use after update means you accept the revised terms.'
          ]
        }
      ],
      legalReferences:
        'Contact email: 2952299066@qq.com. If you have questions or need compliance appeal support, please contact us by email.',
      acceptButton: 'Agree and Continue',
      rejectButton: 'Decline and Exit'
    },
    'zh-CN': {
      title: '用户使用协议与服务条款',
      effectiveDateLabel: '生效日期',
      effectiveDate: '2026-05-13',
      intro:
        '在你使用本客户端及相关服务前，请完整阅读并充分理解本协议。你点击“同意并继续”或继续使用本服务，即视为你已阅读、理解并接受全部条款。',
      sections: [
        {
          title: '一、适用范围与协议生效',
          lines: [
            '本协议适用于上传、打包、构建、下载、日志查看等全部功能与服务。',
            '若你不同意本协议任一条款，请立即停止使用本服务。'
          ]
        },
        {
          title: '二、合法使用与授权义务',
          lines: [
            '你应确保上传的源码、素材、应用名称、包名、域名等信息真实、合法并已取得必要授权。',
            '你不得提交任何违反法律法规、侵犯第三方权益或危害平台安全的内容。'
          ]
        },
        {
          title: '三、明确禁止的应用类别',
          lines: [
            '严禁制作或分发以下应用：假冒金融理财/贷款、假冒政府或权威机构、假冒客服、赌博博彩类应用。',
            '严禁制作或分发以下应用：传销拉新返利诈骗、钓鱼登录盗号、远程控制滥用、间谍木马、破解盗版、绕过授权分发工具。',
            '严禁制作或分发三无应用商店、仿冒应用市场、诱导下载中心等高风险分发类应用。'
          ]
        },
        {
          title: '四、风控扫描与自动阻断',
          lines: [
            '平台会对应用名称、包名、用途说明、源码关键文件、HTML 文本、外链域名及权限组合进行规则与 AI 合规扫描。',
            '一旦命中高风险规则，平台可立即阻断任务创建或构建执行，并将风险原因记录至合规审核。'
          ]
        },
        {
          title: '五、违规后果',
          lines: [
            '对已确认或高度疑似违规的任务，平台有权执行中止任务、冻结 client_id、限制功能、拒绝构建、终止服务并保留证据。',
            '情节严重的，平台将依法向监管或司法机构提供必要记录。'
          ]
        },
        {
          title: '六、误杀申诉与解冻流程',
          lines: [
            '若你认为被误判，可通过反馈入口提交申诉，并提供用途说明、权属或授权证明、域名归属证明及关键代码说明。',
            '申诉一般在 1-3 个工作日内处理。审核通过后，管理员可纠正风险标记并解除对应 client_id 冻结状态。'
          ]
        },
        {
          title: '七、条款更新与联系方式',
          lines: [
            '平台可根据法律、政策或安全要求更新本条款，并通过公告、弹窗或系统通知发布。',
            '你在条款更新后继续使用服务，视为接受更新后的条款。'
          ]
        }
      ],
      legalReferences:
        '联系邮箱：2952299066@qq.com。如需条款咨询或合规申诉支持，请通过该邮箱联系平台。',
      acceptButton: '同意并继续',
      rejectButton: '拒绝并退出'
    },
    'zh-TW': {
      title: '使用者協議與服務條款',
      effectiveDateLabel: '生效日期',
      effectiveDate: '2026-05-13',
      intro:
        '在你使用本客戶端及相關服務前，請完整閱讀並充分理解本協議。你點擊「同意並繼續」或繼續使用本服務，即視為你已閱讀、理解並接受全部條款。',
      sections: [
        {
          title: '一、適用範圍與協議生效',
          lines: [
            '本協議適用於上傳、打包、構建、下載、日誌查看等全部功能與服務。',
            '若你不同意本協議任一條款，請立即停止使用本服務。'
          ]
        },
        {
          title: '二、合法使用與授權義務',
          lines: [
            '你應確保上傳的原始碼、素材、應用名稱、包名、網域等資訊真實、合法並已取得必要授權。',
            '你不得提交任何違反法律法規、侵犯第三方權益或危害平台安全的內容。'
          ]
        },
        {
          title: '三、明確禁止的應用類別',
          lines: [
            '嚴禁製作或散佈以下應用：假冒金融理財或貸款、假冒政府或權威機構、假冒客服、賭博博彩類應用。',
            '嚴禁製作或散佈以下應用：傳銷拉新返利詐騙、釣魚登入盜號、遠端控制濫用、間諜木馬、破解盜版、繞過授權分發工具。',
            '嚴禁製作或散佈三無應用商店、仿冒應用市場、誘導下載中心等高風險分發類應用。'
          ]
        },
        {
          title: '四、風控掃描與自動阻斷',
          lines: [
            '平台會對應用名稱、包名、用途說明、原始碼關鍵檔案、HTML 文字、外鏈網域及權限組合進行規則與 AI 合規掃描。',
            '一旦命中高風險規則，平台可立即阻斷任務建立或構建執行，並將風險原因記錄至合規審核。'
          ]
        },
        {
          title: '五、違規後果',
          lines: [
            '對已確認或高度疑似違規的任務，平台有權執行中止任務、凍結 client_id、限制功能、拒絕構建、終止服務並保留證據。',
            '情節嚴重者，平台將依法向監管或司法機構提供必要紀錄。'
          ]
        },
        {
          title: '六、誤殺申訴與解凍流程',
          lines: [
            '若你認為被誤判，可透過回饋入口提交申訴，並提供用途說明、權屬或授權證明、網域歸屬證明及關鍵程式碼說明。',
            '申訴通常於 1-3 個工作日內處理。審核通過後，管理員可更正風險標記並解除對應 client_id 凍結狀態。'
          ]
        },
        {
          title: '七、條款更新與聯絡方式',
          lines: [
            '平台可依法律、政策或安全需求更新本條款，並透過公告、彈窗或系統通知發布。',
            '你於條款更新後繼續使用服務，視為接受更新後條款。'
          ]
        }
      ],
      legalReferences:
        '聯絡信箱：2952299066@qq.com。如需條款諮詢或合規申訴支援，請透過該信箱聯絡平台。',
      acceptButton: '同意並繼續',
      rejectButton: '拒絕並退出'
    }
  }
  const complianceNotice = computed(() => {
    const defaultNotice = currentLang.value === 'zh-CN'
      ? complianceNoticeByLang['zh-CN']
      : (currentLang.value === 'zh-TW' ? complianceNoticeByLang['zh-TW'] : complianceNoticeByLang.en)
    const customContent = normalizeComplianceNoticeText(featureFlags.value.compliance_notice_content, 8000)
    if (!customContent) return defaultNotice
    return {
      title: normalizeComplianceNoticeText(featureFlags.value.compliance_notice_title, 160, defaultNotice.title),
      effectiveDateLabel: defaultNotice.effectiveDateLabel,
      effectiveDate: normalizeComplianceNoticeText(featureFlags.value.compliance_notice_effective_date, 32, defaultNotice.effectiveDate),
      intro: '',
      paragraphs: customContent
        .split(/\n{2,}/)
        .map((paragraph) => paragraph.trim())
        .filter((paragraph) => paragraph),
      sections: [],
      legalReferences: '',
      acceptButton: normalizeComplianceNoticeText(featureFlags.value.compliance_notice_accept_button, 80, defaultNotice.acceptButton),
      rejectButton: normalizeComplianceNoticeText(featureFlags.value.compliance_notice_reject_button, 80, defaultNotice.rejectButton)
    }
  })
  const taskComplianceError = computed(() => {
    if (clientFreezeState.value.frozen) {
      return buildClientFrozenMessage(clientFreezeState.value)
    }
    if (updatingTaskId.value) return ''
    if (!taskComplianceAck.value) return t('config.taskComplianceAckRequired')
    return ''
  })

  // Logs
  const showLogs = ref(false)
  const taskLogs = ref([])
  const currentLogTaskId = ref(null)
  const logsContainer = ref(null)
  const taskLogsTotal = ref(0)
  const taskLogsHasMore = ref(false)
  const logsLoading = ref(false)
  const taskLogFetchLines = 220
  const taskLogMaxLineChars = 1400
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

  const normalizeStatusBarColor = (raw) => {
    let value = String(raw || '').trim()
    if (!value) return '#FFFFFF'
    if (value.toLowerCase() === 'transparent') return 'transparent'
    if (/^[0-9a-fA-F]{6}$/.test(value) || /^[0-9a-fA-F]{8}$/.test(value)) {
      value = `#${value}`
    }
    if (/^#[0-9a-fA-F]{3}$/.test(value)) {
      value = `#${value.slice(1).split('').map((item) => item + item).join('')}`
    }
    if (/^#[0-9a-fA-F]{6}$/.test(value) || /^#[0-9a-fA-F]{8}$/.test(value)) {
      return value.toUpperCase()
    }
    return '#FFFFFF'
  }

  const statusBarColorPickerValue = computed(() => {
    const normalized = normalizeStatusBarColor(config.value.status_bar_color)
    if (/^#[0-9A-F]{8}$/.test(normalized)) {
      return `#${normalized.slice(3)}`
    }
    if (/^#[0-9A-F]{6}$/.test(normalized)) {
      return normalized
    }
    return '#FFFFFF'
  })

  const handleStatusBarColorPickerInput = (event) => {
    config.value.status_bar_color = normalizeStatusBarColor(event?.target?.value)
  }

  const normalizeStatusBarColorInput = () => {
    config.value.status_bar_color = normalizeStatusBarColor(config.value.status_bar_color)
  }

  const prohibitedGenerationKeywords = [
    '下载站',
    '下载器',
    '下载工具',
    '下载平台',
    '资源下载',
    '资源解析',
    '资源聚合',
    '聚合下载',
    '采集下载',
    '抓取下载',
    '内容抓取',
    '内容下载',
    '漫画下载',
    '漫画抓取',
    '本子下载',
    '禁漫',
    '禁漫天堂',
    '18comic',
    'jmcomic',
    'jmscraper',
    'jm scraper',
    'download site',
    'download website',
    'download portal',
    'download station',
    'downloader',
    'download app',
    'download tool',
    'content downloader',
    'media downloader',
    'video downloader',
    'comic downloader',
    'manga downloader',
    'scraper downloader',
    'crawler downloader',
    'resource downloader',
    'piracy downloader',
    'adult downloader'
  ]

  const normalizeProhibitedGenerationText = (value) => String(value || '').trim().toLowerCase()
  const compactProhibitedGenerationText = (value) => normalizeProhibitedGenerationText(value).replace(/[\s._-]+/g, '')
  const findProhibitedGenerationKeyword = (...values) => {
    const normalizedValues = values
      .map((value) => normalizeProhibitedGenerationText(value))
      .filter((value) => value)
    if (!normalizedValues.length) return ''
    const compactValues = normalizedValues.map((value) => compactProhibitedGenerationText(value))
    for (const keyword of prohibitedGenerationKeywords) {
      const normalizedKeyword = normalizeProhibitedGenerationText(keyword)
      const compactKeyword = compactProhibitedGenerationText(keyword)
      if (!normalizedKeyword) continue
      const matched = normalizedValues.some((value) => value.includes(normalizedKeyword)) ||
        (compactKeyword && compactValues.some((value) => value.includes(compactKeyword)))
      if (matched) return keyword
    }
    return ''
  }

  const prohibitedGenerationError = computed(() => {
    const keyword = findProhibitedGenerationKeyword(
      config.value.app_name,
      config.value.package_name,
      mode.value === 'web' ? webUrl.value : ''
    )
    if (!keyword) return ''
    return t('config.prohibitedGenerationRule', { keyword })
  })

  const applyQuickGenerateDefaults = () => {
    // 一键生成使用后端默认图标与签名文件，进入时清理用户已上传的内容。
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
      // 后端会在每次创建任务时自动递增版本号。
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

    // 恢复图标预览。
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

    // 文件输入无法恢复，重置原生控件值以保持界面干净。
    if (keystoreInput.value) keystoreInput.value.value = ''
  }

  const enterQuickGenerate = () => {
    if (quickGenerate.value) return
    if (!quickGenerateSupportedModes.has(mode.value) || updatingTaskId.value) return
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
  const isDailyBuildLimitReachedError = (error) => {
    const detail = getErrorDetailPayload(error)
    const data = error?.response?.data
    const sources = [getErrorDetailText(error)]
    if (detail && typeof detail === 'object') {
      sources.push(detail?.reason, detail?.code, detail?.message)
    }
    if (data && typeof data === 'object') {
      sources.push(data?.reason, data?.code, data?.message)
    }
    const sourceText = sources
      .filter((item) => item !== undefined && item !== null)
      .map((item) => String(item).trim().toLowerCase())
      .filter(Boolean)
      .join(' ')
    return (
      sourceText.includes('daily_limit_reached') ||
      sourceText.includes('daily limit reached') ||
      sourceText.includes('daily build limit')
    )
  }
  const showDailyBuildLimitDialog = () => {
    void openConfirmDialog({
      title: '构建次数已达上限',
      message: '当天的构建次数已达上限，如需额外构建请联系作者。',
      confirmText: '我知道了',
      cancelText: '关闭',
      confirmType: 'primary'
    })
  }
  const normalizeFreezeState = (payload = {}) => {
    const freeze = payload?.freeze && typeof payload.freeze === 'object' ? payload.freeze : payload
    const frozen = Boolean(payload?.frozen ?? freeze?.frozen)
    const reason = String(freeze?.reason || '').trim()
    const contact = String(freeze?.contact || '').trim()
    const sourceTaskId = String(freeze?.source_task_id || '').trim()
    const frozenAt = String(freeze?.frozen_at || '').trim()
    const freezeExpiresAt = String(
      payload?.freeze_expires_at || freeze?.freeze_expires_at || freeze?.expires_at || ''
    ).trim()
    const freezeRemainingSeconds = Number(
      payload?.freeze_remaining_seconds || freeze?.freeze_remaining_seconds || freeze?.remaining_seconds || 0
    )
    const freezeSeconds = Number(
      payload?.freeze_seconds || freeze?.freeze_seconds || 0
    )
    const cooldownRemainingSeconds = Number(payload?.cooldown_remaining_seconds || freeze?.cooldown_remaining_seconds || 0)
    const cooldownSeconds = Number(payload?.cooldown_seconds || freeze?.cooldown_seconds || 600)
    return {
      frozen,
      reason,
      contact,
      source_task_id: sourceTaskId,
      frozen_at: frozenAt,
      freeze_expires_at: freezeExpiresAt,
      freeze_remaining_seconds: Number.isFinite(freezeRemainingSeconds) ? Math.max(0, Math.round(freezeRemainingSeconds)) : 0,
      freeze_seconds: Number.isFinite(freezeSeconds) && freezeSeconds > 0 ? Math.round(freezeSeconds) : 600,
      cooldown_remaining_seconds: Number.isFinite(cooldownRemainingSeconds) ? Math.max(0, Math.round(cooldownRemainingSeconds)) : 0,
      cooldown_seconds: Number.isFinite(cooldownSeconds) && cooldownSeconds > 0 ? Math.round(cooldownSeconds) : 600
    }
  }

  const formatFreezeUnfreezeTime = (rawValue) => {
    const text = String(rawValue || '').trim()
    if (!text) return ''
    const parsed = new Date(text)
    if (Number.isNaN(parsed.getTime())) return ''
    const pad = (num) => String(num).padStart(2, '0')
    const year = parsed.getFullYear()
    const month = pad(parsed.getMonth() + 1)
    const day = pad(parsed.getDate())
    const hour = pad(parsed.getHours())
    const minute = pad(parsed.getMinutes())
    const second = pad(parsed.getSeconds())
    return `${year}-${month}-${day} ${hour}:${minute}:${second}`
  }

  const buildClientFrozenMessage = (freezeLike = {}) => {
    const freezeState = normalizeFreezeState(freezeLike)
    const reason = freezeState.reason || t('config.clientFrozenByRiskDefaultReason')
    const unfreezeAt = formatFreezeUnfreezeTime(freezeState.freeze_expires_at) || t('config.clientFrozenByRiskUnknownUnfreezeTime')
    return t('config.clientFrozenByRisk', { reason, unfreezeAt })
  }

  const extractClientFrozenDetail = (error) => {
    const detail = getErrorDetailPayload(error)
    if (detail && typeof detail === 'object') {
      const code = String(detail?.code || '').trim().toLowerCase()
      const message = String(detail?.message || '').trim().toLowerCase()
      if (
        code === 'client_frozen_by_ai_risk' ||
        message.includes('client is frozen by ai risk guard') ||
        message.includes('client is frozen by risk guard')
      ) {
        return normalizeFreezeState(detail)
      }
    }
    const detailText = getErrorDetailText(error)
    if (detailText.includes('client is frozen by ai risk guard') || detailText.includes('client is frozen by risk guard')) {
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
      return buildClientFrozenMessage(freezeDetail)
    }
    const detail = getErrorDetailText(error)
    if (!detail) return ''
    if (detail.includes('compliance confirmation is required')) return t('config.taskComplianceAckRequired')
    if (
      detail.includes('prohibited download/distribution app') ||
      detail.includes('prohibited_downloader') ||
      detail.includes('download site') ||
      detail.includes('downloader')
    ) {
      return t('config.prohibitedGenerationBackendBlocked')
    }
    if (detail.includes('task blocked by policy')) return t('config.marketplaceBlocked')
    if (detail.includes('task is pending admin risk review')) return t('toast.riskReviewPending')
    if (detail.includes('task was rejected by admin risk review')) return t('toast.riskReviewRejected')
    if (
      detail.includes('filename is required for zip-based mode')
      || detail.includes('uploaded zip file not found')
      || detail.includes('zip file not found')
      || detail.includes('zip文件不存在')
    ) {
      return '未检测到可用 ZIP 文件，请重新上传后再试'
    }
    if (
      detail.includes('html_filename is required for html mode')
      || detail.includes('uploaded html file not found')
      || detail.includes('html文件不存在')
    ) {
      return '未检测到可用 HTML 文件，请重新上传后再试'
    }
    if (
      detail.includes('zip format is invalid')
      || detail.includes('failed to inspect zip')
      || detail.includes('index.html was not found in zip')
    ) {
      return '上传的 ZIP 无法识别，请确认项目结构后重试'
    }
    if (
      detail.includes('request failed with status code 422')
      || detail.includes('desktop_port must be')
      || detail.includes('package_name must be')
    ) {
      return '构建参数校验失败，请检查包名、版本号和端口配置'
    }
    if (detail.includes('native android mode is disabled')) {
      return '原生 Android 打包功能已关闭，请联系管理员开启'
    }
    if (detail.includes('request failed with status code 413')) {
      return '上传文件过大，请压缩后重试'
    }
    if (
      detail.includes('request failed with status code 503')
      || detail.includes('service unavailable')
      || detail.includes('admin_unavailable')
    ) {
      return '服务暂时不可用，请稍后重试'
    }
    return ''
  }

  const resolveStartTaskErrorMessage = (error) => {
    const freezeDetail = extractClientFrozenDetail(error)
    if (freezeDetail && freezeDetail.frozen) {
      applyClientFreezeState(freezeDetail)
      return buildClientFrozenMessage(freezeDetail)
    }
    const detail = getErrorDetailText(error)
    if (!detail) return ''
    if (detail.includes('task is pending admin risk review')) return t('toast.riskReviewPending')
    if (detail.includes('task was rejected by admin risk review')) return t('toast.riskReviewRejected')
    if (detail.includes('insufficient_quota') || detail.includes('insufficient quota')) return '构建次数不足，请先购买或兑换构建额度'
    if (
      detail.includes('quota_login_required')
      || detail.includes('quota requires login')
      || detail.includes('login required')
      || detail.includes('login_required')
    ) {
      return '请先登录账号，再使用构建次数'
    }
    if (detail.includes('build_quota_service_unavailable') || detail.includes('build quota service unavailable') || detail.includes('admin_unavailable')) {
      return '构建额度服务暂不可用，请稍后重试'
    }
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
        freeze_expires_at: String(alert?.freeze_expires_at || '').trim(),
        freeze_seconds: Number(alert?.freeze_seconds || 0),
        freeze_remaining_seconds: Number(alert?.freeze_remaining_seconds || 0),
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
      await fetchBuildQuotaContext()
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
      await fetchBuildQuotaContext()
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
    const hasIcon = quickGenerate.value && quickGenerateSupportedModes.has(mode.value) && !updatingTaskId.value
      ? true
      : (appIcon.value || uploadedIcon.value)
    const common =
      config.value.app_name &&
      config.value.package_name &&
      !prohibitedGenerationError.value &&
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
    if (!quickGenerateSupportedModes.has(value) && quickGenerate.value) {
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
  const outputRetentionDays = 3

  const checkDownloadAvailability = async (url) => {
    try {
      const response = await fetch(url, { method: 'HEAD', cache: 'no-store' })
      if (response.ok) return { ok: true }
      if (response.status === 404 || response.status === 410) {
        return { ok: false, message: t('toast.outputExpired', { days: outputRetentionDays }) }
      }
      return { ok: true }
    } catch {
      return { ok: true }
    }
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
    if (artifactType !== 'signed') {
      const availability = await checkDownloadAvailability(url)
      if (!availability.ok) {
        showToast(availability.message, 'error')
        await refreshTasks()
        return
      }
    }
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
  const normalizeTaskReviewStatus = (task) => {
    const directStatus = String(task?.review_status || '').trim().toLowerCase()
    if (directStatus) return directStatus
    const configStatus = String(task?.config?.review_status || '').trim().toLowerCase()
    if (configStatus) return configStatus
    const metaStatus = String(task?.zip_meta?.review_status || '').trim().toLowerCase()
    return metaStatus
  }
  const isRiskReviewReleasedPendingTask = (task) => {
    if (!task || task.status !== 'pending') return false
    const reviewRequired = Boolean(
      task?.review_required
      ?? task?.config?.review_required
      ?? task?.zip_meta?.review_required
    )
    if (!reviewRequired) return false
    return normalizeTaskReviewStatus(task) === 'approved'
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
  const refreshUploadLimitForValidation = async () => {
    try {
      const result = await api.getAdminFeatures({ force: true })
      if (result && Object.prototype.hasOwnProperty.call(result, 'upload_max_size_mb')) {
        featureFlags.value = {
          ...featureFlags.value,
          upload_max_size_mb: normalizeUploadMaxSizeMb(result.upload_max_size_mb)
        }
      }
    } catch {
      // 上传前刷新失败时保留本地缓存，最终仍由后端限制兜底。
    }
  }

  const validateUploadFileSize = async (file) => {
    const fileSize = Number(file?.size)
    if (!Number.isFinite(fileSize) || fileSize <= 0) return true
    await refreshUploadLimitForValidation()
    const maxSizeMb = normalizeUploadMaxSizeMb(featureFlags.value.upload_max_size_mb)
    const maxSizeBytes = maxSizeMb * 1024 * 1024
    if (fileSize <= maxSizeBytes) return true
    showToast(
      t('toast.uploadTooLarge', {
        size: formatFileSize(fileSize),
        limit: `${maxSizeMb} MB`
      }),
      'error'
    )
    return false
  }

  const triggerFileInput = () => fileInput.value?.click?.()
  const handleFileSelect = async (event) => {
    const file = event.target.files[0]
    if (file) {
      const uploaded = await uploadFile(file)
      if (!uploaded && event.target) event.target.value = ''
    }
  }
  const handleDrop = async (event) => {
    isDragging.value = false
    const file = event.dataTransfer.files[0]
    if (file && file.name.endsWith('.zip')) await uploadFile(file)
    else showToast('请上传 ZIP 文件', 'error')
  }
  const uploadFile = async (file) => {
    if (!(await validateUploadFileSize(file))) {
      uploadProgress.value = 0
      return false
    }
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
      return true
    } catch (error) {
      showErrorToast('toast.uploadFailed', error)
      return false
    }
  }

  const handleHtmlSelect = async (event) => {
    const file = event.target.files[0]
    if (!file) return
    if (!(await validateUploadFileSize(file))) {
      if (event.target) event.target.value = ''
      return
    }
    const previewContent = await syncHtmlEditorContent(file)
    const uploaded = await uploadHtml(file, { previewContent, skipSizeCheck: true })
    if (uploaded) htmlEditorDirty.value = false
    else if (event.target) event.target.value = ''
  }
  const handleHtmlDrop = async (event) => {
    isHtmlDragging.value = false
    const file = event.dataTransfer.files[0]
    if (file && /\.(html|htm)$/i.test(file.name)) {
      if (!(await validateUploadFileSize(file))) return
      const previewContent = await syncHtmlEditorContent(file)
      const uploaded = await uploadHtml(file, { previewContent, skipSizeCheck: true })
      if (uploaded) htmlEditorDirty.value = false
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
    if (options.skipSizeCheck !== true && !(await validateUploadFileSize(file))) {
      htmlUploadProgress.value = 0
      return null
    }
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
      if (isDailyBuildLimitReachedError(error)) {
        showDailyBuildLimitDialog()
        await fetchBuildQuotaContext()
        return
      }
      if (mappedMessage) {
        showToast(mappedMessage, 'error')
        const detail = getErrorDetailText(error)
        if (detail.includes('insufficient_quota') || detail.includes('insufficient quota')) {
          openBuildPaymentModal()
        }
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
  const retryTask = async (taskId, options = {}) => {
    const autoStart = Boolean(options?.autoStart)
    try {
      await api.retryTask(taskId)
      showToast(t('toast.taskRetried'), 'success')
      await refreshTasks()
      if (autoStart) {
        const canStartBuild = await requestRewardAdBeforeBuild()
        if (!canStartBuild) return
        await startTaskDirectly(taskId, { notify: false, showRiskReviewingNotice: false })
      }
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
    } else if (taskMode === 'native') {
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
    if (prohibitedGenerationError.value) {
      showToast(prohibitedGenerationError.value, 'error')
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
        showToast(buildClientFrozenMessage(clientFreezeState.value), 'error')
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
      if (mode.value === 'convert' || mode.value === 'web' || mode.value === 'html') {
        normalizeStatusBarColorInput()
      }

      const isQuickGenerate = quickGenerate.value && quickGenerateSupportedModes.has(mode.value) && !updatingTaskId.value

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
          status_bar_color: normalizeStatusBarColor(config.value.status_bar_color),
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
            status_bar_color: normalizeStatusBarColor(config.value.status_bar_color),
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
          showToast(buildClientFrozenMessage(freezeState), 'warning')
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
      if (isDailyBuildLimitReachedError(error)) {
        showDailyBuildLimitDialog()
        await fetchBuildQuotaContext()
        return
      }
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
    if (preserveQuickGenerate && quickGenerate.value && quickGenerateSupportedModes.has(mode.value)) {
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
    taskLogsTotal.value = 0
    taskLogsHasMore.value = false
    logsLoading.value = false
    taskDiagnosis.value = null
    taskDiagnosisLoading.value = false
    taskDiagnosisError.value = ''
  }
  const shouldReplaceTaskLogs = (currentLogs, nextLogs) => {
    if (!Array.isArray(currentLogs) || !Array.isArray(nextLogs)) return true
    if (currentLogs.length !== nextLogs.length) return true
    if (currentLogs.length === 0) return false
    const currentLast = currentLogs[currentLogs.length - 1]
    const nextLast = nextLogs[nextLogs.length - 1]
    if (currentLast !== nextLast) return true
    const currentFirst = currentLogs[0]
    const nextFirst = nextLogs[0]
    return currentFirst !== nextFirst
  }
  const refreshLogs = async () => {
    if (!currentLogTaskId.value || logsLoading.value) return
    logsLoading.value = true
    try {
      const result = await api.getTaskLogs(currentLogTaskId.value, {
        lines: taskLogFetchLines,
        maxLineChars: taskLogMaxLineChars
      })
      const nextLogs = Array.isArray(result?.logs) ? result.logs : []
      const replaced = shouldReplaceTaskLogs(taskLogs.value, nextLogs)
      if (replaced) {
        taskLogs.value = nextLogs
        await nextTick()
        if (logsContainer.value) {
          logsContainer.value.scrollTop = logsContainer.value.scrollHeight
        }
      }
      const totalRaw = Number(result?.total)
      taskLogsTotal.value = Number.isFinite(totalRaw) && totalRaw >= 0 ? totalRaw : nextLogs.length
      taskLogsHasMore.value = Boolean(result?.has_more) || taskLogsTotal.value > nextLogs.length
    } catch {
      taskLogs.value = []
      taskLogsTotal.value = 0
      taskLogsHasMore.value = false
    } finally {
      logsLoading.value = false
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
  const normalizeBuildQuotaContext = (payload) => {
    const data = payload && typeof payload === 'object' ? payload : {}
    const mode = String(data.effective_build_quota_mode || data.build_quota_mode || 'free_unlimited').trim().toLowerCase()
    const effectiveMode = ['free_unlimited', 'free_quota', 'code_only', 'free_plus_code'].includes(mode)
      ? mode
      : 'free_unlimited'
    const remainingRaw = data.remaining_balance
    const consumedRaw = data.consumed_total
    const remainingBalance = remainingRaw === null || remainingRaw === undefined
      ? null
      : Number.parseInt(remainingRaw, 10)
    const consumedTotal = consumedRaw === null || consumedRaw === undefined
      ? null
      : Number.parseInt(consumedRaw, 10)
    return {
      build_code_enabled: Boolean(data.build_code_enabled),
      build_quota_mode: String(data.build_quota_mode || 'free_unlimited').trim().toLowerCase() || 'free_unlimited',
      effective_build_quota_mode: effectiveMode,
      free_build_quota_default: Math.max(0, Number.parseInt(data.free_build_quota_default || 0, 10) || 0),
      quota_require_login: Boolean(data.quota_require_login),
      subject_type: String(data.subject_type || '').trim(),
      subject_id: String(data.subject_id || '').trim(),
      remaining_balance: Number.isFinite(remainingBalance) ? remainingBalance : null,
      consumed_total: Number.isFinite(consumedTotal) ? consumedTotal : null,
      is_unlimited: data.is_unlimited === undefined ? effectiveMode === 'free_unlimited' : Boolean(data.is_unlimited)
    }
  }
  const fetchBuildQuotaContext = async () => {
    try {
      const result = await api.getBuildQuotaContext()
      buildQuotaContext.value = normalizeBuildQuotaContext(result)
    } catch {
      buildQuotaContext.value = normalizeBuildQuotaContext({})
    }
  }
  const redeemCurrentBuildCode = async () => {
    const code = String(buildCodeInput.value || '').trim()
    if (!code) {
      showToast('请输入构建码', 'error')
      return
    }
    if (buildCodeRedeeming.value) return
    buildCodeRedeeming.value = true
    try {
      await api.redeemBuildQuotaCode(code)
      buildCodeInput.value = ''
      await fetchBuildQuotaContext()
      showToast('兑换成功，构建次数已更新', 'success')
    } catch (error) {
      const detail = getErrorDetailText(error)
      if (detail.includes('invalid_code')) {
        showToast('构建码无效，请检查后重试', 'error')
      } else if (detail.includes('subject_redeem_limit_reached')) {
        showToast('该构建码已达当前用户兑换上限', 'error')
      } else if (detail.includes('login_required') || detail.includes('login required')) {
        showToast('请先登录账号，再兑换构建码', 'warning')
      } else if (detail.includes('exhausted')) {
        showToast('该构建码已被兑换完', 'error')
      } else if (detail.includes('expired')) {
        showToast('该构建码已过期', 'error')
      } else if (detail.includes('build_code_disabled')) {
        showToast('当前已关闭构建码模式，系统为完全免费', 'warning')
      } else if (detail.includes('admin_unavailable')) {
        showToast('额度服务暂不可用，请稍后重试', 'error')
      } else {
        showToast('兑换失败，请稍后重试', 'error')
      }
    } finally {
      buildCodeRedeeming.value = false
    }
  }

  const stopBuildPaymentPolling = () => {
    if (buildPaymentPollTimer) {
      window.clearTimeout(buildPaymentPollTimer)
      buildPaymentPollTimer = null
    }
    buildPaymentPolling.value = false
  }

  const fetchBuildPaymentPlans = async () => {
    buildPaymentPlansLoading.value = true
    buildPaymentPlansError.value = ''
    try {
      const result = await api.getBuildPaymentPlans()
      buildPaymentPlans.value = Array.isArray(result?.plans) ? result.plans : []
      buildPaymentAlipayConfigured.value = Boolean(result?.alipay_configured)
    } catch (error) {
      buildPaymentPlans.value = []
      buildPaymentAlipayConfigured.value = false
      buildPaymentPlansError.value = '加载构建额度套餐失败，请稍后重试'
    } finally {
      buildPaymentPlansLoading.value = false
    }
  }

  const openBuildPaymentModal = async () => {
    showBuildPaymentModal.value = true
    if (!buildPaymentPlans.value.length && !buildPaymentPlansLoading.value) {
      await fetchBuildPaymentPlans()
    }
  }

  const closeBuildPaymentModal = () => {
    showBuildPaymentModal.value = false
  }

  const pollBuildPaymentOrder = async (orderNo, round = 0) => {
    const normalizedOrderNo = String(orderNo || '').trim()
    if (!normalizedOrderNo) return
    if (round > 90) {
      buildPaymentPolling.value = false
      showToast('支付结果确认超时，请稍后刷新额度', 'warning')
      return
    }
    buildPaymentPolling.value = true
    try {
      const order = await api.getBuildPaymentOrder(normalizedOrderNo)
      buildPaymentOrder.value = order
      if (String(order?.status || '').toLowerCase() === 'paid') {
        stopBuildPaymentPolling()
        await fetchBuildQuotaContext()
        showToast('支付成功，构建次数已到账', 'success')
        return
      }
    } catch {
      // 轮询失败不立即打断，避免支付宝回调和本地查询存在短暂时间差
    }
    buildPaymentPollTimer = window.setTimeout(() => {
      pollBuildPaymentOrder(normalizedOrderNo, round + 1)
    }, 3000)
  }

  const startAlipayBuildPayment = async (planId) => {
    const normalizedPlanId = String(planId || '').trim()
    if (!normalizedPlanId || buildPaymentCreating.value) return
    if (!isBuildPaymentModeEnabled.value) {
      showToast('当前为免费构建模式，无需购买额度', 'info')
      return
    }
    buildPaymentCreating.value = true
    try {
      const returnUrl = typeof window !== 'undefined' ? window.location.href : ''
      const result = await api.createAlipayBuildPayment(normalizedPlanId, returnUrl)
      buildPaymentOrder.value = result?.order || null
      const paymentUrl = String(result?.payment_url || '').trim()
      if (!paymentUrl) {
        showToast('支付宝支付暂未配置，请联系管理员', 'warning')
        return
      }
      const opened = window.open(paymentUrl, '_blank', 'noopener,noreferrer')
      if (!opened) {
        window.location.href = paymentUrl
      }
      const orderNo = String(result?.order?.order_no || '').trim()
      if (orderNo) {
        stopBuildPaymentPolling()
        pollBuildPaymentOrder(orderNo)
      }
      showToast('已打开支付宝支付页，支付完成后会自动更新额度', 'info')
    } catch (error) {
      const detail = getErrorDetailText(error)
      if (detail.includes('alipay_not_configured') || detail.includes('payment service unavailable')) {
        showToast('支付宝支付暂未配置，请联系管理员', 'warning')
      } else if (detail.includes('free_unlimited')) {
        showToast('当前为免费构建模式，无需购买额度', 'info')
      } else {
        showToast('创建支付订单失败，请稍后重试', 'error')
      }
    } finally {
      buildPaymentCreating.value = false
    }
  }

  const fetchAdminFeatures = async () => {
    try {
      const result = await api.getAdminFeatures()
      featureFlags.value = {
        web_link_to_apk_enabled: Boolean(result?.web_link_to_apk_enabled),
        zip_to_desktop_enabled: Boolean(result?.zip_to_desktop_enabled),
        native_android_packaging_enabled: Boolean(result?.native_android_packaging_enabled),
        rewarded_build_ads_enabled: Boolean(result?.rewarded_build_ads_enabled),
        donation_popup_probability: normalizeDonationPopupProbability(result?.donation_popup_probability),
        donation_popup_message: String(result?.donation_popup_message || '').replace(/\r\n/g, '\n').replace(/\r/g, '\n'),
        compliance_notice_enabled: result?.compliance_notice_enabled === true,
        compliance_notice_title: String(result?.compliance_notice_title || 'User Agreement and Terms of Service'),
        compliance_notice_effective_date: String(result?.compliance_notice_effective_date || '2026-05-13'),
        compliance_notice_content: String(result?.compliance_notice_content || '').replace(/\r\n/g, '\n').replace(/\r/g, '\n'),
        compliance_notice_accept_button: String(result?.compliance_notice_accept_button || 'Agree and Continue'),
        compliance_notice_reject_button: String(result?.compliance_notice_reject_button || 'Decline and Exit'),
        client_login_enabled: result?.client_login_enabled === undefined ? true : Boolean(result?.client_login_enabled),
        client_sms_login_enabled: result?.client_sms_login_enabled === true,
        client_register_enabled: result?.client_register_enabled === undefined ? true : Boolean(result?.client_register_enabled),
        upload_max_size_mb: normalizeUploadMaxSizeMb(result?.upload_max_size_mb),
      }
    } catch {
      featureFlags.value = {
        web_link_to_apk_enabled: false,
        zip_to_desktop_enabled: false,
        native_android_packaging_enabled: false,
        rewarded_build_ads_enabled: false,
        donation_popup_probability: 10,
        donation_popup_message: '',
        compliance_notice_enabled: false,
        compliance_notice_title: 'User Agreement and Terms of Service',
        compliance_notice_effective_date: '2026-05-13',
        compliance_notice_content: '',
        compliance_notice_accept_button: 'Agree and Continue',
        compliance_notice_reject_button: 'Decline and Exit',
        client_login_enabled: true,
        client_sms_login_enabled: false,
        client_register_enabled: true,
        upload_max_size_mb: 200,
      }
    }
    if (!isWebModeEnabled.value && mode.value === 'web') {
      mode.value = 'convert'
    }
    if (!isDesktopModeEnabled.value && mode.value === 'desktop') {
      mode.value = 'convert'
    }
    if (mode.value === 'native') {
      mode.value = 'convert'
    }
    showComplianceNotice.value = complianceNoticeEnabled.value
    const buildQuotaPromise = fetchBuildQuotaContext()
    if (!isAuthEntryEnabled.value) {
      if (showAuthModal.value) {
        closeAuthModal()
      }
      await Promise.allSettled([
        buildQuotaPromise,
        refreshClientFreezeStatus()
      ])
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
    await Promise.allSettled([
      buildQuotaPromise,
      refreshClientFreezeStatus()
    ])
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
    const content = sanitizeFeedbackReplyContent(feedbackContent.value)
    if (!canSubmitInitialFeedback(content, feedbackImages.value)) {
      showToast(t('toast.feedbackEmpty'), 'error')
      return
    }
    feedbackSubmitting.value = true
    try {
      const result = await api.submitFeedback({
        client_id: api.getClientId(),
        content,
        device_info: { ...deviceInfo.value },
        images: feedbackImages.value
      })
      if (saveFeedbackTicket(localStorage, result)) {
        feedbackTickets.value = readFeedbackTickets()
      }
      feedbackContent.value = ''
      feedbackImages.value = []
      showToast(t('toast.feedbackSent'), 'success')
    } catch (error) {
      showToast(t('toast.feedbackFailed'), 'error')
    } finally {
      feedbackSubmitting.value = false
    }
  }

  const addFeedbackMessages = (messages) => {
    const knownMessages = new Map(feedbackMessages.value.map((message) => [`${message.feedback_id}:${message.id}`, message]))
    for (const message of Array.isArray(messages) ? messages : []) {
      const feedbackId = Number.parseInt(message?.feedback_id, 10)
      const messageId = Number.parseInt(message?.id, 10)
      if (feedbackId > 0 && messageId > 0) {
        knownMessages.set(`${feedbackId}:${messageId}`, { ...message, feedback_id: feedbackId, id: messageId })
      }
    }
    feedbackMessages.value = [...knownMessages.values()]
  }

  const loadFeedbackInboxOnce = async () => {
    if (!feedbackInboxGuard.consume()) return
    const tickets = readFeedbackTickets()
    feedbackTickets.value = tickets
    if (!tickets.length) return
    try {
      const messages = enqueueUnreadAdminMessages(await api.fetchFeedbackInbox(tickets))
      addFeedbackMessages(messages)
      feedbackReplyQueue.value = enqueueUnreadAdminMessages([...feedbackReplyQueue.value, ...messages])
    } catch {
      // 启动收件箱失败不显示敏感请求细节，也不会自动重试或轮询。
    }
  }

  const getFeedbackTicket = (feedbackId) => feedbackTickets.value.find((ticket) => ticket.feedback_id === Number.parseInt(feedbackId, 10)) || null

  const markFeedbackMessageRead = async (message) => {
    const ticket = getFeedbackTicket(message?.feedback_id)
    if (!ticket || message?.sender_type !== 'admin') return false
    try {
      await api.acknowledgeFeedbackMessage(ticket.feedback_id, message.id, ticket.access_token)
      return true
    } catch {
      return false
    }
  }

  const removeQueuedFeedbackMessage = (message) => {
    feedbackReplyQueue.value = feedbackReplyQueue.value.filter((item) => !(item.feedback_id === message.feedback_id && item.id === message.id))
  }

  const closeFeedbackReplyPopup = async () => {
    const message = activeFeedbackReply.value
    if (!message) return
    if (shouldDismissFeedbackQueueMessage(await markFeedbackMessageRead(message))) {
      removeQueuedFeedbackMessage(message)
      return
    }
    showToast('已读确认失败，请重试', 'error')
  }

  const openFeedbackConversation = async (feedbackId, message = null) => {
    const nextFeedbackTicketId = Number.parseInt(feedbackId, 10) || null
    if (activeFeedbackTicketId.value !== nextFeedbackTicketId) revokeFeedbackAttachmentPreviews()
    activeFeedbackTicketId.value = nextFeedbackTicketId
    showFeedbackConversation.value = Boolean(activeFeedbackTicketId.value)
    if (message) {
      if (shouldDismissFeedbackQueueMessage(await markFeedbackMessageRead(message))) {
        removeQueuedFeedbackMessage(message)
      } else {
        showToast('已读确认失败，请重试', 'error')
      }
    }
  }

  const closeFeedbackConversation = () => {
    showFeedbackConversation.value = false
    feedbackReplyContent.value = ''
    feedbackReplyImages.value = []
    revokeFeedbackAttachmentPreviews()
  }

  const triggerFeedbackReplyFileSelect = () => {
    feedbackReplyFileInput.value?.click?.()
  }

  const handleFeedbackReplyFiles = (event) => {
    const files = Array.from(event.target?.files || [])
    const selected = selectFeedbackReplyImages(files)
    if (selected.length < files.length) showToast(t('toast.feedbackFileLimit'), 'error')
    feedbackReplyImages.value = selected
    if (event.target) event.target.value = ''
  }

  const attachmentPreviewKey = (messageId, index) => `${messageId}:${index}`
  const revokeFeedbackAttachmentPreviews = () => {
    revokeFeedbackPreviewUrls(feedbackAttachmentPreviews.value)
    feedbackAttachmentPreviews.value = {}
  }
  const attachmentPreviewUrl = (messageId, index) => feedbackAttachmentPreviews.value[attachmentPreviewKey(messageId, index)] || ''
  const setAttachmentPreview = (messageId, index, blob) => {
    const key = attachmentPreviewKey(messageId, index)
    const previousUrl = feedbackAttachmentPreviews.value[key]
    if (previousUrl) URL.revokeObjectURL(previousUrl)
    feedbackAttachmentPreviews.value = { ...feedbackAttachmentPreviews.value, [key]: URL.createObjectURL(blob) }
  }
  const loadFeedbackAttachmentPreview = async (message, index) => {
    const ticket = getFeedbackTicket(message?.feedback_id)
    if (!ticket || attachmentPreviewUrl(message.id, index)) return
    try {
      const blob = await api.downloadFeedbackAttachment(ticket.feedback_id, message.id, index, ticket.access_token)
      setAttachmentPreview(message.id, index, blob)
    } catch {
      showToast(t('toast.feedbackFailed'), 'error')
    }
  }
  const downloadFeedbackAttachment = async (message, index) => {
    const ticket = getFeedbackTicket(message?.feedback_id)
    if (!ticket) return
    try {
      const blob = await api.downloadFeedbackAttachment(ticket.feedback_id, message.id, index, ticket.access_token)
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = `feedback-${message.id}-${index + 1}`
      anchor.click()
      URL.revokeObjectURL(url)
    } catch {
      showToast(t('toast.feedbackFailed'), 'error')
    }
  }

  const submitFeedbackReply = async () => {
    const ticket = activeFeedbackTicket.value
    const content = sanitizeFeedbackReplyContent(feedbackReplyContent.value)
    if (!ticket || (!content && !feedbackReplyImages.value.length)) return
    feedbackReplySubmitting.value = true
    try {
      const result = await api.replyToFeedback(ticket.feedback_id, {
        access_token: ticket.access_token,
        content,
        images: feedbackReplyImages.value
      })
      addFeedbackMessages([{ ...result, feedback_id: ticket.feedback_id, sender_type: 'client' }])
      feedbackReplyContent.value = ''
      feedbackReplyImages.value = []
      const currentAdminMessage = activeFeedbackReply.value
      if (currentAdminMessage?.feedback_id === ticket.feedback_id) {
        if (shouldDismissFeedbackQueueMessage(await markFeedbackMessageRead(currentAdminMessage))) {
          removeQueuedFeedbackMessage(currentAdminMessage)
        } else {
          showToast('已读确认失败，请重试', 'error')
        }
      }
    } catch {
      showToast(t('toast.feedbackFailed'), 'error')
    } finally {
      feedbackReplySubmitting.value = false
    }
  }

  const formatFeedbackMessageText = (message) => selectAdminMessageText(message?.content_i18n, currentLang.value) || String(message?.content || '')

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
  const shouldAutoShowDonation = () => {
    const probabilityPercent = donationPopupProbability.value
    if (probabilityPercent <= 0) return false
    if (probabilityPercent >= 100) return true
    return Math.random() < (probabilityPercent / 100)
  }
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
    appBootLoading.value = true
    try {
      updateMobileShell()
      applyTheme(currentTheme.value)
      // 首次加载时应用保存的语言到 html[lang]，便于辅助技术发音
      applyDocumentLang(currentLang.value)
      document.addEventListener('click', handleClickOutside)
      document.addEventListener('visibilitychange', handleDocumentVisibilityChange)
      document.addEventListener('keydown', handleGlobalEscape)
      window.addEventListener('resize', updateMobileShell)
      window.addEventListener('pagehide', releaseDesktopOutputsOnPageExit)
      window.addEventListener('beforeunload', releaseDesktopOutputsOnPageExit)
      startDesktopOutputHeartbeat()
      const githubCallbackResult = consumeGithubCallbackHash()
      const [
        authReadyResult
      ] = await Promise.allSettled([
        syncAuthUser({ silent: true }),
        fetchAdminFeatures(),
        refreshTasks(),
        fetchAnnouncements(),
        loadSystemInfo(),
        loadFeedbackInboxOnce()
      ])
      const authReady = authReadyResult.status === 'fulfilled' && Boolean(authReadyResult.value)
      if (githubCallbackResult.handled) {
        if (githubCallbackResult.success && authReady) {
          showToast(t('auth.githubLoginSuccess'), 'success')
        } else if (githubCallbackResult.error) {
          showToast(resolveAuthErrorMessage(githubCallbackResult.error), 'error')
        }
      }
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
    } finally {
      appBootLoading.value = false
    }
  })

  onUnmounted(() => {
    stopPolling()
    stopDiagnosisPolling()
    stopBuildPaymentPolling()
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
    revokeFeedbackAttachmentPreviews()
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
    appBootLoading,
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
    buildQuotaContext,
    buildCodeInput,
    buildCodeRedeeming,
    isBuildQuotaUnlimited,
    isBuildPaymentModeEnabled,
    buildPaymentPlans,
    buildPaymentPlansLoading,
    buildPaymentPlansError,
    buildPaymentAlipayConfigured,
    showBuildPaymentModal,
    buildPaymentCreating,
    buildPaymentPolling,
    buildPaymentOrder,
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
    openFirstTaskGuide,
    handleModeChange,
    statusBarColorPickerValue,
    handleStatusBarColorPickerInput,
    normalizeStatusBarColorInput,
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
    fetchBuildQuotaContext,
    redeemCurrentBuildCode,
    fetchBuildPaymentPlans,
    openBuildPaymentModal,
    closeBuildPaymentModal,
    startAlipayBuildPayment,
    announcements,
    deviceInfo,
    feedbackContent,
    feedbackImages,
    feedbackFileInput,
    feedbackSubmitting,
    feedbackTickets,
    feedbackMessages,
    feedbackReplyQueue,
    activeFeedbackReply,
    activeFeedbackTicket,
    activeFeedbackConversationMessages,
    showFeedbackConversation,
    feedbackReplyContent,
    feedbackReplyImages,
    feedbackReplyFileInput,
    feedbackReplySubmitting,
    attachmentPreviewUrl,
    formatFeedbackMessageText,
    showDonation,
    donationHideChecked,
    donationAutoDisabled,
    donationDialogPrimaryText,
    donationDialogSecondaryText,
    showComplianceNotice,
    taskComplianceAck,
    taskComplianceError,
    complianceNotice,
    previousVersionName,
    showLogs,
    taskLogs,
    taskLogsTotal,
    taskLogsHasMore,
    logsLoading,
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
    prohibitedGenerationError,
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
    isRiskReviewReleasedPendingTask,
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
    closeFeedbackReplyPopup,
    openFeedbackConversation,
    closeFeedbackConversation,
    triggerFeedbackReplyFileSelect,
    handleFeedbackReplyFiles,
    submitFeedbackReply,
    loadFeedbackAttachmentPreview,
    downloadFeedbackAttachment,
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
