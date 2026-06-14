import axios from 'axios'
import { getSavedLanguage } from '../i18n'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000
})
// 上传类请求不设置超时时间，避免大文件中途被断开
const uploadRequestTimeoutMs = 0

const authTokenStorageKey = 'apk_builder_auth_token'

export const getAuthToken = () => {
  if (typeof window === 'undefined') return ''
  return localStorage.getItem(authTokenStorageKey) || ''
}

export const setAuthToken = (token) => {
  if (typeof window === 'undefined') return
  const normalizedToken = String(token || '').trim()
  if (!normalizedToken) {
    localStorage.removeItem(authTokenStorageKey)
    return
  }
  localStorage.setItem(authTokenStorageKey, normalizedToken)
}

export const clearAuthToken = () => {
  if (typeof window === 'undefined') return
  localStorage.removeItem(authTokenStorageKey)
}

// 请求拦截器：自动为所有请求附加 Bearer Token
api.interceptors.request.use((config) => {
  const token = getAuthToken()
  if (token) {
    if (!config.headers) {
      config.headers = {}
    }
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 获取当前客户端标识，优先使用桌面端注入的 clientId，否则从本地存储读取或生成新的
export const getClientId = () => {
  if (window.appClient?.clientId) {
    return window.appClient.clientId
  }
  let clientId = localStorage.getItem('apk_builder_client_id')
  if (!clientId) {
    clientId = 'client_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9)
    localStorage.setItem('apk_builder_client_id', clientId)
  }
  return clientId
}

// 注册账号，成功后自动保存登录令牌
export const registerAccount = async ({ email, password, clientId } = {}) => {
  const payload = {
    email: String(email || '').trim(),
    password: String(password || ''),
    client_id: clientId || getClientId()
  }
  const response = await api.post('/auth/register', payload)
  if (response?.data?.token) {
    setAuthToken(response.data.token)
  }
  return response.data
}

// 登录账号，成功后自动保存登录令牌
export const loginAccount = async ({ email, password, clientId } = {}) => {
  const payload = {
    email: String(email || '').trim(),
    password: String(password || ''),
    client_id: clientId || getClientId()
  }
  const response = await api.post('/auth/login', payload)
  if (response?.data?.token) {
    setAuthToken(response.data.token)
  }
  return response.data
}

// 发送短信验证码
export const sendSmsLoginCode = async ({ phone, clientId } = {}) => {
  const payload = {
    phone: String(phone || '').trim(),
    client_id: clientId || getClientId()
  }
  const response = await api.post('/auth/sms/send-code', payload)
  return response.data
}

// 短信验证码登录，成功后自动保存登录令牌
export const loginBySmsCode = async ({ phone, code, clientId } = {}) => {
  const payload = {
    phone: String(phone || '').trim(),
    code: String(code || '').trim(),
    client_id: clientId || getClientId()
  }
  const response = await api.post('/auth/sms/login', payload)
  if (response?.data?.token) {
    setAuthToken(response.data.token)
  }
  return response.data
}

// 获取当前登录用户信息
export const getAuthMe = async (clientId) => {
  const response = await api.get('/auth/me', {
    params: { client_id: clientId || getClientId() }
  })
  return response.data
}

// 退出登录，无论后端是否成功都清除本地令牌
export const logoutAccount = async () => {
  try {
    const response = await api.post('/auth/logout')
    return response.data
  } finally {
    clearAuthToken()
  }
}

// 获取 GitHub OAuth 登录授权地址
export const getGithubAuthAuthorize = async ({ clientId, returnUrl } = {}) => {
  const normalizedClientId = clientId || getClientId()
  const normalizedReturnUrl = String(returnUrl || '').trim()
  const response = await api.get('/auth/github/login', {
    params: {
      client_id: normalizedClientId,
      return_url: normalizedReturnUrl || undefined
    }
  })
  return response.data
}

// 上传 APK/ZIP 等主文件，支持进度回调
export const uploadFile = async (file, onProgress) => {
  const clientId = getClientId()
  const formData = new FormData()
  formData.append('file', file)
  
  const response = await api.post('/upload', formData, {
    params: { client_id: clientId },
    headers: {
      'Content-Type': 'multipart/form-data'
    },
    timeout: uploadRequestTimeoutMs,
    onUploadProgress: (progressEvent) => {
      if (onProgress) {
        const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total)
        onProgress(percent)
      }
    }
  })
  return response.data
}

// 上传应用图标文件（PNG/JPG 等），返回服务端保存后的文件名
export const uploadIcon = async (file) => {
  const formData = new FormData()
  formData.append('file', file)
  
  const response = await api.post('/upload-icon', formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  })
  return response.data
}

// 上传 HTML/ZIP 资源包，用于 Web 转 APK 模式
export const uploadHtml = async (file, onProgress) => {
  const clientId = getClientId()
  const formData = new FormData()
  formData.append('file', file)

  const response = await api.post('/upload-html', formData, {
    params: { client_id: clientId },
    headers: {
      'Content-Type': 'multipart/form-data'
    },
    timeout: uploadRequestTimeoutMs,
    onUploadProgress: (progressEvent) => {
      if (onProgress) {
        const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total)
        onProgress(percent)
      }
    }
  })
  return response.data
}


