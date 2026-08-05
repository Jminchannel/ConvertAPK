<template>
  <div
    class="app"
    :class="{
      'light-theme': currentTheme === 'light',
      'mobile-shell-active': isMobileShell,
      'mobile-tab-build': mobileTab === 'build',
      'mobile-tab-tasks': mobileTab === 'tasks',
      'mobile-tab-profile': mobileTab === 'profile',
      'app-boot-loading': appBootLoading
    }"
    :aria-busy="appBootLoading ? 'true' : 'false'"
  >
    <Transition name="app-boot-loader">
      <div
        v-if="appBootLoading"
        class="app-boot-overlay"
        role="status"
        aria-live="polite"
        aria-label="Loading"
      >
        <div class="app-boot-panel">
          <div class="app-boot-gooey" aria-hidden="true">
            <span class="app-boot-blob app-boot-blob-main"></span>
            <span class="app-boot-blob app-boot-blob-accent"></span>
            <span class="app-boot-blob app-boot-blob-dot"></span>
          </div>
          <div class="app-boot-pulse" aria-hidden="true">
            <span></span>
            <span></span>
            <span></span>
          </div>
        </div>
      </div>
    </Transition>

    <AppHeader />
    <main class="main" ref="mainRef">
      <div class="container mobile-main-container">
        <div v-if="isMobileShell" ref="mobilePageHeadRef" class="mobile-page-head">
          <div class="mobile-page-head-title">{{ mobileTab === 'profile' ? mobileSettingsLabel : mobileTabTitle }}</div>
          <div class="mobile-page-head-subtitle">{{ mobileTabSubtitle }}</div>
        </div>

        <div
          class="mobile-swipe-stage"
          :class="{ 'mobile-swipe-dragging': mobileSwipeDragging }"
          :style="isMobileShell ? mobileSwipeStyle : null"
          @touchstart="handleMobileSwipeStart"
          @touchmove="handleMobileSwipeMove"
          @touchend="handleMobileSwipeEnd"
          @touchcancel="handleMobileSwipeCancel"
        >

        <div
          v-if="activeAnnouncement && !isMobileShell"
          class="card no-drag"
          style="margin-bottom: 16px;"
        >
          <div class="card-header">
            <div class="card-icon">!</div>
            <div>
              <div class="card-title">{{ t('announcement.title') }}</div>
              <div class="card-subtitle">{{ activeAnnouncement.title }} - {{ activeAnnouncement.body }}</div>
            </div>
            <button class="btn btn-ghost btn-sm no-drag" style="margin-left: auto;" @click.stop="dismissAnnouncement">
              {{ t('announcement.dismiss') }}
            </button>
          </div>
        </div>

        <!-- Mode Tabs -->
        <div
          class="mode-tabs mobile-build-only"
          v-show="!isMobileShell || mobileTab === 'build'"
        >
          <button class="mode-tab" :class="{ active: mode === 'convert' }" @click="handleModeChange('convert')">
            <span class="mode-icon">◇</span>
            {{ t('mode.apk') }}
          </button>
          <button v-if="isWebModeEnabled" class="mode-tab" :class="{ active: mode === 'web' }" @click="handleModeChange('web')">
            <span class="mode-icon">◎</span>
            {{ t('mode.web') }}
          </button>
          <button v-if="isDesktopModeEnabled" class="mode-tab" :class="{ active: mode === 'desktop' }" @click="handleModeChange('desktop')">
            <span class="mode-icon">&#x1F5A5;</span>
            {{ t('mode.desktop') }}
          </button>
          <button class="mode-tab" :class="{ active: mode === 'html' }" @click="handleModeChange('html')">
            <span class="mode-icon">&lt;/&gt;</span>
            {{ t('mode.html') }}
          </button>
        </div>

        <!-- Steps -->
        <div
          class="steps mobile-build-only"
          v-show="!isMobileShell || mobileTab === 'build'"
        >
          <div class="step" :class="{ active: currentStep === 1, completed: currentStep > 1 }">
            <div class="step-number">{{ currentStep > 1 ? '✓' : '1' }}</div>
            <div class="step-text">
              {{ mode === 'web' ? t('web.url') : (mode === 'html' ? t('html.upload') : t('steps.upload')) }}
            </div>
          </div>
          <div class="step" :class="{ active: currentStep === 2, completed: currentStep > 2 }">
            <div class="step-number">{{ currentStep > 2 ? '✓' : '2' }}</div>
            <div class="step-text">{{ t('steps.configure') }}</div>
          </div>
          <div class="step" :class="{ active: currentStep === 3, completed: currentStep > 3 }">
            <div class="step-number">{{ currentStep > 3 ? '✓' : '3' }}</div>
            <div class="step-text">{{ mode === 'desktop' ? t('steps.buildDesktop') : t('steps.build') }}</div>
          </div>
        </div>

        <div class="grid grid-auto mobile-content-grid">
          <BuildWorkspace />
          <TaskWorkspace />
        </div>
        </div>
      </div>
    </main>
    <nav v-if="isMobileShell" class="mobile-bottom-nav no-drag">
      <button class="mobile-tab-btn" :class="{ active: mobileTab === 'build' }" @click="switchMobileTab('build', { animate: false })">
        <span class="mobile-tab-icon">&#x1F6E0;</span>
        <span class="mobile-tab-label">{{ t('config.title') }}</span>
      </button>
      <button class="mobile-tab-btn" :class="{ active: mobileTab === 'tasks' }" @click="switchMobileTab('tasks', { animate: false })">
        <span class="mobile-tab-icon">&#x1F4CB;</span>
        <span class="mobile-tab-label">{{ t('tasks.title') }}</span>
      </button>
      <button class="mobile-tab-btn" :class="{ active: mobileTab === 'profile' }" @click="switchMobileTab('profile', { animate: false })">
        <span class="mobile-tab-icon">&#x2699;</span>
        <span class="mobile-tab-label">{{ mobileSettingsLabel }}</span>
      </button>
    </nav>
    <AppDialogs />
    <!-- Toast -->
    <Transition name="toast">
      <div
        v-if="toast.show"
        class="toast"
        :class="toast.type"
        role="status"
        aria-live="polite"
      >
        <span class="toast-icon" aria-hidden="true">
          {{ toast.type === 'success' ? '\u2714' : (toast.type === 'warning' ? '\u26A0' : '\u2716') }}
        </span>
        <span>{{ toast.message }}</span>
      </div>
    </Transition>
  </div>
</template>

<script>
import { defineComponent } from 'vue'
import { useAppStateContext } from './appStateContext'
import AppHeader from '../components/layout/AppHeader.vue'
import BuildWorkspace from '../features/build/BuildWorkspace.vue'
import TaskWorkspace from '../features/tasks/TaskWorkspace.vue'
import AppDialogs from '../features/dialogs/AppDialogs.vue'

export default defineComponent({
  name: 'AppShell',
  components: { AppHeader, BuildWorkspace, TaskWorkspace, AppDialogs },
  setup() {
    return useAppStateContext()
  }
})
</script>

<style scoped>
/* Toast 过渡动画：仅在 App.vue 组件内使用，保持 scoped */
.toast-enter-active,
.toast-leave-active {
  transition: all 0.3s ease;
}
.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translateY(20px);
}
/* Toast 内部图标样式（将 'OK'/'X' 文本替换为 Unicode 对钩/叉后所需的显示调整） */
.toast .toast-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 20px;
  font-weight: 600;
}
/* 尊重系统低动效偏好 */
@media (prefers-reduced-motion: reduce) {
  .toast-enter-active,
  .toast-leave-active {
    transition: none;
  }
}

</style>

<!--
  下方为非 scoped 的全局样式块，承载 Teleport 到 body 的弹窗 / 全局工具类样式。
  若迁移到 src/style.css 需要注意：弹窗样式被 Teleport 渲染到 App 组件树之外，
  scoped 会丢失作用域属性导致样式失效；保留为非 scoped 的单文件样式块是有意选择。
