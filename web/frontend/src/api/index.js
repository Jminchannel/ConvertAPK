import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000
})
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

export const getAuthMe = async (clientId) => {
  const response = await api.get('/auth/me', {
    params: { client_id: clientId || getClientId() }
  })
  return response.data
}

export const logoutAccount = async () => {
  try {
    const response = await api.post('/auth/logout')
    return response.data
  } finally {
    clearAuthToken()
  }
}

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

export const uploadFile = async (file, onProgress) => {
  const formData = new FormData()
  formData.append('file', file)
  
  const response = await api.post('/upload', formData, {
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

// 濠电偞鍨堕幐鎼佹晝閿濆洦顫曢柤绋跨仛閸庣喖鏌￠崘銊モ偓褰掑汲韫囨稒鐓曢柕澹啩澹曢梺?
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

// 濠电偞鍨堕幐鎼佹晝閿濆洦顫曠紒鍌涚炕ML闂備礁鎼崐绋棵洪敐鍛瀻?
export const uploadHtml = async (file, onProgress) => {
  const formData = new FormData()
  formData.append('file', file)

  const response = await api.post('/upload-html', formData, {
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


// 濠电偞鍨堕幐鎼佹晝閿濆洦顫曢柛鎾茶兌妞规娊鏌熼鍡楀閳ь剚濞婇弻锟犲磼濮橆厾鐓戝┑鐐叉閸ㄤ粙寮?jks / .keystore闂?
export const scanExternalLinks = async (payload) => {
  const response = await api.post('/external-links/scan', payload || {})
  return response.data
}

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

export const probeUrl = async (url) => {
  const response = await api.post('/url-probe', { url })
  return response.data
}

// 闂備礁鎲＄敮妤冪矙閹寸姷纾介柟鎹愵嚙閸戠娀鏌涢弴銊ヤ簽缂佹唻绠戦湁闁绘ü璀﹂崵娆忊攽?
// taskData: { filename, icon_filename, config, reuse_keystore_from }
export const createTask = async (taskData) => {
  const clientId = getClientId()
  const response = await api.post('/tasks', { ...taskData, client_id: clientId })
  return response.data
}

// 闂備礁鍚嬮崕鎶藉床閼艰翰浜归柛銉ｅ妿椤╃兘鎮归崶銊ョ祷妞ゎ偁鍊濋弻娑㈠箳閹垮啯鐣介梺闈涙閸熸挳寮澶婇唶闁绘棃顥撳Ο鍝籰ient_id缂傚倷鐒︾粙鎺楁儎椤栫偛鐒垫い鎺嗗亾妞ぱ€鍋撶紓?
export const getTasks = async () => {
  const clientId = getClientId()
  const response = await api.get('/tasks', { params: { client_id: clientId } })
  return response.data
}

// 闂備礁鍚嬮崕鎶藉床閼艰翰浜归柛銉ｅ妿椤╃兘鎮归崶銊ョ祷妞ゎ偁鍊濋幃褰掑炊閻戣姤顎嶉梺?
export const getTask = async (taskId) => {
  const clientId = getClientId()
  const response = await api.get(`/tasks/${taskId}`, { params: { client_id: clientId } })
  return response.data
}

// 闂備礁鎲＄敮鐐寸箾閳ь剚绻涢崨顓烆劉缂佸倹甯為幏鐘诲箵閹烘繃鍖?
export const deleteTask = async (taskId) => {
  const clientId = getClientId()
  const response = await api.delete(`/tasks/${taskId}`, { params: { client_id: clientId } })
  return response.data
}

export const cancelRunningTasks = async () => {
  const clientId = getClientId()
  const response = await api.post('/tasks/cancel-running', { client_id: clientId })
  return response.data
}

// 闁诲孩顔栭崰鎺楀磻閹炬枼鏀芥い鏃傗拡閸庢劙鏌ｆ惔顔肩仩妞?
export const startTask = async (taskId) => {
  const clientId = getClientId()
  const response = await api.post(`/tasks/${taskId}/start`, null, { params: { client_id: clientId } })
  return response.data
}

// 闂傚倷鐒﹁ぐ鍐矓閻戣姤鍎婃い鏍ㄧ〒椤╃兘鎮归崶銊ョ祷妞?
export const retryTask = async (taskId) => {
  const clientId = getClientId()
  const response = await api.post(`/tasks/${taskId}/retry`, null, { params: { client_id: clientId } })
  return response.data
}

// 闂備礁鎲￠悷锕傛偋濡ゅ啰鐭撻柣鎴ｆ缁犱即鏌涢妷鎴濇噺濮ｅ孩绻涚€电鞋妞ゆ泦鍕弿?
export const cancelTask = async (taskId) => {
  const clientId = getClientId()
  const response = await api.post(`/tasks/${taskId}/cancel`, { client_id: clientId })
  return response.data
}

// 闂備礁鎼ú銈夋偤閵娾晛钃熷┑鐘插暟椤╃兘鎮归崶銊ョ祷妞ゎ偁鍊濋弻銊モ槈濡厧顣洪悷婊勬緲閸婂寮鈧畷姗€鍩￠崒婊冨笌闂備胶绮〃鍛存偋婵犲偊鑰垮ù鐓庣摠閺?
export const updateTask = async (taskId, updateData) => {
  const clientId = getClientId()
  const response = await api.put(`/tasks/${taskId}`, { ...updateData, client_id: clientId })
  return response.data
}

// 闂備礁鍚嬮崕鎶藉床閼艰翰浜归柛銉ｅ妿椤╃兘鎮归崶銊ョ祷妞ゎ偁鍊濋弻锟犲礃閿曗偓閸旀氨绱?
export const getTaskLogs = async (taskId, lines = 100) => {
  const clientId = getClientId()
  const response = await api.get(`/tasks/${taskId}/logs`, { params: { lines, client_id: clientId } })
  return response.data
}

// 闂備礁鍚嬮崕鎶藉床閼艰翰浜归柛銉ｅ妿閳绘棃鎮楅敐搴″箺缂佷椒鍗冲娲礈瑜嶆禍楣冩偨?
export const getDownloadUrl = (taskId) => {
  const clientId = getClientId()
  return `/api/download/${taskId}?client_id=${encodeURIComponent(clientId)}`
}

export const releaseDesktopOutputs = async () => {
  const clientId = getClientId()
  const response = await api.post('/tasks/desktop-output/release', null, {
    params: { client_id: clientId }
  })
  return response.data
}

export const sendReleaseDesktopOutputsBeacon = () => {
  const clientId = getClientId()
  const url = `/api/tasks/desktop-output/release?client_id=${encodeURIComponent(clientId)}`
  if (typeof navigator !== 'undefined' && typeof navigator.sendBeacon === 'function') {
    try {
      return navigator.sendBeacon(url, new Blob([], { type: 'text/plain;charset=UTF-8' }))
    } catch (error) {
      // 闂傚鍋勫ú銊╁疾椤愶箑姹?beacon 濠电姰鍨洪崕鑲╁垝閸撗勫枂闁挎洖鍊诲畵渚€鎮归搹鐟板妺缂佲偓閳ь剟姊绘笟鍥т簮闁稿鎹囬弻?fetch
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

export const getKeystoreUrl = (taskId) => {
  const clientId = getClientId()
  return `/api/keystore/${taskId}?client_id=${encodeURIComponent(clientId)}`
}

export const getIconUrl = (taskId) => {
  const clientId = getClientId()
  return `/api/icon/${taskId}?client_id=${encodeURIComponent(clientId)}`
}

// 闂備礁鍚嬮崕鎶藉床閼艰翰浜归柛銉墮閸戠娀鏌涢弴銊ヤ簽缂佹唻绠撳濠氬礃椤忓嫭鐎婚梺鍓茬厛娴滎亪骞冮埡鍛殝缁剧増锚娴?
export const getQueueStatus = async () => {
  const response = await api.get('/queue/status')
  return response.data
}

// 闂備礁鍚嬮崕鎶藉床閼艰翰浜归柛銉墮閸戠娀鏌涢弴銊ヤ簽缂佹唻绠撻弻锝咁煥鎼达紕浠╁銈忕祷閸旀垿骞冮埡鍛殝缁剧増锚娴?
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

// 闂備礁鎲￠崹闈浳涘Δ鍚藉洭顢楅崟顐㈠殤闂佸憡娲﹂崑鍡欐閿曞倹鐓熸繝濠傞閻忕姵銇?
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

// 闂備礁鍚嬮崕鎶藉床閼艰翰浜归柛銉戝苯鏅犻梺闈涱槶閸庡崬顕ラ弮鍫熲拺濡わ絽鍟伴悾娲煕濡鈧妲?
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

// 闂佽崵濮崇粈浣规櫠娴犲鍋柛鈩冾殢閸熷懘鏌曟径鍫濆姎鐎电増妫冨鐑樸偅閸愵亞鏆梺鍛娗滈崐妤冩?
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

// 缂傚倷鑳舵刊瀵告閺囥垹绠栧┑鐘叉搐鐟欙箓骞栫划鍏夊亾閹惰棄褰欓梻浣侯焾濞存岸宕滃▎鎾崇疅?
export const getAdminAnnouncements = async () => {
  const response = await api.get('/adminhub/announcements')
  return response.data
}

export const getAdminFeatures = async () => {
  const response = await api.get('/adminhub/features')
  return response.data
}

// 闂備礁鎼ú銈夋偤閵娾晛钃熷┑鐘蹭迹濞戙垹鐒垫い鎺戝閽?
export const checkUpdate = async (version) => {
  const response = await api.get('/adminhub/update-check', { params: { version } })
  return response.data
}

// 缂傚倷绶￠崹闈涚暦閻㈤潧鍨濋柣鎴烆焽閳瑰秹鏌嶉埡浣告殨缂?
export const getSystemInfo = async () => {
  const response = await api.get('/system/info')
  return response.data
}

// 闂備礁鍚嬮崕鎶藉床閼艰翰浜归柛銉簵娴滃綊鏌熼幆褍鏆辨い銈呮嚇閺岋絽螖閳ь剟鎮ф繝鍌﹁€?
export const getAppVersion = async () => {
  const response = await api.get('/app/version')
  return response.data
}

// 闂備礁鎲￠悷銉х矓瑜版帇鈧懘顢橀姀鐘殿唽闂佸綊鍋婃禍婵嬪船?
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

export const getGithubRepoStats = async () => {
  const response = await api.get('/github/repo-stats')
  return response.data
}