// 扫描 HTML 资源包内的外链 CDN 资源，用于本地化下载
export const scanExternalLinks = async (payload) => {
  const response = await api.post('/external-links/scan', payload || {})
  return response.data
}

// 上传签名证书文件（.jks / .keystore）
export const uploadKeystore = async (file) => {
  const formData = new FormData()
  formData.append('file', file)

  const response = await api.post('/upload-keystore', formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  })
  return response.data
}

// 探测目标网址信息（标题、图标等），用于 URL 转 APK 模式
export const probeUrl = async (url) => {
  const response = await api.post('/url-probe', { url, client_id: getClientId() })
  return response.data
}

// 创建构建任务
// taskData: { filename, icon_filename, config, reuse_keystore_from }
export const createTask = async (taskData) => {
  const clientId = getClientId()
  const response = await api.post('/tasks', { ...taskData, client_id: clientId })
  return response.data
}

// 获取当前客户端的所有任务列表
export const getTasks = async () => {
  const clientId = getClientId()
  const response = await api.get('/tasks', { params: { client_id: clientId } })
  return response.data
}

// 获取指定任务的详情
export const getTask = async (taskId) => {
  const clientId = getClientId()
  const response = await api.get(`/tasks/${taskId}`, { params: { client_id: clientId } })
  return response.data
}

// 删除指定任务
export const deleteTask = async (taskId) => {
  const clientId = getClientId()
  const response = await api.delete(`/tasks/${taskId}`, { params: { client_id: clientId } })
  return response.data
}

// 取消所有正在运行中的任务
export const cancelRunningTasks = async () => {
  const clientId = getClientId()
  const response = await api.post('/tasks/cancel-running', { client_id: clientId })
  return response.data
}

// 启动指定任务开始构建
export const startTask = async (taskId) => {
  const clientId = getClientId()
  const response = await api.post(`/tasks/${taskId}/start`, null, { params: { client_id: clientId } })
  return response.data
}

// 重试失败的任务
export const retryTask = async (taskId) => {
  const clientId = getClientId()
  const response = await api.post(`/tasks/${taskId}/retry`, null, { params: { client_id: clientId } })
  return response.data
}

// 取消进行中的任务
export const cancelTask = async (taskId) => {
  const clientId = getClientId()
  const response = await api.post(`/tasks/${taskId}/cancel`, { client_id: clientId })
  return response.data
}

// 更新任务配置（例如重新编辑后保存）
export const updateTask = async (taskId, updateData) => {
  const clientId = getClientId()
  const response = await api.put(`/tasks/${taskId}`, { ...updateData, client_id: clientId })
  return response.data
}