-->
<style>
/* 首屏加载遮罩 */
.app-boot-overlay {
  position: fixed;
  inset: 0;
  z-index: 4000;
  display: grid;
  place-items: center;
  padding: 24px;
  background:
    linear-gradient(135deg, rgba(7, 16, 31, 0.92), rgba(9, 18, 34, 0.82)),
    rgba(7, 16, 31, 0.88);
  backdrop-filter: blur(18px) saturate(1.2);
  -webkit-backdrop-filter: blur(18px) saturate(1.2);
  pointer-events: auto;
  cursor: wait;
  touch-action: none;
  overscroll-behavior: contain;
}

.light-theme .app-boot-overlay {
  background:
    linear-gradient(135deg, rgba(238, 245, 255, 0.92), rgba(248, 252, 255, 0.82)),
    rgba(238, 245, 255, 0.88);
}

.app-boot-panel {
  width: min(360px, calc(100vw - 40px));
  min-height: 338px;
  display: grid;
  justify-items: center;
  align-content: center;
  gap: 20px;
  padding: 32px 28px;
  border: 1px solid rgba(134, 190, 255, 0.24);
  border-radius: 8px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.12), rgba(255, 255, 255, 0.04)),
    rgba(10, 20, 38, 0.72);
  box-shadow:
    0 24px 72px rgba(0, 0, 0, 0.32),
    inset 0 1px 0 rgba(255, 255, 255, 0.18);
}

.light-theme .app-boot-panel {
  border-color: rgba(47, 111, 237, 0.20);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.86), rgba(255, 255, 255, 0.58)),
    rgba(255, 255, 255, 0.72);
  box-shadow:
    0 24px 72px rgba(47, 111, 237, 0.16),
    inset 0 1px 0 rgba(255, 255, 255, 0.84);
}

.app-boot-orbit {
  position: relative;
  width: 132px;
  height: 132px;
  display: grid;
  place-items: center;
}

.app-boot-ring,
.app-boot-spark,
.app-boot-core {
  position: absolute;
}

.app-boot-ring {
  border-radius: 50%;
}

.app-boot-ring-a {
  inset: 0;
  border: 2px solid rgba(134, 190, 255, 0.22);
  border-top-color: #66d4ff;
  border-right-color: #25d189;
  animation: appBootSpin 1.45s linear infinite;
}

.app-boot-ring-b {
  inset: 18px;
  border: 1px dashed rgba(255, 255, 255, 0.32);
  border-left-color: rgba(37, 209, 137, 0.74);
  border-bottom-color: rgba(61, 134, 255, 0.74);
  animation: appBootSpinReverse 2.8s linear infinite;
}

