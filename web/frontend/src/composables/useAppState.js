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
    if (count < 10000) return `${(count / 1000).toFixed(1).replace(/\\.0$/, '')}k`
    if (count < 1000000) return `${Math.round(count / 1000)}k`
    return `${(count / 1000000).toFixed(1).replace(/\\.0$/, '')}M`
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

  const changeLanguage = (lang) => {
    currentLang.value = lang
    saveLanguage(lang)
    i18n.value = createI18n(lang)
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
    zip_to_desktop_enabled: false
  })
  const isWebModeEnabled = computed(() => Boolean(featureFlags.value.web_link_to_apk_enabled))
  const isDesktopModeEnabled = computed(() => Boolean(featureFlags.value.zip_to_desktop_enabled))
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
  const previousVersionName = ref('')

  const complianceNoticeByLang = {
    en: {
      title: 'User Compliance Notice and Disclaimer',
      effectiveDateLabel: 'Effective date',
      effectiveDate: '2026-03-01',
      intro:
        'This platform only provides web packaging and app build services. You must read and agree before using it.',
      sections: [
        {
          title: 'Prohibited Uses',
          lines: [
            'Do not create or distribute illegal information.',
            'Do not create or distribute obscene, pornographic, vulgar, violent, or terror-related content.',
            'Do not engage in phishing, fraud, impersonation, or social-engineering scams.',
            'Do not use this platform for gambling or betting promotion.',
            'Do not infringe copyright, trademark, patent, privacy, portrait, or reputation rights.',
            'Do not create, spread, or host malware, trojans, backdoors, ransomware, or attack scripts.'
          ]
        },
        {
          title: 'User Responsibility',
          lines: [
            'You are solely responsible for all uploaded, generated, and distributed content.',
            'You must ensure you have lawful rights and authorization for all materials you use.'
          ]
        },
        {
          title: 'Platform Rights',
          lines: [
            'For suspected violations, the platform may block tasks, remove content, suspend service, and preserve evidence.',
            'The platform may report and cooperate with regulators or law-enforcement agencies as required by law.'
          ]
        },
        {
          title: 'Compensation',
          lines: [
            'If your actions cause claims, penalties, or losses to the platform, you shall bear full liability and compensation.'
          ]
        }
      ],
      legalReferences:
        'Applicable laws include the Cybersecurity Law of the PRC and the Anti-Telecom and Online Fraud Law of the PRC.',
      acceptButton: 'Agree and Continue',
      rejectButton: 'Decline and Exit'
    },
    'zh-CN': {
      title: '用户合规使用与免责告知',
      effectiveDateLabel: '生效日期',
      effectiveDate: '2026-03-01',
      intro: '本平台仅提供网页打包与应用构建技术服务。您须阅读并同意本告知后方可继续使用。',
      sections: [
        {
          title: '禁止用途',
          lines: [
            '禁止制作、发布、传播违法信息。',
            '禁止制作、发布、传播低俗、色情、暴力、恐怖相关内容。',
            '禁止实施诈骗、钓鱼、仿冒或社会工程攻击行为。',
            '禁止用于赌博、博彩或相关引流推广。',
            '禁止侵犯著作权、商标权、专利权、隐私权、肖像权、名誉权等合法权益。',
            '禁止制作、传播、托管恶意软件、木马、后门、勒索程序、攻击脚本等。'
          ]
        },
        {
          title: '用户责任',
          lines: [
            '您对上传、生成、分发、传播的全部内容承担完整法律责任。',
            '您应保证对所使用素材享有合法权利或已获得有效授权。'
          ]
        },
        {
          title: '平台处置权',
          lines: [
            '对疑似违规行为，平台有权拦截任务、下架内容、限制服务并保全证据。',
            '平台可依法向监管与司法机关报告并配合调查。'
          ]
        },
        {
          title: '赔偿责任',
          lines: ['如因您的行为导致平台遭受索赔、处罚或损失，您应承担全部责任并赔偿。']
        }
      ],
      legalReferences: '相关法律包括《中华人民共和国网络安全法》《中华人民共和国反电信网络诈骗法》等。',
      acceptButton: '同意并继续',
      rejectButton: '拒绝并退出'
    },
    'zh-TW': {
      title: '使用者合規與免責告知',
      effectiveDateLabel: '生效日期',
      effectiveDate: '2026-03-01',
      intro: '本平台僅提供網頁封裝與應用建置技術服務。您須閱讀並同意本告知後方可繼續使用。',
      sections: [
        {
          title: '禁止用途',
          lines: [
            '禁止製作、發布、傳播違法資訊。',
            '禁止製作、發布、傳播低俗、色情、暴力、恐怖相關內容。',
            '禁止從事詐騙、釣魚、仿冒或社交工程攻擊行為。',
            '禁止用於賭博、博彩或相關導流推廣。',
            '禁止侵犯著作權、商標權、專利權、隱私權、肖像權、名譽權等合法權益。',
            '禁止製作、傳播、託管惡意軟體、木馬、後門、勒索程式、攻擊腳本等。'
          ]
        },
        {
          title: '使用者責任',
          lines: [
            '您對上傳、生成、散布、傳播的全部內容承擔完整法律責任。',
            '您應確保對使用素材享有合法權利或已取得有效授權。'
          ]
        },
        {
          title: '平台處置權',
          lines: [
            '對疑似違規行為，平台有權攔截任務、下架內容、限制服務並保全證據。',
            '平台可依法向監管與司法機關通報並配合調查。'
          ]
        },
        {
          title: '賠償責任',
          lines: ['如因您的行為導致平台遭受索賠、處罰或損失，您應承擔全部責任並賠償。']
        }
      ],
      legalReferences: '相關法律包括《中華人民共和國網路安全法》《中華人民共和國反電信網路詐騙法》等。',
      acceptButton: '同意並繼續',
      rejectButton: '拒絕並離開'
    }
  }
  const complianceNotice = computed(() => {
    if (currentLang.value === 'zh-CN') return complianceNoticeByLang['zh-CN']
    if (currentLang.value === 'zh-TW') return complianceNoticeByLang['zh-TW']
    return complianceNoticeByLang.en
  })

  // Logs
  const showLogs = ref(false)
  const taskLogs = ref([])
  const currentLogTaskId = ref(null)
  const logsContainer = ref(null)

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
    if (mode.value === 'web' && !isWebModeEnabled.value) {
      return false
    }
    if (mode.value === 'desktop' && !isDesktopModeEnabled.value) {
      return false
    }
    const shouldCheckKeystore = !isKeystoreUploaded.value
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

  const consumeDesktopTaskLocally = (taskId, message) => {
    const task = tasks.value.find((item) => item.id === taskId)
    if (!task || String(task.mode || '') !== 'desktop') return
    task.output_filename = null
    task.download_url = null
    if (message) {
      task.message = message
    }
  }

  const downloadTaskArtifact = async (taskId, artifactType = 'apk') => {
    const task = tasks.value.find((item) => item.id === taskId)
    const isDesktopArtifact = artifactType !== 'signed' && String(task?.mode || '') === 'desktop'
    const url = artifactType === 'signed' ? getKeystoreUrl(taskId) : getDownloadUrl(taskId)
    closeDownloadMenu()
    if (!url) return

    const triggerDownload = () => {
      if (isDesktopArtifact) {
        consumeDesktopTaskLocally(taskId, 'EXE 下载已开始，仅可下载一次，下载后服务器将自动删除该安装包')
      }
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
      showToast(t('toast.uploadFailed') + ': ' + (error.response?.data?.detail || error.message), 'error')
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
      showToast(t('toast.uploadFailed') + ': ' + (error.response?.data?.detail || error.message), 'error')
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
      showToast(keystoreUploadError.value + ': ' + (error.response?.data?.detail || error.message), 'error')
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
        showToast('图标设置成功', 'success')
      } catch (error) {
        showToast('图标上传失败: ' + (error.response?.data?.detail || error.message), 'error')
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

  const startTask = async (taskId) => {
    try {
      await api.startTask(taskId)
      showToast(t('toast.taskStarted'), 'success')
      await refreshTasks()
      startPolling()
    } catch (error) {
      showToast('启动失败: ' + (error.response?.data?.detail || error.message), 'error')
    }
  }
  const retryTask = async (taskId) => {
    try {
      await api.retryTask(taskId)
      showToast(t('toast.taskRetried'), 'success')
      await refreshTasks()
    } catch (error) {
      showToast('重试失败: ' + (error.response?.data?.detail || error.message), 'error')
    }
  }
  const cancelTask = async (taskId) => {
    if (!confirm('确定要取消这个任务吗？')) return
    try {
      await api.cancelTask(taskId)
      showToast('任务已取消', 'success')
      await refreshTasks()
    } catch (error) {
      showToast('取消失败: ' + (error.response?.data?.detail || error.message), 'error')
    }
  }
  const deleteTask = async (taskId) => {
    if (!confirm('确定要删除这个任务吗？')) return
    try {
      await api.deleteTask(taskId)
      showToast(t('toast.taskDeleted'), 'success')
      await refreshTasks()
    } catch (error) {
      showToast('删除失败: ' + (error.response?.data?.detail || error.message), 'error')
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
    if (!canCreateTask.value) return
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
        try {
          await api.startTask(created.id)
          await refreshTasks()
          startPolling()
        } catch (error) {
          showToast('启动失败: ' + (error.response?.data?.detail || error.message), 'error')
        }
      }
      resetForm({ preserveQuickGenerate: isQuickGenerate })
      await refreshTasks()
    } catch (error) {
      showToast('操作失败: ' + (error.response?.data?.detail || error.message), 'error')
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
    previousVersionName.value = ''
    config.value = {
      app_name: '',
      package_name: '',
      version_name: '1.0.0',
      version_code: 1,
      output_format: 'apk',
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
  const viewLogs = async (taskId) => {
    currentLogTaskId.value = taskId
    showLogs.value = true
    await refreshLogs()
  }
  const closeLogs = () => {
    showLogs.value = false
    currentLogTaskId.value = null
    taskLogs.value = []
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
  }

  // Settings
  const openSettings = () => {
    showSettings.value = true
  }

  const closeSettings = () => (showSettings.value = false)
  const fetchAdminFeatures = async () => {
    try {
      const result = await api.getAdminFeatures()
      featureFlags.value = {
        web_link_to_apk_enabled: Boolean(result?.web_link_to_apk_enabled),
        zip_to_desktop_enabled: Boolean(result?.zip_to_desktop_enabled)
      }
    } catch {
      featureFlags.value = {
        web_link_to_apk_enabled: false,
        zip_to_desktop_enabled: false
      }
    }
    if (!isWebModeEnabled.value && mode.value === 'web') {
      mode.value = 'convert'
    }
    if (!isDesktopModeEnabled.value && mode.value === 'desktop') {
      mode.value = 'convert'
    }
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

  onMounted(async () => {
    updateMobileShell()
    applyTheme(currentTheme.value)
    showComplianceNotice.value = true
    document.addEventListener('click', handleClickOutside)
    document.addEventListener('visibilitychange', handleDocumentVisibilityChange)
    window.addEventListener('resize', updateMobileShell)
    window.addEventListener('pagehide', releaseDesktopOutputsOnPageExit)
    window.addEventListener('beforeunload', releaseDesktopOutputsOnPageExit)
    startDesktopOutputHeartbeat()
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
    document.removeEventListener('click', handleClickOutside)
    document.removeEventListener('visibilitychange', handleDocumentVisibilityChange)
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
    mode,
    isWebModeEnabled,
    isDesktopModeEnabled,
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
    complianceNotice,
    previousVersionName,
    showLogs,
    taskLogs,
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