// 获取指定任务的运行日志
export const getTaskLogs = async (taskId, options = {}) => {
  const clientId = getClientId()
  const isLegacyNumber = typeof options === 'number'
  const lines = isLegacyNumber
    ? options
    : Number.isFinite(Number(options?.lines)) ? Number(options.lines) : 100
  const maxLineChars = isLegacyNumber
    ? 1400
    : Number.isFinite(Number(options?.maxLineChars)) ? Number(options.maxLineChars) : 1400
  const response = await api.get(`/tasks/${taskId}/logs`, {
    params: { lines, max_line_chars: maxLineChars, client_id: clientId }
  })
  return response.data
}

// 获取任务失败智能诊断结果
export const getTaskDiagnosis = async (taskId, refresh = false) => {
  const clientId = getClientId()
  const lang = getSavedLanguage()
  const response = await api.get(`/tasks/${taskId}/diagnosis`, {
    params: { client_id: clientId, refresh: Boolean(refresh), lang }
  })
  return response.data
}

// 手动触发一次失败日志重诊断
export const rerunTaskDiagnosis = async (taskId) => {
  const clientId = getClientId()
  const lang = getSavedLanguage()
  const response = await api.post(`/tasks/${taskId}/diagnosis`, { client_id: clientId, lang })
  return response.data
}

// 构造任务产物的下载地址
export const getDownloadUrl = (taskId) => {
  const clientId = getClientId()
  return `/api/download/${taskId}?client_id=${encodeURIComponent(clientId)}`
}

// 通知后端释放桌面端已导出的产物引用（用于桌面端关闭前清理）
export const releaseDesktopOutputs = async () => {
  const clientId = getClientId()
  const response = await api.post('/tasks/desktop-output/release', null, {
    params: { client_id: clientId }
  })
  return response.data
}

// 桌面端退出前通过 beacon 发送产物释放通知，保证在页面卸载时仍能送达
export const sendReleaseDesktopOutputsBeacon = () => {
  const clientId = getClientId()
  const url = `/api/tasks/desktop-output/release?client_id=${encodeURIComponent(clientId)}`
  if (typeof navigator !== 'undefined' && typeof navigator.sendBeacon === 'function') {
    try {
      return navigator.sendBeacon(url, new Blob([], { type: 'text/plain;charset=UTF-8' }))
    } catch (error) {
      // sendBeacon 调用失败时降级使用 keepalive fetch
    }
  }
  if (typeof fetch === 'function') {
    fetch(url, {
      method: 'POST',
      keepalive: true,
      credentials: 'same-origin'
    }).catch(() => {})
  }
  return true
}

// 构造签名证书下载地址
export const getKeystoreUrl = (taskId) => {
  const clientId = getClientId()
  return `/api/keystore/${taskId}?client_id=${encodeURIComponent(clientId)}`
}

// 构造图标文件访问地址
export const getIconUrl = (taskId) => {
  const clientId = getClientId()
  return `/api/icon/${taskId}?client_id=${encodeURIComponent(clientId)}`
}

// 获取构建队列整体状态（排队数、运行中等）
export const getQueueStatus = async () => {
  const response = await api.get('/queue/status')
  return response.data
}

// 获取构建环境准备状态
export const getEnvStatus = async () => {
  try {
    const response = await api.get('/env/status')
    return response.data
  } catch (error) {
    if (error.response && error.response.status === 404) {
      const response = await axios.get('/env/status')
      return response.data
    }
    throw error
  }
}

// 触发构建环境准备（JDK/Node/Android SDK 等工具链）
export const prepareEnv = async (force = false) => {
  try {
    const response = await api.post('/env/prepare', { force })
    return response.data
  } catch (error) {
    if (error.response && error.response.status === 405) {
      const response = await api.get('/env/prepare', { params: { force } })
      return response.data
    }
    if (error.response && error.response.status === 404) {
      try {
        const response = await axios.post('/env/prepare', { force })
        return response.data
      } catch (innerError) {
        if (innerError.response && innerError.response.status === 405) {
          const response = await axios.get('/env/prepare', { params: { force } })
          return response.data
        }
      }
    }
    throw error
  }
}

// 获取构建环境的路径与代理配置
export const getEnvConfig = async () => {
  try {
    const response = await api.get('/env/config')
    return response.data
  } catch (error) {
    if (error.response && error.response.status === 404) {
      const response = await axios.get('/env/config')
      return response.data
    }
    throw error
  }
}