.app-boot-core {
  width: 58px;
  height: 58px;
  display: grid;
  place-items: center;
  border-radius: 8px;
  background: linear-gradient(135deg, #3d86ff 0%, #25d189 100%);
  color: #fff;
  box-shadow:
    0 18px 40px rgba(61, 134, 255, 0.30),
    inset 0 1px 0 rgba(255, 255, 255, 0.30);
  animation: appBootCore 2.4s ease-in-out infinite;
}

.app-boot-core-mark {
  font-size: 15px;
  font-weight: 800;
  letter-spacing: 0;
}

.app-boot-spark {
  width: 10px;
  height: 10px;
  border-radius: 2px;
  background: #66d4ff;
  box-shadow: 0 0 18px rgba(102, 212, 255, 0.60);
  transform: rotate(45deg);
  animation: appBootSpark 1.9s ease-in-out infinite;
}

.app-boot-spark-a {
  top: 16px;
  right: 24px;
}

.app-boot-spark-b {
  bottom: 20px;
  left: 20px;
  background: #25d189;
  box-shadow: 0 0 18px rgba(37, 209, 137, 0.54);
  animation-delay: 0.28s;
}

.app-boot-spark-c {
  right: 13px;
  bottom: 38px;
  width: 8px;
  height: 8px;
  background: #f2a53b;
  box-shadow: 0 0 18px rgba(242, 165, 59, 0.48);
  animation-delay: 0.56s;
}

.app-boot-progress {
  position: relative;
  width: 100%;
  max-width: 238px;
  height: 5px;
  overflow: hidden;
  border-radius: 999px;
  background: rgba(134, 190, 255, 0.16);
}

.light-theme .app-boot-progress {
  background: rgba(47, 111, 237, 0.12);
}

.app-boot-progress span {
  position: absolute;
  inset: 0 auto 0 0;
  width: 46%;
  border-radius: inherit;
  background: linear-gradient(90deg, #3d86ff 0%, #25d189 64%, #66d4ff 100%);
  animation: appBootProgress 1.25s ease-in-out infinite;
}

.app-boot-loader-enter-active,
.app-boot-loader-leave-active {
  transition: opacity 0.34s ease, transform 0.34s ease;
}

.app-boot-loader-enter-from,
.app-boot-loader-leave-to {
  opacity: 0;
  transform: scale(1.015);
}

@keyframes appBootSpin {
  to { transform: rotate(360deg); }
}

@keyframes appBootSpinReverse {
  to { transform: rotate(-360deg); }
}

@keyframes appBootCore {
  0%, 100% { transform: scale(1) rotate(0deg); }
  50% { transform: scale(1.06) rotate(4deg); }
}

@keyframes appBootSpark {
  0%, 100% { opacity: 0.42; transform: rotate(45deg) scale(0.82); }
  50% { opacity: 1; transform: rotate(45deg) scale(1.16); }
}

@keyframes appBootProgress {
  0% { transform: translateX(-110%); }
  100% { transform: translateX(235%); }
}

@media (max-width: 640px) {
  .app-boot-overlay {
    padding: 18px;
  }

  .app-boot-panel {
    width: min(326px, calc(100vw - 32px));
    min-height: 314px;
    padding: 28px 22px;
  }

  .app-boot-orbit {
    width: 118px;
    height: 118px;
  }

  .app-boot-core {
    width: 52px;
    height: 52px;
  }

}

@media (prefers-reduced-motion: reduce) {
  .app-boot-ring-a,
  .app-boot-ring-b,
  .app-boot-core,
  .app-boot-spark,
  .app-boot-progress span {
    animation: none;
  }

  .app-boot-loader-enter-active,
  .app-boot-loader-leave-active {
    transition: none;
  }
}

/* 首屏加载遮罩：参考 gooey blob 风格重新实现 */
.app-boot-overlay {
  background: #000;
  backdrop-filter: none;
  -webkit-backdrop-filter: none;
}

.light-theme .app-boot-overlay {
  background: #000;
}

.app-boot-panel {
  width: min(420px, calc(100vw - 40px));
  min-height: 360px;
  display: grid;
  justify-items: center;
  align-content: center;
  gap: 18px;
  padding: 24px 20px;
  border: 0;
  border-radius: 0;
  background: transparent;
  box-shadow: none;
  color: #fff;
}

.light-theme .app-boot-panel {
  border: 0;
  background: transparent;
  box-shadow: none;
}

.app-boot-gooey {
  position: relative;
  width: min(340px, 82vw);
  height: 168px;
  overflow: hidden;
  background: #000;
  filter: blur(11px) contrast(24);
  -webkit-filter: blur(11px) contrast(24);
}

.app-boot-blob {
  position: absolute;
  top: 50%;
  left: 50%;
  border-radius: 50%;
  transform: translate(-50%, -50%);
}

.app-boot-blob-main,
.app-boot-blob-accent {
  width: 72px;
  height: 72px;
}

.app-boot-blob-main {
  left: 24%;
  background: #fff;
  box-shadow: 0 0 32px rgba(255, 255, 255, 0.88);
  animation: appBootGooeyLeft 2.45s ease-in-out infinite;
}

.app-boot-blob-accent {
  left: 76%;
  background: #00f5ff;
  box-shadow: 0 0 36px rgba(0, 245, 255, 0.92);
  animation: appBootGooeyRight 2.45s ease-in-out infinite;
}

.app-boot-blob-dot {
  width: 30px;
  height: 30px;
  background: #b8fff8;
  box-shadow: 0 0 26px rgba(184, 255, 248, 0.72);
  animation: appBootGooeyDot 2.45s ease-in-out infinite;
}

.app-boot-pulse {
  display: inline-flex;
  gap: 8px;
  padding-top: 2px;
}

.app-boot-pulse span {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #fff;
  opacity: 0.28;
  animation: appBootPulse 1.15s ease-in-out infinite;
}

.app-boot-pulse span:nth-child(2) {
  background: #00f5ff;
  animation-delay: 0.16s;
}

.app-boot-pulse span:nth-child(3) {
  animation-delay: 0.32s;
}

@keyframes appBootGooeyLeft {
  0%, 100% {
    left: 24%;
    transform: translate(-50%, -50%) scale(0.94);
  }
  48%, 52% {
    left: 50%;
    transform: translate(-50%, -50%) scale(1.08);
  }
}

@keyframes appBootGooeyRight {
  0%, 100% {
    left: 76%;
    transform: translate(-50%, -50%) scale(0.94);
  }
  48%, 52% {
    left: 50%;
    transform: translate(-50%, -50%) scale(1.08);
  }
}

@keyframes appBootGooeyDot {
  0%, 100% {
    opacity: 0.5;
    transform: translate(-50%, -50%) scale(0.84);
  }
  50% {
    opacity: 1;
    transform: translate(-50%, -50%) scale(1.34);
  }
}

@keyframes appBootPulse {
  0%, 100% {
    opacity: 0.22;
    transform: translateY(0);
  }
  50% {
    opacity: 0.92;
    transform: translateY(-5px);
  }
}

@media (max-width: 640px) {
  .app-boot-panel {
    width: min(340px, calc(100vw - 32px));
    min-height: 320px;
    padding: 18px 10px;
  }

  .app-boot-gooey {
    width: min(286px, 86vw);
    height: 142px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .app-boot-blob,
  .app-boot-pulse span {
    animation: none;
  }
}

/* Mode Tabs */
.status-bar-settings {
  gap: 16px;
  align-items: start;
  margin-bottom: 12px;
}

.status-bar-toggle-group {
  display: flex;
  align-items: flex-end;
  min-height: 78px;
}

.status-bar-color-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.status-bar-color-row.is-disabled {
  opacity: 0.62;
}

.status-bar-color-picker {
  flex: 0 0 48px;
  width: 48px;
  height: 44px;
  padding: 4px;
  border: 1px solid var(--input-border);
  border-radius: 10px;
  background: var(--input-bg);
  cursor: pointer;
}

.status-bar-color-picker:disabled,
.status-bar-color-text:disabled {
  cursor: not-allowed;
}

.status-bar-color-text {
  min-width: 0;
  text-transform: uppercase;
}

.mode-tabs {
  --mode-tabs-text: rgba(51, 65, 85, 0.84);
  --mode-tabs-active-text: #1d4ed8;
  position: relative;
  display: flex;
  gap: 0;
  margin-bottom: 24px;
  background:
    linear-gradient(90deg, rgba(255, 255, 255, 0.12), transparent 42%, rgba(255, 255, 255, 0.10)),
    rgba(248, 250, 252, 0.035);
  padding: 6px;
  border-radius: 18px;
  border: 1px solid rgba(255, 255, 255, 0.70);
  width: fit-content;
  color: var(--mode-tabs-text);
  box-shadow:
    0 14px 30px rgba(15, 23, 42, 0.08),
    inset 2px -2px 1px -1px rgba(255, 255, 255, 0.84),
    inset -2px 2px 1px -1px rgba(255, 255, 255, 0.78),
    inset 8px -8px 2px -8px rgba(255, 255, 255, 0.34),
    inset -8px 8px 2px -8px rgba(255, 255, 255, 0.36),
    inset 0 0 2px rgba(15, 23, 42, 0.11);
  backdrop-filter: blur(3px) saturate(1.18) contrast(1.01) brightness(1.02);
  -webkit-backdrop-filter: blur(3px) saturate(1.18) contrast(1.01) brightness(1.02);
  overflow: hidden;
  isolation: isolate;
}

.mode-tabs::before,
.mode-tabs::after {
  content: "";
  position: absolute;
  pointer-events: none;
  z-index: 0;
  border-radius: inherit;
}

.mode-tabs::before {
  top: 34%;
  left: 8px;
  right: 8px;
  bottom: 6px;
  border: 1px solid rgba(15, 23, 42, 0.14);
  filter: blur(7px);
  opacity: 0.10;
}

.mode-tabs::after {
  inset: 0;
  background:
    linear-gradient(45deg, rgba(255, 255, 255, 0.54) 0%, transparent 16%, transparent 82%, rgba(255, 255, 255, 0.42) 100%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.08), transparent 34%, transparent);
  filter: blur(0.4px);
  opacity: 0.32;
}
.mode-tab {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 24px;
  border-radius: 13px;
  border: 1px solid transparent;
  background: transparent;
  color: var(--mode-tabs-text);
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  overflow: hidden;
  transition: color 0.2s ease, transform 0.18s ease, box-shadow 0.2s ease;
}

.mode-tab::before,
.mode-tab::after {
  content: "";
  position: absolute;
  inset: 1px 3px;
  border-radius: inherit;
  pointer-events: none;
  opacity: 0;
  transition: opacity 0.2s ease;
}

.mode-tab::before {
  background:
    radial-gradient(circle at 54% 54%, rgba(148, 163, 184, 0.22), rgba(148, 163, 184, 0.10) 40%, transparent 68%),
    radial-gradient(circle at 48% 42%, rgba(255, 255, 255, 0.42), transparent 56%);
  filter: blur(0.2px);
}

.mode-tab::after {
  background:
    linear-gradient(45deg, rgba(255, 255, 255, 0.58) 0%, transparent 21%, transparent 76%, rgba(255, 255, 255, 0.48) 100%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.22), rgba(255, 255, 255, 0.04) 42%, rgba(226, 232, 240, 0.12));
  box-shadow:
    inset 2px -2px 1px -1px rgba(255, 255, 255, 0.82),
    inset -2px 2px 1px -1px rgba(255, 255, 255, 0.62),
    inset 0 0 1px rgba(15, 23, 42, 0.14);
  filter: blur(0.55px);
}
.mode-tab:hover {
  color: var(--mode-tabs-active-text);
}

.mode-tab:focus,
.mode-tab:focus-visible,
.mode-tab:active {
  outline: none;
  border-color: transparent;
  box-shadow: none;
}

.mode-tab.active {
  background: transparent;
  color: var(--mode-tabs-active-text);
  border-color: transparent;
  box-shadow: none;
  font-weight: 750;
}

.mode-tab.active::before,
.mode-tab.active::after {
  opacity: 1;
}

.mode-tab:active {
  transform: scale(0.98);
}

.mode-tab > * {
  position: relative;
  z-index: 1;
}
.mode-icon { font-size: 16px; }

html:not(.light-theme) .mode-tabs {
  --mode-tabs-text: rgba(226, 232, 240, 0.78);
  --mode-tabs-active-text: #dbeafe;
  background:
    linear-gradient(90deg, rgba(148, 163, 184, 0.055), rgba(15, 23, 42, 0.04) 42%, rgba(96, 165, 250, 0.055)),
    rgba(15, 23, 42, 0.10);
  border-color: rgba(203, 213, 225, 0.22);
  box-shadow:
    0 18px 34px rgba(0, 0, 0, 0.28),
    inset 2px -2px 1px -1px rgba(255, 255, 255, 0.30),
    inset -2px 2px 1px -1px rgba(255, 255, 255, 0.22),
    inset 8px -8px 2px -8px rgba(255, 255, 255, 0.07),
    inset -8px 8px 2px -8px rgba(255, 255, 255, 0.07),
    inset 0 0 2px rgba(0, 0, 0, 0.42);
}

html:not(.light-theme) .mode-tabs::before {
  border-color: rgba(0, 0, 0, 0.30);
  opacity: 0.16;
}

html:not(.light-theme) .mode-tabs::after {
  background:
    linear-gradient(45deg, rgba(255, 255, 255, 0.14) 0%, transparent 18%, transparent 82%, rgba(255, 255, 255, 0.10) 100%),
    linear-gradient(180deg, rgba(226, 232, 240, 0.025), transparent 34%, transparent);
  opacity: 0.18;
}

html:not(.light-theme) .mode-tab {
  color: var(--mode-tabs-text);
}

html:not(.light-theme) .mode-tab.active,
html:not(.light-theme) .mode-tab:hover {
  color: var(--mode-tabs-active-text);
}

html:not(.light-theme) .mode-tab::before {
  background:
    radial-gradient(circle at 54% 54%, rgba(71, 85, 105, 0.38), rgba(30, 41, 59, 0.22) 40%, transparent 68%),
    radial-gradient(circle at 48% 42%, rgba(226, 232, 240, 0.20), transparent 56%);
}

html:not(.light-theme) .mode-tab::after {
  background:
    linear-gradient(45deg, rgba(255, 255, 255, 0.24) 0%, transparent 22%, transparent 76%, rgba(255, 255, 255, 0.18) 100%),
    linear-gradient(180deg, rgba(226, 232, 240, 0.09), rgba(255, 255, 255, 0.025) 42%, rgba(37, 99, 235, 0.10));
  box-shadow:
    inset 2px -2px 1px -1px rgba(255, 255, 255, 0.26),
    inset -2px 2px 1px -1px rgba(255, 255, 255, 0.18),
    inset 0 0 1px rgba(0, 0, 0, 0.44);
}

@media (max-width: 640px) {
  .mode-tabs {
    width: 100%;
    max-width: 100%;
    padding: 6px;
    gap: 8px;
  }

  .mode-tab {
    flex: 1 1 0;
    min-width: 0;
    padding: 10px 6px;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    text-align: center;
    font-size: 12px;
    line-height: 1.15;
  }

  .mode-icon { font-size: 18px; }
}

/* Card Header Actions */
.card-header-actions {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 10px;
}

.quickgen-switch {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px;
  border-radius: 999px;
  border: 1px solid var(--border-color);
  background: rgba(0, 0, 0, 0.22);
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.02);
}
.quickgen-option {
  border: none;
  background: transparent;
  color: var(--text-sub);
  font-size: 12px;
  font-weight: 700;
  padding: 7px 10px;
  border-radius: 999px;
  cursor: pointer;
  transition: transform 0.18s ease, background 0.18s ease, color 0.18s ease, box-shadow 0.18s ease;
  letter-spacing: 0.2px;
}
.quickgen-option:hover {
  background: rgba(255, 255, 255, 0.06);
  color: var(--text-main);
}
.quickgen-option.active {
  background: var(--primary-gradient);
  color: #fff;
  box-shadow: var(--shadow-glow);
}
.quickgen-switch.disabled {
  opacity: 0.55;
}
.quickgen-option:disabled {
  cursor: not-allowed;
}
.quickgen-option:disabled:hover {
  background: transparent;
  color: var(--text-sub);
  transform: none;
}

