<template>
  <!-- 通用确认对话框：替代原生 confirm()，统一 UI 风格与 i18n -->
  <Teleport to="body">
    <Transition name="confirm-dialog">
      <div
        v-if="visible"
        class="confirm-overlay"
        role="dialog"
        aria-modal="true"
        :aria-labelledby="titleId"
        :aria-describedby="messageId"
        @click.self="handleCancel"
        @keydown.esc.stop="handleCancel"
        tabindex="-1"
        ref="overlayRef"
      >
        <div class="confirm-dialog">
          <h3 v-if="title" :id="titleId" class="confirm-title">{{ title }}</h3>
          <p :id="messageId" class="confirm-message">{{ message }}</p>
          <div class="confirm-actions">
            <button type="button" class="confirm-btn confirm-btn-cancel" @click="handleCancel" ref="cancelBtnRef">
              {{ cancelText }}
            </button>
            <button
              type="button"
              class="confirm-btn"
              :class="confirmType === 'danger' ? 'confirm-btn-danger' : 'confirm-btn-primary'"
              @click="handleConfirm"
            >
              {{ confirmText }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
  title: { type: String, default: '' },
  message: { type: String, default: '' },
  confirmText: { type: String, default: 'OK' },
  cancelText: { type: String, default: 'Cancel' },
  // 'danger' | 'primary'
  confirmType: { type: String, default: 'primary' }
})
const emit = defineEmits(['confirm', 'cancel'])

// 为 aria 关联生成唯一 id
const uid = Math.random().toString(36).slice(2, 8)
const titleId = computed(() => `confirm-title-${uid}`)
const messageId = computed(() => `confirm-message-${uid}`)

const overlayRef = ref(null)
const cancelBtnRef = ref(null)

// 对话框打开时把焦点移入，便于键盘用户 ESC / Tab 操作
watch(
  () => props.visible,
  async (val) => {
    if (val) {
      await nextTick()
      // 默认聚焦到取消按钮，符合破坏性操作的安全默认值
      cancelBtnRef.value?.focus()
    }
  }
)

const handleConfirm = () => emit('confirm')
const handleCancel = () => emit('cancel')
</script>

<style scoped>
.confirm-overlay {
  position: fixed;
  inset: 0;
  background: rgba(5, 8, 16, 0.55);
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  padding: 16px;
}

.confirm-dialog {
  background: var(--bg-card, #1a1a24);
  color: var(--text-main, #e5e7eb);
  border: 1px solid var(--border, rgba(255, 255, 255, 0.08));
  border-radius: 12px;
  padding: 24px;
  width: min(420px, 100%);
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
}

.confirm-title {
  margin: 0 0 12px;
  font-size: 16px;
  font-weight: 600;
}

.confirm-message {
  margin: 0 0 20px;
  font-size: 14px;
  line-height: 1.6;
  color: var(--text-sub, #94a3b8);
}

.confirm-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.confirm-btn {
  padding: 8px 18px;
  font-size: 14px;
  border-radius: 8px;
  cursor: pointer;
  border: 1px solid transparent;
  transition: background 0.15s ease, border-color 0.15s ease;
}
.confirm-btn:focus-visible {
  outline: 2px solid #6366f1;
  outline-offset: 2px;
}

.confirm-btn-cancel {
  background: transparent;
  color: var(--text-sub, #94a3b8);
  border-color: var(--border, rgba(255, 255, 255, 0.12));
}
.confirm-btn-cancel:hover {
  background: rgba(255, 255, 255, 0.05);
  color: var(--text-main, #e5e7eb);
}

.confirm-btn-primary {
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  color: #fff;
}
.confirm-btn-primary:hover {
  filter: brightness(1.1);
}

.confirm-btn-danger {
  background: linear-gradient(135deg, #ef4444, #dc2626);
  color: #fff;
}
.confirm-btn-danger:hover {
  filter: brightness(1.1);
}

/* 过渡 */
.confirm-dialog-enter-active,
.confirm-dialog-leave-active {
  transition: opacity 0.18s ease;
}
.confirm-dialog-enter-active .confirm-dialog,
.confirm-dialog-leave-active .confirm-dialog {
  transition: transform 0.18s ease;
}
.confirm-dialog-enter-from,
.confirm-dialog-leave-to {
  opacity: 0;
}
.confirm-dialog-enter-from .confirm-dialog,
.confirm-dialog-leave-to .confirm-dialog {
  transform: translateY(-8px) scale(0.98);
}

/* 尊重系统低动效偏好 */
@media (prefers-reduced-motion: reduce) {
  .confirm-dialog-enter-active,
  .confirm-dialog-leave-active,
  .confirm-dialog-enter-active .confirm-dialog,
  .confirm-dialog-leave-active .confirm-dialog {
    transition: none;
  }
}
</style>
