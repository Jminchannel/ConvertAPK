import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000
})

// 生成或获取客户端ID（用于设备/浏览器隔离）
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

// 上传ZIP文件
export const uploadFile = async (file, onProgress) => {
  const formData = new FormData()
  formData.append('file', file)
  
  const response = await api.post('/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    },
    onUploadProgress: (progressEvent) => {
      if (onProgress) {
        const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total)
        onProgress(percent)
      }
    }
  })
  return response.data
}

// 上传应用图标
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

// 上传HTML文件
export const uploadHtml = async (file, onProgress) => {
  const formData = new FormData()
  formData.append('file', file)

  const response = await api.post('/upload-html', formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    },
    onUploadProgress: (progressEvent) => {
      if (onProgress) {
        const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total)
        onProgress(percent)
      }
    }
  })
  return response.data
}


// 上传签名文件（.jks / .keystore）
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

// 创建构建任务
// taskData: { filename, icon_filename, config, reuse_keystore_from }
export const createTask = async (taskData) => {
  const clientId = getClientId()
  const response = await api.post('/tasks', { ...taskData, client_id: clientId })
  return response.data
}

// 获取任务列表（按client_id筛选）
export const getTasks = async () => {
  const clientId = getClientId()
  const response = await api.get('/tasks', { params: { client_id: clientId } })
  return response.data
}

// 获取任务详情
export const getTask = async (taskId) => {
  const clientId = getClientId()
  const response = await api.get(`/tasks/${taskId}`, { params: { client_id: clientId } })
  return response.data
}

// 删除任务
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

// 开始构建
export const startTask = async (taskId) => {
  const clientId = getClientId()
  const response = await api.post(`/tasks/${taskId}/start`, null, { params: { client_id: clientId } })
  return response.data
}

// 重试任务
export const retryTask = async (taskId) => {
  const clientId = getClientId()
  const response = await api.post(`/tasks/${taskId}/retry`, null, { params: { client_id: clientId } })
  return response.data
}

// 取消指定任务
export const cancelTask = async (taskId) => {
  const clientId = getClientId()
  const response = await api.post(`/tasks/${taskId}/cancel`, { client_id: clientId })
  return response.data
}

// 更新任务（发布新版本）
export const updateTask = async (taskId, updateData) => {
  const clientId = getClientId()
  const response = await api.put(`/tasks/${taskId}`, { ...updateData, client_id: clientId })
  return response.data
}

// 获取任务日志
export const getTaskLogs = async (taskId, lines = 100) => {
  const clientId = getClientId()
  const response = await api.get(`/tasks/${taskId}/logs`, { params: { lines, client_id: clientId } })
  return response.data
}

// 获取下载链接
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
      // 忽略 beacon 失败并回退到 fetch
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

// 获取构建队列状态
export const getQueueStatus = async () => {
  const response = await api.get('/queue/status')
  return response.data
}

// 获取构建环境状态
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

// 准备构建环境
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

// 获取工具链配置
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

// 设置工具链配置
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

// 管理后台公告
export const getAdminAnnouncements = async () => {
  const response = await api.get('/adminhub/announcements')
  return response.data
}

export const getAdminFeatures = async () => {
  const response = await api.get('/adminhub/features')
  return response.data
}

// 更新检查
export const checkUpdate = async (version) => {
  const response = await api.get('/adminhub/update-check', { params: { version } })
  return response.data
}

// 系统信息
export const getSystemInfo = async () => {
  const response = await api.get('/system/info')
  return response.data
}

// 获取当前版本
export const getAppVersion = async () => {
  const response = await api.get('/app/version')
  return response.data
}

// 反馈提交
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