/* Quick Generate */
.quickgen-panel {
  margin-top: 16px;
  padding: 16px;
  border-radius: var(--radius-md);
  border: 1px solid rgba(99, 102, 241, 0.22);
  background:
    radial-gradient(circle at 20% 10%, rgba(99, 102, 241, 0.18), transparent 35%),
    radial-gradient(circle at 80% 0%, rgba(139, 92, 246, 0.14), transparent 40%),
    rgba(0, 0, 0, 0.18);
  box-shadow: var(--shadow-sm);
}
.quickgen-head {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 0;
}
.quickgen-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--text-main);
  letter-spacing: 0.2px;
}
.quickgen-subtitle {
  font-size: 12px;
  color: var(--text-sub);
}
.quickgen-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 14px;
}
.quickgen-icon {
  width: 92px;
  height: 92px;
  margin: 0 auto;
  border-radius: 18px;
  overflow: hidden;
  border: 1px dashed rgba(255, 255, 255, 0.18);
  background: rgba(0, 0, 0, 0.25);
  display: grid;
  place-items: center;
}
.quickgen-icon img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.quickgen-icon-fallback {
  width: 100%;
  height: 100%;
  display: grid;
  place-items: center;
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--text-sub);
  letter-spacing: 0.8px;
}
.quickgen-values {
  display: grid;
  grid-template-columns: 1fr;
  gap: 10px;
}
.quickgen-item {
  display: grid;
  grid-template-columns: 110px 1fr;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-color);
  background: rgba(0, 0, 0, 0.18);
}
.quickgen-item .k {
  font-size: 11px;
  color: var(--text-sub);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.quickgen-item .v {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-main);
  min-width: 0;
  justify-self: end;
  text-align: right;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.quickgen-item .v.tags {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 6px;
  white-space: normal;
  overflow: visible;
  text-overflow: unset;
}
.quickgen-tag {
  display: inline-flex;
  align-items: center;
  padding: 4px 8px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.06);
  color: var(--text-main);
  font-size: 11px;
  line-height: 1;
}
.quickgen-item .v.mono {
  font-family: var(--font-mono);
  font-weight: 500;
}

/* Panels */
.ad-config-panel,
.permissions-panel {
  background: rgba(0, 0, 0, 0.2);
  border-radius: var(--radius-md);
  padding: 16px;
  border: 1px solid var(--border-color);
  animation: slideDown 0.3s ease;
}

.task-compliance-panel {
  margin: 14px 0 10px;
  padding: 14px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
  background: rgba(0, 0, 0, 0.16);
}

.task-compliance-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--text-main);
  margin-bottom: 10px;
}

.task-compliance-ack {
  margin-bottom: 10px;
}

.task-compliance-counter {
  margin-top: 6px;
  font-size: 11px;
  color: var(--text-muted);
  text-align: right;
}

.code-preview {
  margin-top: 16px;
  background: #0d0d0d;
  border-radius: 8px;
  border: 1px solid var(--border-color);
  overflow: hidden;
}
.code-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: rgba(255, 255, 255, 0.05);
  border-bottom: 1px solid var(--border-color);
  font-size: 12px;
  color: var(--text-sub);
}
.code-content {
  margin: 0;
  padding: 12px;
  font-family: var(--font-mono);
  font-size: 11px;
  color: #a5b4fc;
  overflow-x: auto;
  white-space: pre-wrap;
  line-height: 1.5;
}

.permissions-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 10px;
  max-height: 300px;
  overflow-y: auto;
  padding: 4px;
}
.permission-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all 0.2s;
  user-select: none;
}
.permission-item:hover {
  border-color: var(--primary-start);
  background: var(--bg-hover);
}
.permission-item.active {
  background: rgba(99, 102, 241, 0.1);
  border-color: var(--primary-start);
}
.perm-check {
  width: 18px;
  height: 18px;
  border-radius: 4px;
  border: 1px solid var(--text-muted);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  color: white;
  background: var(--bg-input);
  transition: all 0.2s;
}
.permission-item.active .perm-check {
  background: var(--primary-gradient);
  border-color: transparent;
}
.perm-info { flex: 1; min-width: 0; }
.perm-name { font-size: 13px; font-weight: 500; color: var(--text-main); margin-bottom: 2px; }
.perm-key {
  font-size: 11px;
  color: var(--text-muted);
  font-family: var(--font-mono);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.pagination {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 16px;
}
.pagination .btn {
  white-space: nowrap;
}
.pagination .btn.active {
  background: var(--primary-gradient);
  color: #fff;
}

@keyframes slideDown {
  from { opacity: 0; transform: translateY(-10px); }
  to { opacity: 1; transform: translateY(0); }
}

.download-dropdown {
  position: relative;
  display: inline-flex;
  z-index: 80;
}

.download-dropdown .dropdown-trigger {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.download-dropdown .dropdown-caret {
  font-size: 10px;
  opacity: 0.8;
}

.download-dropdown .dropdown-menu {
  position: absolute;
  top: 100%;
  right: 0;
  margin-top: 6px;
  min-width: 140px;
  max-width: min(240px, calc(100vw - 32px));
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-md);
  padding: 6px;
  display: none;
  z-index: 120;
}

.download-dropdown.open .dropdown-menu {
  display: block;
}

.download-dropdown .dropdown-item {
  display: block;
  padding: 6px 10px;
  border-radius: var(--radius-sm);
  color: var(--text-main);
  text-decoration: none;
  font-size: 12px;
  white-space: nowrap;
}

.download-dropdown .dropdown-item:hover {
  background: var(--bg-hover);
}

@media (max-width: 640px) {
  /* On mobile, open upward and align to the trigger's left to avoid viewport clipping. */
  .download-dropdown .dropdown-menu {
    top: auto;
    bottom: 100%;
    margin-top: 0;
    margin-bottom: 8px;
    left: 0;
    right: auto;
    max-width: calc(100vw - 32px);
  }
}

.keystore-upload {
  margin-bottom: 12px;
}

.keystore-upload-card {
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  background: var(--bg-surface);
  padding: 12px 14px;
  display: grid;
  gap: 10px;
}

.keystore-upload-main {
  display: flex;
  align-items: center;
  gap: 10px;
}

.keystore-icon {
  width: 32px;
  height: 32px;
  border-radius: 10px;
  background: rgba(99, 102, 241, 0.16);
  color: var(--primary-start);
  display: grid;
  place-items: center;
  font-size: 16px;
}

.keystore-meta {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.keystore-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-main);
}

