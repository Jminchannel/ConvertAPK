import assert from 'node:assert/strict'
import {
  canSubmitInitialFeedback,
  createFeedbackInboxGuard,
  enqueueUnreadAdminMessages,
  readFeedbackTickets,
  revokeFeedbackPreviewUrls,
  saveFeedbackTicket,
  selectAdminMessageText,
  shouldDismissFeedbackQueueMessage
} from '../src/utils/feedbackConversation.js'

const storage = () => {
  const values = new Map()
  return {
    getItem: (key) => values.get(key) || null,
    setItem: (key, value) => values.set(key, String(value))
  }
}

{
  const guard = createFeedbackInboxGuard()
  assert.equal(guard.consume(), true)
  assert.equal(guard.consume(), false)
}

{
  assert.equal(selectAdminMessageText({ 'zh-CN': '中文', en: 'English' }, 'en'), 'English')
  assert.equal(selectAdminMessageText({ 'zh-CN': '中文' }, 'en'), '中文')
  assert.equal(selectAdminMessageText({}, 'en'), '')
}

{
  const localStorage = storage()
  assert.equal(saveFeedbackTicket(localStorage, { feedback_id: 31, access_token: 'secret-value' }), true)
  assert.deepEqual(readFeedbackTickets(localStorage), [{ feedback_id: 31, access_token: 'secret-value' }])
  assert.equal(saveFeedbackTicket(localStorage, { feedback_id: 31, access_token: '' }), false)
}

{
  const queue = enqueueUnreadAdminMessages([
    { id: 2, feedback_id: 31, sender_type: 'admin', created_at: '2026-07-28T10:00:00Z' },
    { id: 1, feedback_id: 31, sender_type: 'admin', created_at: '2026-07-28T09:00:00Z' },
    { id: 3, feedback_id: 31, sender_type: 'client', created_at: '2026-07-28T08:00:00Z' }
  ])
  assert.deepEqual(queue.map((message) => message.id), [1, 2])
}

{
  assert.equal(shouldDismissFeedbackQueueMessage(false), false)
  assert.equal(shouldDismissFeedbackQueueMessage(true), true)
}

{
  assert.equal(canSubmitInitialFeedback('   ', []), false)
  assert.equal(canSubmitInitialFeedback('   ', [{ name: 'screen.png' }]), true)
}

{
  const revoked = []
  revokeFeedbackPreviewUrls({ first: 'blob:one', second: 'blob:two' }, (url) => revoked.push(url))
  assert.deepEqual(revoked, ['blob:one', 'blob:two'])
}

console.log('feedbackConversation helpers: PASS')
