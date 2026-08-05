<template>
          <div
            ref="tasksSection"
            class="card task-board-card mobile-page mobile-page-tasks"
            :class="isMobileShell ? mobilePageAnimClass : ''"
            v-show="!isMobileShell || mobileTab === 'tasks'"
          >
            <div class="card-header">
              <div class="card-icon">≡</div>
              <div>
                <div class="card-title">{{ t('tasks.title') }}</div>
                <div class="card-subtitle">{{ t('tasks.subtitle') }}</div>
              </div>
            </div>

            <div class="stats">
              <div class="stat-card">
                <div class="stat-value">{{ taskStats.total }}</div>
                <div class="stat-label">{{ t('tasks.total') }}</div>
              </div>
              <div class="stat-card">
                <div class="stat-value">{{ taskStats.success }}</div>
                <div class="stat-label">{{ t('tasks.completed') }}</div>
              </div>
              <div class="stat-card" v-if="queueStatus.queue_size > 0 || queueStatus.running_count > 0">
                <div class="stat-value queue-status">
                  <span class="running">{{ queueStatus.running_count }}</span>
                  <span class="queue-sep">/</span>
                  <span class="waiting">{{ queueStatus.queue_size }}</span>
                </div>
                <div class="stat-label">{{ t('tasks.running') }}/{{ t('tasks.queued') }}</div>
              </div>
            </div>

            <div class="task-list" v-if="tasks.length > 0">
              <div
                class="task-item"
                :class="{ 'task-item-menu-open': openDownloadMenu === task.id }"
                v-for="task in pagedTasks"
                :key="task.id"
              >
                <div class="task-icon">{{ getTaskIcon(task.status) }}</div>
                <div class="task-info">
                  <div class="task-name">{{ task.config.app_name }}</div>
                  <div class="task-meta">
                    {{ task.config.package_name }}  -  v{{ task.config.version_name || '1.0.0' }}  -  {{ formatDate(getTaskTime(task)) }}
                  </div>
                  <div
                    v-if="task.status === 'processing' && !isQueuedTask(task)"
                    class="progress-bar"
                    style="margin-top: 8px;"
                  >
                    <div class="progress-fill progress-active" :style="{ width: task.progress + '%' }"></div>
                  </div>
                </div>
                <div class="task-status" :class="task.status">{{ getStatusText(task.status) }}</div>
                <div class="task-actions">
                  <button
                    v-if="task.status === 'pending' && !isRiskReviewReleasedPendingTask(task)"
                    class="btn btn-primary btn-sm"
                    @click="startTask(task.id)"
                    :disabled="nativeAdRequesting"
                    :title="isRewardedBuildAdsEnabled ? t('tasks.rewardedStart') : t('tasks.start')"
                  >
                    ▶
                  </button>
                  <span v-if="task.status === 'processing'" class="task-progress-badge">
                    {{ isQueuedTask(task) ? t('tasks.waiting') : `${task.progress}%` }}
                  </span>
                  <div v-if="task.status === 'success' && (task.output_filename || (task.mode !== 'desktop' && task.keystore_filename))" class="download-dropdown" :class="{ open: openDownloadMenu === task.id }">
                    <button
                      class="btn btn-primary btn-sm dropdown-trigger"
                      :title="t('tasks.downloadMenu')"
                      @click.stop="toggleDownloadMenu(task.id)"
                    >
                      <span class="action-icon">&#x2B07;</span>
                    </button>
                    <div v-if="openDownloadMenu === task.id" class="dropdown-menu">
                      <a v-if="task.output_filename" class="dropdown-item" :href="getDownloadUrl(task.id)" @click.prevent="downloadTaskArtifact(task.id, 'apk')">
                        {{ t('tasks.download') }}
                      </a>
                      <a v-if="task.mode !== 'desktop' && task.keystore_filename" class="dropdown-item" :href="getKeystoreUrl(task.id)" @click.prevent="downloadTaskArtifact(task.id, 'signed')">
                        {{ t('tasks.downloadSigned') }}
                      </a>
                    </div>
                  </div>
                  <button
                    v-if="task.status === 'success' || isQueuedTask(task)"
                    class="btn btn-success btn-sm"
                    @click="useTaskConfig(task)"
                    :title="t('tasks.useConfig')"
                  >
                    🔄
                  </button>
                  <button
                    v-if="task.status === 'failed' || isRiskReviewReleasedPendingTask(task)"
                    class="btn btn-warning btn-sm"
                    @click="retryTask(task.id, { autoStart: isRiskReviewReleasedPendingTask(task) })"
                    :title="t('tasks.retry')"
                  >
                    🔄
                  </button>
                  <button
                    v-if="isCancelableTask(task) && task.status !== 'processing' && !isQueuedTask(task)"
                    class="btn btn-warning btn-sm"
                    @click="cancelTask(task.id)"
                    :title="t('tasks.cancel') || 'Cancel'"
                    :aria-label="t('tasks.cancel') || 'Cancel'"
                  >
                    <span aria-hidden="true">✕</span>
                  </button>
                  <button
                    v-if="task.status === 'processing' || task.status === 'failed' || task.status === 'success'"
                    class="btn btn-secondary btn-sm"
                    @click="viewLogs(task.id)"
                    :title="t('tasks.viewLogs')"
                  >
                    📋
                  </button>
                  <button
                    class="btn btn-ghost btn-sm"
                    @click="deleteTask(task.id)"
                    :title="t('tasks.delete')"
                    style="color: var(--error-start);"
                  >
                    ✕
                  </button>
                </div>
              </div>
            </div>

            <div v-else class="empty-state task-empty-state">
              <div class="empty-icon">＋</div>
              <div class="empty-text">{{ t('tasks.noTasks') }}</div>
              <div class="empty-hint">{{ t('tasks.createFirst') }}</div>
              <div class="task-empty-actions">
                <button class="btn btn-primary btn-sm" @click="openFirstTaskGuide">
                  {{ t('onboarding.primaryAction') }}
                </button>
                <a class="btn btn-secondary btn-sm" href="/help.html">
                  {{ t('onboarding.requirementsAction') }}
                </a>
              </div>
              <div class="task-empty-preview" :aria-label="t('onboarding.previewLabel')">
                <div class="task-empty-preview-icon">✓</div>
                <div class="task-empty-preview-main">
                  <div class="task-empty-preview-title">{{ t('onboarding.previewTitle') }}</div>
                  <div class="task-empty-preview-text">{{ t('onboarding.previewText') }}</div>
                </div>
                <div class="task-empty-preview-status">{{ t('onboarding.previewStatus') }}</div>
              </div>
            </div>

            <div v-if="totalTaskPages > 1" class="pagination">
              <button class="btn btn-ghost btn-sm" :disabled="currentTaskPage <= 1" @click="goToTaskPage(currentTaskPage - 1)">
                ‹
              </button>
              <button
                v-for="page in taskPageNumbers"
                :key="page.key"
                class="btn btn-ghost btn-sm"
                :class="{ active: page.type === 'page' && page.value === currentTaskPage }"
                :disabled="page.type !== 'page'"
                @click="page.type === 'page' && goToTaskPage(page.value)"
              >
                {{ page.value }}
              </button>
              <button
                class="btn btn-ghost btn-sm"
                :disabled="currentTaskPage >= totalTaskPages"
                @click="goToTaskPage(currentTaskPage + 1)"
              >
                ›
              </button>
            </div>
          </div>

          <div
            v-if="isMobileShell"
            ref="profileSection"
            class="card mobile-page mobile-page-profile"
            :class="isMobileShell ? mobilePageAnimClass : ''"
            v-show="mobileTab === 'profile'"
          >
            <div v-if="activeAnnouncement" class="mobile-profile-announcement">
              <div class="mobile-profile-announcement-top">
                <span class="mobile-profile-announcement-icon">&#x1F4D9;</span>
                <div class="mobile-profile-announcement-title">{{ t('announcement.title') }}</div>
                <button class="btn btn-ghost btn-sm no-drag" @click.stop="dismissAnnouncement">
                  {{ t('announcement.dismiss') }}
                </button>
              </div>
              <div class="mobile-profile-announcement-body">{{ activeAnnouncement.title }} - {{ activeAnnouncement.body }}</div>
            </div>

            <div class="mobile-profile-actions">
              <button class="mobile-action-item" @click="openSettings">
                <span class="mobile-action-icon">&#x1F4AC;</span>
                <span class="mobile-action-text">{{ t('settings.feedbackSection') }}</span>
                <span class="mobile-action-arrow">&#x203A;</span>
              </button>

              <button v-if="!isLoggedIn && isAuthEntryEnabled" class="mobile-action-item" @click="openAuthModal('login')">
                <span class="mobile-action-icon">&#x1F464;</span>
                <span class="mobile-action-text">{{ t('auth.entry') }}</span>
                <span class="mobile-action-arrow">&#x203A;</span>
              </button>
              <button v-else class="mobile-action-item" @click="logoutCurrentUser">
                <span class="mobile-action-icon">&#x1F513;</span>
                <span class="mobile-action-text">{{ t('auth.logout') }}</span>
                <span class="mobile-action-arrow">&#x203A;</span>
              </button>

              <button class="mobile-action-item" @click="openDonation(false)">
                <span class="mobile-action-icon">&#x1F496;</span>
                <span class="mobile-action-text">{{ t('donation.button') }}</span>
                <span class="mobile-action-arrow">&#x203A;</span>
              </button>

              <button v-if="isBuildPaymentModeEnabled" class="mobile-action-item" @click="openBuildPaymentModal">
                <span class="mobile-action-icon">￥</span>
                <span class="mobile-action-text">购买构建额度</span>
                <span class="mobile-action-arrow">&#x203A;</span>
              </button>

              <button class="mobile-action-item" @click="toggleTheme">
                <span v-if="currentTheme === 'dark'" class="mobile-action-icon">&#x2600;</span>
                <span v-else class="mobile-action-icon">&#x1F319;</span>
                <span class="mobile-action-text">{{ currentTheme === 'dark' ? t('theme.light') : t('theme.dark') }}</span>
                <span class="mobile-action-arrow">&#x203A;</span>
              </button>

              <a class="mobile-action-item" href="/help.html">
                <span class="mobile-action-icon">&#x2139;</span>
                <span class="mobile-action-text">{{ siteContent.nav.help }}</span>
                <span class="mobile-action-arrow">&#x203A;</span>
              </a>

              <a class="mobile-action-item" href="/privacy.html">
                <span class="mobile-action-icon">&#x1F512;</span>
                <span class="mobile-action-text">{{ siteContent.nav.privacy }}</span>
                <span class="mobile-action-arrow">&#x203A;</span>
              </a>
            </div>

            <div class="mobile-lang-card">
              <div class="mobile-lang-title">{{ mobileSettingsLabel }} - {{ currentLangLabel }}</div>
              <div class="mobile-lang-grid">
                <button
                  v-for="lang in languages"
                  :key="'mobile-lang-' + lang.code"
                  class="mobile-lang-item"
                  :class="{ active: currentLang === lang.code }"
                  @click="changeLanguage(lang.code)"
                >
                  {{ lang.label }}
                </button>
              </div>
            </div>
          </div>

          <AdSenseSlot
            v-if="!isMobileShell"
            slot-name="home_bottom"
            :label="siteContent.adLabel"
            :preview-text="siteContent.adPreview"
            :min-height="140"
            variant="wide"
          />
</template>

<script>
import { defineComponent } from 'vue'
import { useAppStateContext } from '../../app/appStateContext'
import AdSenseSlot from '../../components/AdSenseSlot.vue'

export default defineComponent({
  name: 'TaskWorkspace',
  components: { AdSenseSlot },
  setup() {
    return useAppStateContext()
  }
})
</script>