.keystore-subtitle {
  font-size: 11px;
  color: var(--text-muted);
}

.keystore-upload-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.keystore-upload-actions .btn {
  background: rgba(255, 255, 255, 0.06);
  border-color: rgba(255, 255, 255, 0.18);
}

.keystore-upload-actions .btn:hover {
  background: rgba(255, 255, 255, 0.12);
}

.keystore-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  border-radius: 999px;
  background: rgba(16, 185, 129, 0.12);
  color: #34d399;
  font-size: 12px;
  border: 1px solid rgba(16, 185, 129, 0.2);
  width: fit-content;
}

.keystore-file-input {
  position: absolute;
  width: 1px;
  height: 1px;
  opacity: 0;
  pointer-events: none;
}

.form-hint.warning {
  margin-top: 6px;
  color: var(--warning-start);
  font-size: 12px;
}

.desktop-basic-grid,
.desktop-meta-grid {
  align-items: start;
}

.desktop-basic-grid {
  gap: 16px;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
}

.desktop-meta-grid {
  gap: 16px;
  grid-template-columns: repeat(auto-fit, minmax(min(180px, 100%), 1fr));
}

.desktop-basic-grid .form-group,
.desktop-meta-grid .form-group {
  min-width: 0;
  margin-bottom: 0;
}

.desktop-meta-grid .desktop-field-installer .form-label {
  white-space: normal;
}

.desktop-meta-grid .form-input,
.desktop-meta-grid .form-select {
  min-width: 0;
}

.desktop-meta-grid .desktop-port-group {
  grid-column: 1 / -1;
}

.desktop-meta-grid .desktop-port-row,
.desktop-meta-grid .desktop-port-group .form-hint,
.desktop-meta-grid .desktop-port-group .form-error {
  max-width: 420px;
}

.desktop-meta-grid .desktop-port-group .form-hint,
.desktop-meta-grid .desktop-port-group .form-error {
  line-height: 1.45;
}

.desktop-port-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.desktop-port-row .form-input {
  flex: 1 1 160px;
  min-width: 140px;
}

.desktop-port-row .btn {
  flex: 0 0 auto;
  white-space: nowrap;
}

.mobile-shell-active .desktop-meta-grid {
  grid-template-columns: 1fr;
  gap: 12px;
}

.mobile-shell-active .desktop-meta-grid .desktop-port-row {
  display: grid;
  grid-template-columns: 1fr;
  gap: 8px;
  max-width: 100%;
}

.mobile-shell-active .desktop-meta-grid .desktop-port-row .form-input,
.mobile-shell-active .desktop-meta-grid .desktop-port-row .btn {
  width: 100%;
  min-width: 0;
}

.mobile-shell-active .desktop-meta-grid .desktop-port-row .btn {
  justify-content: center;
  white-space: normal;
}

@media (max-width: 640px) {
  .desktop-basic-grid,
  .desktop-meta-grid {
    grid-template-columns: 1fr;
    gap: 12px;
  }

  .desktop-meta-grid .desktop-field-installer .form-label {
    white-space: normal;
  }

  .desktop-meta-grid .desktop-port-row,
  .desktop-meta-grid .desktop-port-group .form-hint,
  .desktop-meta-grid .desktop-port-group .form-error {
    max-width: 100%;
  }
}

.keystore-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.mobile-page-head,
.mobile-bottom-nav {
  display: none;
}

.mobile-header-theme-btn {
  display: none;
}

.mobile-header-star-btn {
  display: none;
}

.mobile-header-star-count {
  display: none;
}

.header {
  position: relative;
}

.header-auth-inline {
  display: inline-flex;
  align-items: center;
}

.auth-entry-btn {
  min-height: 36px;
  min-width: 112px;
  padding: 7px 13px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border: 1px solid var(--glass-border-muted);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.42);
  color: var(--text-main);
  box-shadow: 0 1px 0 var(--glass-highlight) inset;
  cursor: pointer;
  font-size: 13px;
  font-weight: 750;
  line-height: 1;
  white-space: nowrap;
  transition: all 0.2s ease;
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
}

.auth-entry-btn:hover {
  background: rgba(255, 255, 255, 0.62);
  border-color: var(--glass-border);
  transform: translateY(-1px);
}

.auth-entry-dot {
  width: 7px;
  height: 7px;
  border-radius: 999px;
  background: var(--success-gradient);
  box-shadow: 0 0 0 4px rgba(24, 168, 102, 0.12);
}

.auth-user-chip {
  display: inline-flex;
  align-items: center;
  border: 1px solid var(--glass-border-muted);
  background: rgba(255, 255, 255, 0.46);
  border-radius: 999px;
  overflow: hidden;
  box-shadow: 0 1px 0 var(--glass-highlight) inset;
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
}

.auth-user-main,
.auth-user-logout {
  border: none;
  background: transparent;
  color: var(--text-main);
  cursor: pointer;
  padding: 7px 12px;
  font-size: 12px;
  line-height: 1.2;
}

.auth-user-main {
  max-width: 190px;
}

.auth-user-email {
  display: inline-block;
  max-width: 166px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  vertical-align: middle;
}

.auth-user-logout {
  border-left: 1px solid rgba(148, 163, 184, 0.28);
  color: var(--error-start);
}

html:not(.light-theme) .auth-entry-btn,
html:not(.light-theme) .auth-user-chip {
  background: rgba(28, 43, 66, 0.58);
}

.auth-overlay {
  position: fixed;
  inset: 0;
  z-index: 1200;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  background: radial-gradient(circle at 20% 10%, rgba(99, 102, 241, 0.22), transparent 42%), rgba(2, 6, 23, 0.72);
  backdrop-filter: blur(8px);
}

.auth-dialog {
  width: min(460px, calc(100vw - 32px));
  border-radius: 20px;
  border: 1px solid rgba(129, 140, 248, 0.3);
  background:
    radial-gradient(circle at 100% 0%, rgba(56, 189, 248, 0.18), transparent 40%),
    radial-gradient(circle at 0% 100%, rgba(129, 140, 248, 0.14), transparent 38%),
    var(--bg-card);
  box-shadow: 0 24px 56px rgba(2, 6, 23, 0.55);
  overflow: hidden;
}

.auth-dialog-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px 8px;
}

.auth-dialog-title {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-main);
}

.auth-close-btn {
  border: none;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  font-size: 18px;
}

.auth-tabs {
  display: flex;
  margin: 0 20px 14px;
  padding: 4px;
  border-radius: 999px;
  border: 1px solid var(--border-color);
  background: rgba(148, 163, 184, 0.08);
}

