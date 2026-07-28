export const feedbackTicketStorageKey = 'apk_builder_feedback_conversations'

const normalizeTicket = (ticket) => {
  const feedbackId = Number.parseInt(ticket?.feedback_id, 10)
  const accessToken = String(ticket?.access_token || '').trim()
  if (!Number.isSafeInteger(feedbackId) || feedbackId <= 0 || !accessToken || accessToken.length > 512) {
    return null
  }
  return { feedback_id: feedbackId, access_token: accessToken }
}

export const createFeedbackInboxGuard = () => {
  let consumed = false
  return {
    consume: () => {
      if (consumed) return false
      consumed = true
      return true
    }
  }
}

export const readFeedbackTickets = (storage = typeof localStorage === 'undefined' ? null : localStorage) => {
  if (!storage) return []
  try {
    const parsed = JSON.parse(storage.getItem(feedbackTicketStorageKey) || '[]')
    if (!Array.isArray(parsed)) return []
    const knownTickets = new Map()
    for (const item of parsed) {
      const ticket = normalizeTicket(item)
      if (ticket) knownTickets.set(ticket.feedback_id, ticket)
    }
    return [...knownTickets.values()]
  } catch {
    return []
  }
}

export const saveFeedbackTicket = (storage, ticket) => {
  const normalizedTicket = normalizeTicket(ticket)
  if (!storage || !normalizedTicket) return false
  try {
    const tickets = readFeedbackTickets(storage)
    const knownTickets = new Map(tickets.map((item) => [item.feedback_id, item]))
    knownTickets.set(normalizedTicket.feedback_id, normalizedTicket)
    storage.setItem(feedbackTicketStorageKey, JSON.stringify([...knownTickets.values()]))
    return true
  } catch {
    return false
  }
}

export const selectAdminMessageText = (contentI18n, language) => {
  const messages = contentI18n && typeof contentI18n === 'object' ? contentI18n : {}
  const preferredLocales = [language, 'zh-CN', 'en', 'zh-TW']
  for (const locale of preferredLocales) {
    const text = String(messages[locale] || '').trim()
    if (text) return text
  }
  for (const text of Object.values(messages)) {
    const normalized = String(text || '').trim()
    if (normalized) return normalized
  }
  return ''
}

const messageTime = (message) => {
  const timestamp = Date.parse(String(message?.created_at || ''))
  return Number.isFinite(timestamp) ? timestamp : 0
}

export const enqueueUnreadAdminMessages = (messages) => {
  if (!Array.isArray(messages)) return []
  const knownMessages = new Map()
  for (const message of messages) {
    const feedbackId = Number.parseInt(message?.feedback_id, 10)
    const messageId = Number.parseInt(message?.id, 10)
    if (message?.sender_type !== 'admin' || feedbackId <= 0 || messageId <= 0) continue
    knownMessages.set(`${feedbackId}:${messageId}`, { ...message, feedback_id: feedbackId, id: messageId })
  }
  return [...knownMessages.values()].sort((left, right) => messageTime(left) - messageTime(right) || left.id - right.id)
}

export const sanitizeFeedbackReplyContent = (value, maxLength = 4000) => String(value || '')
  .replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F]/g, '')
  .trim()
  .slice(0, maxLength)

export const canSubmitInitialFeedback = (content, images) => Boolean(sanitizeFeedbackReplyContent(content) || (Array.isArray(images) && images.length))

export const shouldDismissFeedbackQueueMessage = (acknowledged) => acknowledged === true

export const revokeFeedbackPreviewUrls = (previews, revoke = (url) => URL.revokeObjectURL(url)) => {
  for (const url of Object.values(previews || {})) revoke(url)
}

export const selectFeedbackReplyImages = (files, maxImages = 5, maxSize = 10 * 1024 * 1024) => {
  const allowedTypes = new Set(['image/jpeg', 'image/png', 'image/webp', 'image/gif'])
  return Array.from(files || [])
    .filter((file) => file && allowedTypes.has(String(file.type || '').toLowerCase()) && file.size > 0 && file.size <= maxSize)
    .slice(0, maxImages)
}
