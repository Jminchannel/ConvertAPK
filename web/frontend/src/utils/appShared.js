export const jsTemplate = `// 1. 定义广告API (h5api) - 需添加到您的网页中
window.h5api = {
  canPlayAd: function(callback) {
    if (callback) callback({ canPlayAd: true });
    return true;
  },
  playAd: function(callback) {
    if (window.adIsExecuting) {
      callback({ code: 10006, message: "广告加载中" });
      return;
    }
    window.adIsExecuting = true;
    if (window.sendToApp) {
      let tm = setTimeout(() => {
        window.playAdBack = () => {};
        window.adIsExecuting = false;
        callback({ code: 10005, message: "超时" });
      }, 10000);
      window.playAdBack = function(msg) {
        clearTimeout(tm);
        let data = typeof msg === "string" ? JSON.parse(msg) : msg;
        window.adIsExecuting = false;
        callback(data);
      };
      window.sendToApp("playAd", "");
    } else {
      window.adIsExecuting = false;
      callback({ code: 10004, message: "无环境，不支持广告" });
    }
  }
};
var app = {
  showVideo: function(videoAdCallback) {
    if (window.h5api && h5api.canPlayAd()) {
      h5api.playAd(function(res) {
        if (res.code === 10001) {
          videoAdCallback(1);
        } else {
          console.log("广告未完成: " + res.message);
        }
      });
    }
  }
};`

export const permissionsList = [
  'INTERNET',
  'ACCESS_NETWORK_STATE',
  'ACCESS_WIFI_STATE',
  'CAMERA',
  'READ_EXTERNAL_STORAGE',
  'WRITE_EXTERNAL_STORAGE',
  'ACCESS_FINE_LOCATION',
  'ACCESS_COARSE_LOCATION',
  'RECORD_AUDIO',
  'READ_PHONE_STATE',
  'CALL_PHONE',
  'READ_CONTACTS',
  'WRITE_CONTACTS',
  'VIBRATE',
  'WAKE_LOCK',
  'RECEIVE_BOOT_COMPLETED',
  'FOREGROUND_SERVICE',
  'REQUEST_INSTALL_PACKAGES',
  'SYSTEM_ALERT_WINDOW',
  'BLUETOOTH',
  'BLUETOOTH_ADMIN',
  'NFC',
  'READ_CALENDAR',
  'WRITE_CALENDAR'
]

export const normalizePermissionForUi = (permission) => {
  const raw = String(permission || '').trim()
  if (!raw) return ''
  if (raw.startsWith('android.permission.')) {
    return raw.slice('android.permission.'.length).toUpperCase()
  }
  if (permissionsList.includes(raw)) return raw
  const upper = raw.toUpperCase()
  if (permissionsList.includes(upper)) return upper
  return raw
}

export const normalizePermissionsForUi = (permissions) => {
  if (!Array.isArray(permissions)) return []
  const normalized = []
  const seen = new Set()
  for (const perm of permissions) {
    const value = normalizePermissionForUi(perm)
    if (!value || seen.has(value)) continue
    seen.add(value)
    normalized.push(value)
  }
  return normalized
}

export const defaultHtmlTemplate = `<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>My HTML App</title>
    <style>
      body { margin: 0; font-family: system-ui, -apple-system, "Segoe UI", sans-serif; }
      main { padding: 32px; }
    </style>
  </head>
  <body>
    <main>
      <h1>Hello HTML</h1>
      <p>Edit this HTML and save to build your APK.</p>
    </main>
  </body>
</html>
`

export const isValidPackageName = (value) => {
  if (!value) return false
  const trimmed = String(value).trim()
  return /^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$/.test(trimmed)
}

export const isValidUrl = (value) => {
  if (!value) return false
  try {
    const url = new URL(value)
    return url.protocol === 'http:' || url.protocol === 'https:'
  } catch {
    return false
  }
}

export const isValidHostName = (value) => {
  if (!value) return false
  const host = String(value).toLowerCase()
  if (host === 'localhost') return true
  const ipv4 = /^(25[0-5]|2[0-4]\d|1?\d?\d)(\.(25[0-5]|2[0-4]\d|1?\d?\d)){3}$/
  if (ipv4.test(host)) return true
  const labels = host.split('.')
  if (labels.length < 2) return false
  return labels.every((label, idx) => {
    if (!label || label.length > 63) return false
    if (!/^[a-z0-9-]+$/.test(label)) return false
    if (label.startsWith('-') || label.endsWith('-')) return false
    if (idx === labels.length - 1 && label.length < 2) return false
    return true
  })
}

export const isValidPort = (value) => {
  if (!value) return true
  const port = Number(value)
  return Number.isInteger(port) && port >= 1 && port <= 65535
}

export const isValidWebUrl = (value) => {
  if (!value) return false
  const trimmed = String(value).trim()
  if (!trimmed) return false
  const candidate = /^https?:\/\//i.test(trimmed) ? trimmed : `http://${trimmed}`
  try {
    const url = new URL(candidate)
    if (url.protocol !== 'http:' && url.protocol !== 'https:') return false
    if (!isValidHostName(url.hostname)) return false
    return isValidPort(url.port)
  } catch {
    return false
  }
}

export const formatFileSize = (bytes) => {
  if (!bytes && bytes !== 0) return '-'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

export const formatDate = (dateStr) => {
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

export const parseVersionParts = (value) => {
  const raw = String(value || '').trim()
  if (!raw) return [0]
  return raw.split('.').map((part) => {
    const n = Number(part)
    return Number.isFinite(n) ? Math.max(0, Math.floor(n)) : 0
  })
}

export const compareVersion = (a, b) => {
  const left = parseVersionParts(a)
  const right = parseVersionParts(b)
  const maxLen = Math.max(left.length, right.length)
  for (let i = 0; i < maxLen; i += 1) {
    const l = left[i] ?? 0
    const r = right[i] ?? 0
    if (l > r) return 1
    if (l < r) return -1
  }
  return 0
}

export const bumpPatchVersion = (value) => {
  const parts = parseVersionParts(value)
  if (!parts.length) return '1.0.1'
  while (parts.length < 3) parts.push(0)
  parts[parts.length - 1] += 1
  return parts.join('.')
}