.auth-tab {
  flex: 1;
  border: none;
  border-radius: 999px;
  background: transparent;
  color: var(--text-sub);
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
  padding: 8px 12px;
  transition: all 0.2s ease;
}

.auth-tab.active {
  color: #fff;
  background: var(--primary-gradient);
}

.auth-login-methods {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  margin-bottom: 12px;
}

.auth-method-btn {
  height: 34px;
  border: 1px solid var(--border-color);
  border-radius: 10px;
  background: rgba(148, 163, 184, 0.08);
  color: var(--text-sub);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.auth-method-btn.active {
  color: #fff;
  border-color: transparent;
  background: var(--primary-gradient);
}

.auth-dialog-body {
  padding: 0 20px 8px;
}

.auth-input {
  height: 42px;
}

.auth-sms-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 8px;
}

.auth-sms-btn {
  min-width: 120px;
}

.auth-error {
  margin-top: 4px;
}

.auth-oauth-wrap {
  padding: 0 20px 8px;
}

.auth-oauth-divider {
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--text-muted);
  font-size: 12px;
  margin-bottom: 10px;
}

.auth-oauth-divider::before,
.auth-oauth-divider::after {
  content: '';
  flex: 1;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(148, 163, 184, 0.4), transparent);
}

.auth-github-btn {
  width: 100%;
  border: 1px solid rgba(148, 163, 184, 0.36);
  border-radius: 12px;
  background: linear-gradient(135deg, rgba(15, 23, 42, 0.88), rgba(30, 41, 59, 0.78));
  color: var(--text-main);
  height: 44px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: transform 0.2s ease, border-color 0.2s ease, background 0.2s ease;
}

.auth-github-btn:hover {
  transform: translateY(-1px);
  border-color: rgba(129, 140, 248, 0.45);
  background: linear-gradient(135deg, rgba(30, 41, 59, 0.92), rgba(51, 65, 85, 0.84));
}

.auth-github-btn:disabled {
  opacity: 0.66;
  cursor: not-allowed;
  transform: none;
}

.auth-github-mark {
  width: 22px;
  height: 22px;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: rgba(99, 102, 241, 0.22);
  border: 1px solid rgba(129, 140, 248, 0.36);
  font-size: 10px;
  letter-spacing: 0.3px;
}

.auth-dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 14px 20px 20px;
}

.auth-submit-btn {
  transform-origin: center;
}

.auth-submit-shake {
  animation: authSubmitShake 0.48s cubic-bezier(0.34, 1.56, 0.64, 1);
}

@keyframes authSubmitShake {
  0% {
    transform: translate3d(0, 0, 0) rotate(0deg);
  }
  15% {
    transform: translate3d(-6px, 0, 0) rotate(-2.5deg);
  }
  30% {
    transform: translate3d(6px, 0, 0) rotate(2.5deg);
  }
  45% {
    transform: translate3d(-5px, 0, 0) rotate(-1.8deg);
  }
  60% {
    transform: translate3d(5px, 0, 0) rotate(1.8deg);
  }
  75% {
    transform: translate3d(-3px, 0, 0) rotate(-1deg);
  }
  100% {
    transform: translate3d(0, 0, 0) rotate(0deg);
  }
}

.mobile-swipe-stage {
  width: 100%;
}

@keyframes mobilePageFade {
  from {
    transform: translateY(4px);
  }
  to {
    transform: translateY(0);
  }
}

@keyframes mobilePageSlideFromRight {
  from {
    transform: translateX(16px);
  }
  to {
    transform: translateX(0);
  }
}

@keyframes mobilePageSlideFromLeft {
  from {
    transform: translateX(-16px);
  }
  to {
    transform: translateX(0);
  }
}

