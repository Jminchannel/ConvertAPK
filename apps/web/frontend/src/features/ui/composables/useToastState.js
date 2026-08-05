import { ref } from 'vue'

const defaultDuration = 3000

export const useToastState = () => {
  const toast = ref({ show: false, type: 'success', message: '' })
  let hideTimer = null

  const showToast = (message, type = 'success', duration = defaultDuration) => {
    toast.value = { show: true, type, message }
    if (hideTimer) clearTimeout(hideTimer)
    hideTimer = setTimeout(() => {
      toast.value.show = false
      hideTimer = null
    }, duration)
  }

  return { toast, showToast }
}
