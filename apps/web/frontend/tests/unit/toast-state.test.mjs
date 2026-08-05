import { describe, expect, it, vi } from 'vitest'
import { useToastState } from '../../src/features/ui/composables/useToastState.js'

describe('useToastState', () => {
  it('显示提示并在默认时长后自动隐藏', () => {
    vi.useFakeTimers()
    const { toast, showToast } = useToastState()

    showToast('保存成功', 'success')

    expect(toast.value).toEqual({ show: true, type: 'success', message: '保存成功' })
    vi.advanceTimersByTime(3000)
    expect(toast.value.show).toBe(false)
    vi.useRealTimers()
  })
})