@media (max-width: 640px) {
  .mobile-shell-active .header-content {
    position: relative;
  }

  .mobile-shell-active .mobile-header-star-btn,
  .mobile-shell-active .mobile-header-theme-btn {
    position: absolute;
    top: 50%;
    transform: translateY(-50%);
    height: 34px;
    border: none;
    background: transparent;
    -webkit-appearance: none;
    appearance: none;
    color: var(--text-main);
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 16px;
    line-height: 1;
    text-decoration: none;
    cursor: pointer;
    z-index: 2;
    outline: none;
    box-shadow: none;
    -webkit-tap-highlight-color: transparent;
    transition: opacity 0.2s ease, transform 0.15s ease;
  }

  .mobile-shell-active .mobile-header-star-btn {
    right: 56px;
    min-width: 34px;
    padding: 0 8px;
    gap: 4px;
    font-size: 13px;
    font-weight: 600;
  }

  .mobile-shell-active .mobile-header-star-count {
    display: inline;
    font-size: 11px;
    letter-spacing: -0.01em;
  }

  .mobile-shell-active .mobile-header-theme-btn {
    right: 16px;
    width: 34px;
    padding: 0;
  }

  .mobile-shell-active .mobile-header-star-btn:hover,
  .mobile-shell-active .mobile-header-theme-btn:hover {
    opacity: 0.85;
  }

  .mobile-shell-active .mobile-header-star-btn:focus,
  .mobile-shell-active .mobile-header-star-btn:focus-visible,
  .mobile-shell-active .mobile-header-theme-btn:focus,
  .mobile-shell-active .mobile-header-theme-btn:focus-visible {
    outline: none;
    box-shadow: none;
  }

  .mobile-shell-active .mobile-header-star-btn:active,
  .mobile-shell-active .mobile-header-theme-btn:active {
    transform: translateY(-50%) scale(0.96);
    box-shadow: none;
  }

  .mobile-shell-active .header {
    position: sticky;
    top: 0;
    z-index: 120;
    border-bottom-color: rgba(255, 255, 255, 0.1);
    backdrop-filter: blur(16px);
  }

  .mobile-shell-active .main {
    padding: 10px 0 calc(98px + env(safe-area-inset-bottom));
  }

  .mobile-main-container {
    padding-bottom: 12px;
  }

  .mobile-shell-active .mobile-swipe-stage {
    will-change: transform;
    touch-action: pan-y;
  }

  .mobile-page-head {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    justify-content: flex-start;
    margin: 2px 0 14px;
    padding: 16px;
    text-align: left;
    border-radius: 16px;
    border: 1px solid rgba(255, 255, 255, 0.08);
    background:
      radial-gradient(circle at 90% 0%, rgba(99, 102, 241, 0.28), transparent 45%),
      radial-gradient(circle at 0% 100%, rgba(14, 165, 233, 0.16), transparent 40%),
      var(--bg-card);
    box-shadow: 0 10px 28px rgba(0, 0, 0, 0.24);
  }

  .mobile-page-head-title {
    width: 100%;
    text-align: left;
    font-size: 20px;
    font-weight: 700;
    color: var(--text-main);
    letter-spacing: 0.2px;
  }

  .mobile-page-head-subtitle {
    width: 100%;
    text-align: left;
    margin-top: 4px;
    color: var(--text-sub);
    font-size: 12px;
  }

  .mobile-content-grid {
    gap: 14px;
  }

  .mobile-shell-active .mobile-page {
    backface-visibility: hidden;
    transform: translateZ(0);
  }

  .mobile-page-fade {
    animation: none;
  }

  .mobile-page-swipe-left {
    animation: mobilePageSlideFromRight 0.28s cubic-bezier(0.22, 1, 0.36, 1);
    will-change: transform;
  }

  .mobile-page-swipe-right {
    animation: mobilePageSlideFromLeft 0.28s cubic-bezier(0.22, 1, 0.36, 1);
    will-change: transform;
  }

  .mobile-shell-active .card {
    border-radius: 18px;
    box-shadow: 0 12px 28px rgba(0, 0, 0, 0.24);
    border-color: rgba(255, 255, 255, 0.08);
  }

  .mobile-shell-active .card:hover {
    transform: none;
  }

  .mobile-profile-announcement {
    border: 1px solid var(--border-color);
    border-radius: 14px;
    padding: 12px;
    margin-bottom: 14px;
    background: rgba(255, 255, 255, 0.04);
  }

  .mobile-profile-announcement-top {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .mobile-profile-announcement-icon {
    width: 24px;
    height: 24px;
    border-radius: 8px;
    display: grid;
    place-items: center;
    background: rgba(99, 102, 241, 0.18);
    color: #c7d2fe;
    font-size: 13px;
    flex-shrink: 0;
  }

  .mobile-profile-announcement-title {
    flex: 1;
    font-size: 13px;
    font-weight: 700;
    color: var(--text-main);
  }

  .mobile-profile-announcement-body {
    margin-top: 8px;
    font-size: 12px;
    line-height: 1.5;
    color: var(--text-sub);
  }

  .mobile-profile-actions {
    display: grid;
    gap: 10px;
    margin-bottom: 14px;
  }

  .mobile-action-item {
    width: 100%;
    border: 1px solid var(--border-color);
    border-radius: 14px;
    background: rgba(255, 255, 255, 0.04);
    color: var(--text-main);
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 12px 14px;
    font-size: 14px;
    cursor: pointer;
    text-decoration: none;
  }

  .mobile-action-item:active {
    transform: scale(0.99);
  }

  .mobile-action-icon {
    width: 28px;
    height: 28px;
    border-radius: 10px;
    display: grid;
    place-items: center;
    background: rgba(99, 102, 241, 0.18);
    color: #c7d2fe;
    font-size: 14px;
    flex-shrink: 0;
  }

  .mobile-action-text {
    flex: 1;
    text-align: left;
    font-weight: 600;
  }

  .mobile-action-arrow {
    color: var(--text-muted);
    font-size: 18px;
    line-height: 1;
  }

  .mobile-lang-card {
    border: 1px solid var(--border-color);
    border-radius: 14px;
    padding: 12px;
    background: rgba(255, 255, 255, 0.03);
  }

  .mobile-lang-title {
    font-size: 12px;
    color: var(--text-sub);
    margin-bottom: 10px;
  }

  .mobile-lang-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 8px;
  }

  .mobile-lang-item {
    border: 1px solid var(--border-color);
    border-radius: 10px;
    background: transparent;
    color: var(--text-sub);
    padding: 8px 6px;
    font-size: 12px;
    cursor: pointer;
  }

  .mobile-lang-item.active {
    background: var(--primary-gradient);
    color: #fff;
    border-color: transparent;
    font-weight: 600;
  }

  .mobile-bottom-nav {
    --mobile-nav-text: rgba(51, 65, 85, 0.86);
    --mobile-nav-active-text: #1d4ed8;
    --mobile-nav-active-icon: #2563eb;
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 0;
    position: fixed;
    left: 24px;
    right: 24px;
    bottom: calc(16px + env(safe-area-inset-bottom));
    min-height: 76px;
    padding: 7px 10px;
    border-radius: 999px;
    border: 2px solid rgba(255, 255, 255, 0.84);
    background:
      linear-gradient(90deg, rgba(255, 255, 255, 0.10), transparent 42%, rgba(255, 255, 255, 0.08)),
      rgba(248, 250, 252, 0.025);
    color: var(--mobile-nav-text);
    backdrop-filter: blur(3px) saturate(1.18) contrast(1.01) brightness(1.02);
    -webkit-backdrop-filter: blur(3px) saturate(1.18) contrast(1.01) brightness(1.02);
    box-shadow:
      0 18px 36px rgba(15, 23, 42, 0.10),
      0 8px 18px rgba(15, 23, 42, 0.08),
      inset 2px -2px 1px -1px rgba(255, 255, 255, 0.96),
      inset -2px 2px 1px -1px rgba(255, 255, 255, 0.92),
      inset 10px -10px 2px -10px rgba(255, 255, 255, 0.36),
      inset -10px 10px 2px -10px rgba(255, 255, 255, 0.38),
      inset 0 0 2px rgba(15, 23, 42, 0.12);
    overflow: hidden;
    isolation: isolate;
    z-index: 300;
  }

  .mobile-bottom-nav::before,
  .mobile-bottom-nav::after {
    content: "";
    position: absolute;
    pointer-events: none;
    z-index: 0;
  }

  .mobile-bottom-nav::before {
    top: 34%;
    left: 10px;
    right: 10px;
    bottom: 8px;
    border-radius: inherit;
    border: 1px solid rgba(15, 23, 42, 0.16);
    filter: blur(8px);
    opacity: 0.12;
  }

  .mobile-bottom-nav::after {
    inset: 0;
    border-radius: 999px;
    background:
      linear-gradient(45deg, rgba(255, 255, 255, 0.62) 0%, transparent 16%, transparent 82%, rgba(255, 255, 255, 0.48) 100%),
      linear-gradient(180deg, rgba(255, 255, 255, 0.08), transparent 32%, transparent);
    filter: blur(0.4px);
    opacity: 0.34;
  }

  .light-theme .mobile-bottom-nav {
    --mobile-nav-text: rgba(51, 65, 85, 0.86);
    --mobile-nav-active-text: #1d4ed8;
    --mobile-nav-active-icon: #2563eb;
    border-color: rgba(255, 255, 255, 0.84);
    background:
      linear-gradient(90deg, rgba(255, 255, 255, 0.10), transparent 42%, rgba(255, 255, 255, 0.08)),
      rgba(248, 250, 252, 0.025);
    box-shadow:
      0 18px 36px rgba(15, 23, 42, 0.10),
      0 8px 18px rgba(15, 23, 42, 0.08),
      inset 2px -2px 1px -1px rgba(255, 255, 255, 0.96),
      inset -2px 2px 1px -1px rgba(255, 255, 255, 0.92),
      inset 10px -10px 2px -10px rgba(255, 255, 255, 0.54),
      inset -10px 10px 2px -10px rgba(255, 255, 255, 0.58),
      inset 0 0 2px rgba(15, 23, 42, 0.18);
  }

  html:not(.light-theme) .mobile-bottom-nav {
    --mobile-nav-text: rgba(226, 232, 240, 0.86);
    --mobile-nav-active-text: #dbeafe;
    --mobile-nav-active-icon: #f8fafc;
    border-color: rgba(203, 213, 225, 0.28);
    background:
      linear-gradient(90deg, rgba(148, 163, 184, 0.055), rgba(15, 23, 42, 0.04) 42%, rgba(96, 165, 250, 0.055)),
      rgba(15, 23, 42, 0.10);
    box-shadow:
      0 24px 48px rgba(0, 0, 0, 0.40),
      0 10px 22px rgba(0, 0, 0, 0.20),
      inset 2px -2px 1px -1px rgba(255, 255, 255, 0.38),
      inset -2px 2px 1px -1px rgba(255, 255, 255, 0.28),
      inset 8px -8px 2px -8px rgba(255, 255, 255, 0.075),
      inset -8px 8px 2px -8px rgba(255, 255, 255, 0.075),
      inset 0 0 2px rgba(0, 0, 0, 0.48);
  }

  html:not(.light-theme) .mobile-bottom-nav::before {
    border-color: rgba(0, 0, 0, 0.34);
    opacity: 0.20;
  }

  html:not(.light-theme) .mobile-bottom-nav::after {
    background:
      linear-gradient(45deg, rgba(255, 255, 255, 0.16) 0%, transparent 18%, transparent 82%, rgba(255, 255, 255, 0.10) 100%),
      linear-gradient(180deg, rgba(226, 232, 240, 0.025), transparent 34%, transparent);
    opacity: 0.16;
  }

  .mobile-tab-btn {
    position: relative;
    z-index: 1;
    min-width: 0;
    min-height: 62px;
    border: 1px solid transparent;
    border-radius: 999px;
    background: transparent;
    outline: none;
    box-shadow: none;
    -webkit-tap-highlight-color: transparent;
    color: var(--mobile-nav-text);
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 5px;
    padding: 8px 4px 7px;
    cursor: pointer;
    overflow: visible;
    transition: color 0.2s ease, border-color 0.2s ease, background 0.2s ease, transform 0.18s ease, box-shadow 0.2s ease;
  }

  .mobile-tab-btn::before,
  .mobile-tab-btn::after {
    content: "";
    position: absolute;
    inset: 0;
    border-radius: inherit;
    pointer-events: none;
    opacity: 0;
    transition: opacity 0.2s ease;
  }

  .mobile-tab-btn::before {
    inset: 2px 4px;
    background:
      radial-gradient(circle at 54% 54%, rgba(148, 163, 184, 0.28), rgba(148, 163, 184, 0.13) 40%, transparent 68%),
      radial-gradient(circle at 48% 42%, rgba(255, 255, 255, 0.50), transparent 56%);
    filter: blur(0.25px);
  }

  .mobile-tab-btn::after {
    inset: 2px 4px;
    background:
      linear-gradient(45deg, rgba(255, 255, 255, 0.78) 0%, transparent 21%, transparent 76%, rgba(255, 255, 255, 0.72) 100%),
      linear-gradient(180deg, rgba(255, 255, 255, 0.34), rgba(255, 255, 255, 0.07) 42%, rgba(226, 232, 240, 0.20));
    box-shadow:
      inset 2px -2px 1px -1px rgba(255, 255, 255, 0.92),
      inset -2px 2px 1px -1px rgba(255, 255, 255, 0.78),
      inset 0 0 1px rgba(15, 23, 42, 0.18);
    filter: blur(0.7px);
  }

  .mobile-tab-btn:focus,
  .mobile-tab-btn:focus-visible,
  .mobile-tab-btn:active {
    outline: none;
    box-shadow: none;
  }

  .mobile-tab-btn:active {
    transform: scale(0.97);
  }

  .mobile-tab-btn:active::before {
    opacity: 0.5;
  }

  .mobile-tab-btn.active {
    color: var(--mobile-nav-active-text);
    border-color: transparent;
    background: transparent;
    box-shadow: none;
  }

  .mobile-tab-btn.active::before,
  .mobile-tab-btn.active::after {
    opacity: 1;
  }

  .light-theme .mobile-tab-btn.active {
    border-color: transparent;
    background: transparent;
    box-shadow: none;
  }

  html:not(.light-theme) .mobile-tab-btn::before {
    background:
      radial-gradient(circle at 54% 54%, rgba(71, 85, 105, 0.42), rgba(30, 41, 59, 0.24) 40%, transparent 68%),
      radial-gradient(circle at 48% 42%, rgba(226, 232, 240, 0.24), transparent 56%);
    filter: blur(0.7px);
  }

  html:not(.light-theme) .mobile-tab-btn::after {
    background:
      linear-gradient(45deg, rgba(255, 255, 255, 0.34) 0%, transparent 22%, transparent 76%, rgba(255, 255, 255, 0.24) 100%),
      linear-gradient(180deg, rgba(226, 232, 240, 0.12), rgba(255, 255, 255, 0.035) 42%, rgba(37, 99, 235, 0.12));
    box-shadow:
      inset 2px -2px 1px -1px rgba(255, 255, 255, 0.34),
      inset -2px 2px 1px -1px rgba(255, 255, 255, 0.22),
      inset 0 0 1px rgba(0, 0, 0, 0.52);
  }

  .mobile-tab-icon {
    position: relative;
    z-index: 1;
    font-size: 23px;
    line-height: 1;
    filter: none;
  }

  .mobile-tab-btn.active .mobile-tab-icon {
    color: var(--mobile-nav-active-icon);
  }

  .mobile-tab-label {
    position: relative;
    z-index: 1;
    max-width: 100%;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: 11px;
    font-weight: 500;
    line-height: 1;
    text-shadow: none;
  }

  .mobile-tab-btn.active .mobile-tab-label {
    font-weight: 700;
  }

  html:not(.light-theme) .mobile-tab-label {
    text-shadow: 0 1px 2px rgba(0, 0, 0, 0.36);
  }

  .mobile-shell-active .cropper-overlay,
  .mobile-shell-active .logs-overlay,
  .mobile-shell-active .settings-overlay,
  .mobile-shell-active .donation-overlay,
  .mobile-shell-active .auth-overlay,
  .mobile-shell-active .html-editor-overlay,
  .mobile-shell-active .html-preview-overlay {
    align-items: flex-end;
    padding: 0;
    backdrop-filter: blur(4px);
  }

  .mobile-shell-active .cropper-dialog,
  .mobile-shell-active .logs-dialog,
  .mobile-shell-active .settings-dialog,
  .mobile-shell-active .donation-dialog,
  .mobile-shell-active .auth-dialog,
  .mobile-shell-active .html-editor-dialog,
  .mobile-shell-active .html-preview-dialog {
    width: 100vw;
    max-width: 100vw;
    max-height: 96dvh;
    height: 96dvh;
    border-radius: 18px 18px 0 0;
    border-left: none;
    border-right: none;
    border-bottom: none;
    animation: mobilePageFade 0.24s ease;
  }

  .mobile-shell-active .cropper-dialog-body,
  .mobile-shell-active .logs-dialog-body,
  .mobile-shell-active .settings-dialog-body,
  .mobile-shell-active .donation-dialog-body,
  .mobile-shell-active .auth-dialog-body,
  .mobile-shell-active .html-editor-dialog-body,
  .mobile-shell-active .html-preview-dialog-body {
    flex: 1;
    max-height: none;
  }
}