// 保存构建环境的路径与代理配置
export const setEnvConfig = async (
  toolchainRoot,
  migrate = false,
  npmRegistry = '',
  npmProxy = '',
  npmHttpsProxy = '',
  dataRoot = '',
  nodePath = '',
  jdkPath = '',
  androidPath = '',
  pythonPath = ''
) => {
  const payload = {
    toolchain_root: toolchainRoot,
    migrate,
    npm_registry: npmRegistry,
    npm_proxy: npmProxy,
    npm_https_proxy: npmHttpsProxy,
    data_root: dataRoot,
    node_path: nodePath,
    jdk_path: jdkPath,
    android_path: androidPath,
    python_path: pythonPath
  }
  try {
    const response = await api.post('/env/config', payload)
    return response.data
  } catch (error) {
    if (error.response && error.response.status === 404) {
      const response = await axios.post('/env/config', payload)
      return response.data
    }
    throw error
  }
}

// 获取管理端下发的公告列表
export const getAdminAnnouncements = async () => {
  const response = await api.get('/adminhub/announcements')
  return response.data
}

// 获取管理端下发的功能开关配置
export const getAdminFeatures = async (options = {}) => {
  const response = await api.get('/adminhub/features', {
    params: {
      client_id: getClientId(),
      force: options.force === true ? true : undefined
    }
  })
  return response.data
}

// 获取当前客户端的构建额度上下文
export const getBuildQuotaContext = async () => {
  const response = await api.get('/adminhub/build-quota', {
    params: { client_id: getClientId() }
  })
  return response.data
}

// 兑换构建码，成功后返回最新剩余次数
export const redeemBuildQuotaCode = async (code, idempotencyKey = '') => {
  const payload = {
    client_id: getClientId(),
    code: String(code || '').trim(),
    idempotency_key: String(idempotencyKey || '').trim() || undefined
  }
  const response = await api.post('/build-quota/redeem', payload)
  return response.data
}

// 获取支付宝构建额度套餐
export const getBuildPaymentPlans = async () => {
  const response = await api.get('/payments/plans', {
    params: { client_id: getClientId() }
  })
  return response.data
}

// 创建支付宝构建额度支付订单
export const createAlipayBuildPayment = async (planId, returnUrl = '') => {
  const response = await api.post('/payments/alipay/create', {
    client_id: getClientId(),
    plan_id: String(planId || ''),
    return_url: returnUrl
  })
  return response.data
}

// 查询构建额度支付订单
export const getBuildPaymentOrder = async (orderNo) => {
  const response = await api.get(`/payments/orders/${encodeURIComponent(orderNo)}`, {
    params: { client_id: getClientId() }
  })
  return response.data
}

// 查询当前客户端是否处于 AI 风险冻结状态
export const getClientFreezeStatus = async (clientId) => {
  const response = await api.get('/client-freeze/status', {
    params: { client_id: clientId || getClientId() }
  })
  return response.data
}

// 检查当前客户端是否存在新版本
export const checkUpdate = async (version) => {
  const response = await api.get('/adminhub/update-check', { params: { version } })
  return response.data
}

// 获取本地系统信息（操作系统、架构等）
export const getSystemInfo = async () => {
  const response = await api.get('/system/info')
  return response.data
}

// 获取当前应用版本号
export const getAppVersion = async () => {
  const response = await api.get('/app/version')
  return response.data
}

// 提交用户反馈，支持携带截图
export const submitFeedback = async (payload) => {
  const formData = new FormData()
  formData.append('client_id', payload.client_id)
  formData.append('content', payload.content)
  formData.append('device_info', JSON.stringify(payload.device_info || {}))
  if (payload.images && payload.images.length) {
    payload.images.forEach((file) => formData.append('images', file))
  }
  const response = await api.post('/adminhub/feedback', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
  return response.data
}

// 获取 GitHub 仓库统计信息（Stars/Forks）用于首页展示
export const getGithubRepoStats = async () => {
  const response = await api.get('/github/repo-stats')
  return response.data
}