.build-payment-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}

.build-payment-actions .form-input {
  min-width: min(260px, 100%);
  flex: 1;
}

.build-payment-overlay {
  position: fixed;
  inset: 0;
  z-index: 1100;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: rgba(8, 11, 18, 0.72);
  backdrop-filter: blur(14px);
}

.build-payment-dialog {
  width: min(680px, 100%);
  max-height: min(86vh, 720px);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  border: 1px solid var(--border-color);
  border-radius: 24px;
  background:
    radial-gradient(circle at 12% 0%, rgba(255, 206, 94, 0.2), transparent 32%),
    radial-gradient(circle at 92% 10%, rgba(92, 196, 255, 0.16), transparent 34%),
    var(--card-bg);
  box-shadow: 0 24px 70px rgba(0, 0, 0, 0.34);
}

.build-payment-dialog-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
  padding: 22px 24px 14px;
  border-bottom: 1px solid var(--border-color);
}

.build-payment-dialog-header h3 {
  margin: 0 0 6px;
  font-size: 22px;
}

.build-payment-dialog-header p {
  margin: 0;
  color: var(--text-secondary);
  font-size: 14px;
}

.build-payment-close-btn {
  width: 34px;
  height: 34px;
  border: 1px solid var(--border-color);
  border-radius: 999px;
  color: var(--text-primary);
  background: rgba(255, 255, 255, 0.06);
  cursor: pointer;
}

.build-payment-dialog-body {
  padding: 22px 24px 24px;
  overflow: auto;
}

.build-payment-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
  gap: 14px;
}

.build-payment-plan {
  display: grid;
  gap: 10px;
  padding: 16px;
  border: 1px solid var(--border-color);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.055);
}

.build-payment-plan-name {
  font-weight: 700;
}

.build-payment-plan-price {
  font-size: 28px;
  line-height: 1;
  font-weight: 800;
  color: var(--primary-color);
}

.build-payment-plan-meta,
.build-payment-status,
.build-payment-warning,
.build-payment-error {
  color: var(--text-secondary);
  font-size: 13px;
}

.build-payment-warning {
  margin-bottom: 12px;
  padding: 10px 12px;
  border: 1px solid rgba(255, 196, 87, 0.34);
  border-radius: 12px;
  color: #f4b744;
  background: rgba(255, 196, 87, 0.1);
}

.build-payment-status {
  margin-top: 16px;
  display: grid;
  gap: 4px;
  padding: 12px;
  border: 1px solid var(--border-color);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.05);
}

.mobile-shell-active .build-payment-overlay {
  align-items: flex-end;
  padding: 0;
}

.mobile-shell-active .build-payment-dialog {
  width: 100vw;
  max-height: 88vh;
  border-radius: 24px 24px 0 0;
}
</style>
