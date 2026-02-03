<template>
  <div class="app" :class="{ 'light-theme': currentTheme === 'light' }">
    <!-- Header -->
    <header class="header">
      <div class="container header-content">
        <div class="logo">
          <div class="logo-icon">
            <img :src="appLogo" alt="logo" class="logo-icon-img" />
          </div>
          <div>
            <div class="logo-text">{{ t('header.title') }}</div>
            <div class="logo-subtitle">{{ t('header.subtitle') }}</div>
          </div>
        </div>


        <div class="header-actions no-drag">
          <!-- Theme -->
          <div class="theme-switch">
            <button
              class="btn btn-ghost btn-sm btn-icon no-drag"
              @click="toggleTheme"
              :title="currentTheme === 'dark' ? t('theme.light') : t('theme.dark')"
            >
              <span v-if="currentTheme === 'dark'">&#x2600;</span>
              <span v-else>&#x1F319;</span>
            </button>
          </div>

          <!-- Language -->
          <div class="lang-switch">
            <button class="btn btn-ghost btn-sm no-drag" @click="showLangMenu = !showLangMenu">
              <span class="action-icon">&#x1F310;</span>
              <span class="lang-label">{{ currentLangLabel }}</span>
            </button>
            <div class="lang-menu" v-if="showLangMenu">
              <button
                v-for="lang in languages"
                :key="lang.code"
                class="lang-item no-drag"
                :class="{ active: currentLang === lang.code }"
                @click="changeLanguage(lang.code)"
              >
                {{ lang.label }}
              </button>
            </div>
          </div>

          <button class="btn btn-primary btn-sm no-drag mobile-hide" @click="openDonation(false)">
            <span class="action-icon">&#x1F496;</span>
            <span class="action-label">{{ t('donation.button') }}</span>
          </button>
          <button class="btn btn-ghost btn-sm no-drag" @click="openSettings">
            <span class="action-icon">&#x1F41B;</span>
            <span class="action-label">{{ t('settings.title') }}</span>
          </button>

          <div class="window-controls no-drag" v-if="windowControlsAvailable">
            <button class="window-btn" @click="minimizeWindow" aria-label="Minimize">-</button>
            <button class="window-btn window-maximize" @click="toggleMaximizeWindow" aria-label="Maximize">
              {{ isMaximized ? '🗖' : '🗗' }}
            </button>
            <button class="window-btn window-close" @click="closeWindow" aria-label="Close">✕</button>
          </div>
        </div>
      </div>
    </header>

    <!-- Main Content -->
    <main class="main">
      <div class="container">
        <div v-if="activeAnnouncement" class="card no-drag" style="margin-bottom: 16px;">
          <div class="card-header">
            <div class="card-icon">📢</div>
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
        <div class="mode-tabs">
          <button class="mode-tab" :class="{ active: mode === 'convert' }" @click="mode = 'convert'; resetForm()">
            <span class="mode-icon">📦</span>
            {{ t('mode.apk') }}
          </button>
          <button class="mode-tab" :class="{ active: mode === 'web' }" @click="mode = 'web'; resetForm()">
            <span class="mode-icon">🌐</span>
            {{ t('mode.web') }}
          </button>
        </div>

        <!-- Steps -->
        <div class="steps">
          <div class="step" :class="{ active: currentStep === 1, completed: currentStep > 1 }">
            <div class="step-number">{{ currentStep > 1 ? '✓' : '1' }}</div>
            <div class="step-text">{{ mode === 'web' ? t('web.url') : t('steps.upload') }}</div>
          </div>
          <div class="step" :class="{ active: currentStep === 2, completed: currentStep > 2 }">
            <div class="step-number">{{ currentStep > 2 ? '✓' : '2' }}</div>
            <div class="step-text">{{ t('steps.configure') }}</div>
          </div>
          <div class="step" :class="{ active: currentStep === 3, completed: currentStep > 3 }">
            <div class="step-number">{{ currentStep > 3 ? '✓' : '3' }}</div>
            <div class="step-text">{{ t('steps.build') }}</div>
          </div>
        </div>

        <div class="grid grid-auto">
          <!-- Left -->
          <div class="stack">
            <!-- Guide (convert only) -->
            <div class="card" v-if="mode === 'convert'">
              <div class="card-header">
                <div class="card-icon">💡</div>
                <div>
                  <div class="card-title">{{ t('guide.title') }}</div>
                  <div class="card-subtitle">{{ t('guide.subtitle') }}</div>
                </div>
                <a
                  href="https://aistudio.google.com/apps"
                  target="_blank"
                  class="btn btn-primary btn-sm"
                  style="margin-left: auto; text-decoration: none;"
                >
                  {{ t('guide.openAiStudio') }} ↗
                </a>
              </div>
              <div class="guide-steps">
                <div class="guide-step">
                  <div class="guide-step-num">1</div>
                  <div class="guide-step-text">{{ t('guide.step1') }}</div>
                </div>
                <div class="guide-step-line"></div>
                <div class="guide-step">
                  <div class="guide-step-num">2</div>
                  <div class="guide-step-text">{{ t('guide.step2') }}</div>
                </div>
                <div class="guide-step-line"></div>
                <div class="guide-step">
                  <div class="guide-step-num">3</div>
                  <div class="guide-step-text">{{ t('guide.step3') }}</div>
                </div>
              </div>
              <div class="guide-tip">
                {{ t('guide.tips') }}
              </div>
            </div>

            <!-- Upload (convert only) -->
            <div class="card" v-if="mode === 'convert'">
              <div class="card-header">
                <div class="card-icon">📦</div>
                <div>
                  <div class="card-title">{{ t('upload.title') }}</div>
                  <div class="card-subtitle">{{ t('upload.subtitle') }}</div>
                </div>
              </div>

              <div
                class="upload-zone"
                :class="{ dragover: isDragging, 'has-file': uploadedFile }"
                @dragover.prevent="isDragging = true"
                @dragleave.prevent="isDragging = false"
                @drop.prevent="handleDrop"
              >
                <input
                  type="file"
                  class="file-input-overlay"
                  ref="fileInput"
                  @change="handleFileSelect"
                  accept=".zip"
                />

                <template v-if="!uploadedFile">
                  <div class="upload-icon">📁</div>
                  <div class="upload-text">{{ t('upload.dragDrop') }}</div>
                  <div class="upload-hint">{{ t('upload.hint') }}</div>
                </template>
                <template v-else>
                  <div class="upload-icon">✅</div>
                  <div class="upload-text">{{ t('upload.ready') }}</div>
                  <div class="upload-file-info">
                    <span class="upload-file-name">{{ uploadedFile.original_name }}</span>
                    <span class="upload-file-size">{{ formatFileSize(uploadedFile.size) }}</span>
                  </div>
                </template>

                <div v-if="uploadProgress > 0 && uploadProgress < 100" class="progress-bar" style="margin-top: 16px;">
                  <div class="progress-fill" :style="{ width: uploadProgress + '%' }"></div>
                </div>
              </div>
            </div>

            <!-- Web URL (web only) -->
            <div class="card" v-if="mode === 'web'">
              <div class="card-header">
                <div class="card-icon">🌐</div>
                <div>
                  <div class="card-title">{{ t('web.url') }}</div>
                  <div class="card-subtitle">{{ t('web.urlHint') }}</div>
                </div>
              </div>

              <div class="form-group">
                <input
                  type="url"
                  class="form-input"
                  :class="{ 'input-error': webUrlError }"
                  v-model="webUrl"
                  :placeholder="t('web.urlPlaceholder')"
                  @input="currentStep = webUrl && !webUrlError ? 2 : 1"
                />
                <div v-if="webUrlError" class="form-error">{{ webUrlError }}</div>
              </div>

              <div class="divider"></div>
              <label class="settings-checkbox" style="margin-bottom: 16px;">
                <input type="checkbox" v-model="enableAds" />
                {{ t('web.enableAds') }}
              </label>

              <div v-if="enableAds" class="ad-config-panel">
                <div class="settings-section-title" style="border: none; padding: 0;">
                  <span class="section-title-icon">📺</span>
                  {{ t('web.adConfig') }}
                </div>

                <div class="grid grid-2" style="margin-top: 16px;">
                  <div class="form-group">
                    <label class="form-label">{{ t('web.toponAppId') }} <span class="required">*</span></label>
                    <input type="text" class="form-input" v-model="adConfig.appId" placeholder="a60a..." />
                  </div>
                  <div class="form-group">
                    <label class="form-label">{{ t('web.toponAppKey') }} <span class="required">*</span></label>
                    <input type="text" class="form-input" v-model="adConfig.appKey" placeholder="a60a..." />
                  </div>
                </div>

                <div class="form-group">
                  <label class="form-label">{{ t('web.placementId') }} <span class="required">*</span></label>
                  <input type="text" class="form-input" v-model="adConfig.placementId" placeholder="b60a..." />
                </div>

                <div class="code-preview">
                  <div class="code-header">
                    <span>{{ t('web.jsIntegration') }}</span>
                    <button class="btn btn-ghost btn-sm" @click="copyJsCode">
                      {{ codeCopied ? t('web.codeCopied') : t('web.copyCode') }}
                    </button>
                  </div>
                  <pre class="code-content">{{ jsTemplate }}</pre>
                </div>
              </div>
            </div>

            <!-- App config -->
            <div class="card">
              <div class="card-header">
                <div class="card-icon">⚙️</div>
                <div>
                  <div class="card-title">{{ updatingTaskId ? t('config.updateTitle') : t('config.title') }}</div>
                  <div class="card-subtitle">
                    {{
                      updatingTaskId
                        ? t('config.updateSubtitle', { name: updatingTask?.config.app_name })
                        : t('config.subtitle')
                    }}
                  </div>
                </div>
                <button
                  v-if="updatingTaskId"
                  class="btn btn-ghost btn-sm"
                  @click="resetForm"
                  :title="t('config.cancelUpdate')"
                  style="margin-left: auto;"
                >
                  ✕ {{ t('config.cancelUpdate') }}
                </button>
              </div>

              <!-- Icon -->
              <div class="icon-upload-section">
                <div class="icon-upload">
                  <div class="icon-preview" :class="{ 'has-icon': appIcon }">
                    <input
                      type="file"
                      class="file-input-overlay"
                      ref="iconInput"
                      @change="handleIconSelect"
                      accept="image/png"
                    />
                    <img v-if="appIcon" :src="appIcon" alt="App Icon" />
                <div v-else class="icon-placeholder">
                      <span class="icon-placeholder-icon">🖼️</span>
                      <span class="icon-placeholder-text">{{ t('icon.uploadHint') }}</span>
                    </div>
                  </div>
                  <div class="icon-info">
                    <div class="icon-title">{{ t('icon.title') }} <span style="color: var(--error)">*</span></div>
                    <div class="icon-desc">{{ t('icon.requirements') }}</div>
                    <div v-if="iconError" class="icon-error">{{ iconError }}</div>
                  </div>
                </div>
              </div>

              <div class="divider"></div>

              <!-- Basic info -->
              <div class="grid grid-2">
                <div class="form-group">
                  <label class="form-label">
                    {{ t('config.appName') }} <span class="required">*</span>
                  </label>
                  <input
                    type="text"
                    class="form-input"
                    v-model="config.app_name"
                    :placeholder="t('config.appNamePlaceholder')"
                    :disabled="!!updatingTaskId"
                    :class="{ 'input-locked': updatingTaskId }"
                  />
                </div>
                <div class="form-group">
                  <label class="form-label">
                    {{ t('config.packageName') }} <span class="required">*</span>
                  </label>
                  <input
                    type="text"
                    class="form-input"
                    v-model="config.package_name"
                    :placeholder="t('config.packageNamePlaceholder')"
                    :disabled="!!updatingTaskId"
                    :class="{ 'input-locked': updatingTaskId, 'input-error': packageNameError }"
                  />
                  <div v-if="packageNameError" class="form-error">{{ packageNameError }}</div>
                </div>
              </div>



              <div class="grid grid-3">
                <div class="form-group">
                  <label class="form-label">{{ t('config.versionName') }}</label>
                  <input type="text" class="form-input" v-model="config.version_name" placeholder="1.0.0" />
                </div>
                <div class="form-group">
                  <label class="form-label">{{ t('config.versionCode') }}</label>
                  <input type="number" class="form-input" v-model.number="config.version_code" placeholder="1" :min="1" />
                </div>
                <div class="form-group">
                  <label class="form-label">{{ t('config.outputFormat') }}</label>
                  <select class="form-input form-select" v-model="config.output_format">
                    <option value="apk">{{ t('config.apk') }}</option>
                    <option value="aab">{{ t('config.aab') }}</option>
                  </select>
                </div>
              </div>

              <div class="divider"></div>

              <!-- APK style -->
              <div class="card-header" style="margin-bottom: 16px; padding: 0;">
                <div class="card-icon" style="width: 36px; height: 36px; font-size: 16px;">🎨</div>
                <div>
                  <div class="card-title" style="font-size: 15px;">{{ t('config.styleTitle') }}</div>
                </div>
              </div>

              <div class="grid grid-2">
                <div class="form-group">
                  <label class="form-label">{{ t('config.orientation') }}</label>
                  <select class="form-input form-select" v-model="config.orientation">
                    <option value="portrait">{{ t('config.orientationPortrait') }}</option>
                    <option value="landscape">{{ t('config.orientationLandscape') }}</option>
                    <option value="auto">{{ t('config.orientationAuto') }}</option>
                  </select>
                </div>
                <div class="form-group" style="display: flex; align-items: flex-end;">
                  <label class="settings-checkbox" style="margin-bottom: 12px;">
                    <input type="checkbox" v-model="config.double_click_exit" />
                    {{ t('config.doubleClickExit') }}
                  </label>
                </div>
              </div>

              <div class="form-group" style="margin-bottom: 12px;">
                <label class="settings-checkbox">
                  <input type="checkbox" v-model="config.status_bar_hidden" />
                  {{ t('config.statusBarHidden') }}
                </label>
              </div>

              <!-- Permissions -->
              <div class="divider"></div>

              <label class="settings-checkbox" style="margin-bottom: 16px;">
                <input type="checkbox" v-model="enablePermissions" />
                {{ t('config.enablePermissions') }}
              </label>

              <div v-if="enablePermissions" class="permissions-panel">
                <div class="card-header" style="margin-bottom: 16px; padding: 0; border: none;">
                  <div class="card-icon" style="width: 36px; height: 36px; font-size: 16px;">🛡️</div>
                  <div>
                    <div class="card-title" style="font-size: 15px;">{{ t('config.permissionsTitle') }}</div>
                    <div class="card-subtitle" style="font-size: 12px;">{{ t('config.permissionsHint') }}</div>
                  </div>
                </div>

                <div class="permissions-list">
                  <label
                    v-for="perm in permissionsList"
                    :key="perm"
                    class="permission-item"
                    :class="{ active: config.permissions.includes(perm) }"
                  >
                    <input type="checkbox" :value="perm" v-model="config.permissions" style="display: none;" />
                    <div class="perm-check">
                      {{ config.permissions.includes(perm) ? '✓' : '' }}
                    </div>
                    <div class="perm-info">
                      <div class="perm-name">{{ t('config.perm.' + perm) }}</div>
                      <div class="perm-key">{{ perm }}</div>
                    </div>
                  </label>
                </div>
              </div>

              <div class="divider"></div>

              <!-- Signing -->
              <div class="card-header" style="margin-bottom: 16px; padding: 0;">
                <div class="card-icon" style="width: 36px; height: 36px; font-size: 16px;">🔐</div>
                <div>
                  <div class="card-title" style="font-size: 15px;">{{ t('config.signConfig') }}</div>
                </div>

              </div>

              <div class="form-group keystore-upload">
                <label class="form-label">{{ t('config.keystoreUpload') }}</label>
                <div class="keystore-upload-card">
                  <input
                    ref="keystoreInput"
                    type="file"
                    class="keystore-file-input"
                    accept=".jks,.keystore"
                    @change="handleKeystoreSelect"
                    :disabled="isKeystoreUploaded || !!updatingTaskId"
                  />
                  <div class="keystore-upload-main">
                    <div class="keystore-icon">🔑</div>
                    <div class="keystore-meta">
                      <div class="keystore-title">{{ t('config.keystoreUpload') }}</div>
                      <div class="keystore-subtitle">.jks / .keystore</div>
                    </div>
                  </div>
                  <div class="keystore-upload-actions">
                    <button
                      class="btn btn-ghost btn-sm"
                      type="button"
                      @click="triggerKeystoreInput"
                      :disabled="isKeystoreUploaded || !!updatingTaskId"
                    >
                      {{ t('config.keystoreChoose') }}
                    </button>
                    <button
                      v-if="uploadedKeystore"
                      class="btn btn-ghost btn-sm"
                      type="button"
                      @click="clearKeystoreUpload"
                    >
                      {{ t('config.keystoreRemove') }}
                    </button>
                  </div>
                  <div v-if="uploadedKeystore" class="keystore-pill">
                    {{ uploadedKeystore.original_name }}
                  </div>
                </div>
                <div v-if="keystoreUploadError" class="form-error">{{ keystoreUploadError }}</div>
                <div v-if="isKeystoreUploaded" class="form-hint warning">
                  {{ t('config.keystoreUploadWarning') }}
                </div>
              </div>

              <div class="grid grid-3">

                <div class="form-group">
                  <label class="form-label">{{ t('config.keystoreAlias') }}</label>
                  <input type="text" class="form-input" v-model="config.keystore_alias" placeholder="key0" :disabled="isKeystoreUploaded" />
                </div>
                <div class="form-group">
                  <label class="form-label">{{ t('config.keystorePassword') }}</label>
                  <input
                    type="password"
                    class="form-input"
                    :class="{ 'input-error': keystorePasswordError }"
                    v-model="config.keystore_password"
                    placeholder="********"
                  />
                  <div v-if="keystorePasswordError" class="form-error">{{ keystorePasswordError }}</div>
                </div>
                <div class="form-group">
                  <label class="form-label">{{ t('config.keyPassword') }}</label>
                  <input
                    type="password"
                    class="form-input"
                    :class="{ 'input-error': keyPasswordError }"
                    v-model="config.key_password"
                    placeholder="********"
                  />
                  <div v-if="keyPasswordError" class="form-error">{{ keyPasswordError }}</div>
                </div>
              </div>

              <button
                class="btn btn-primary btn-lg"
                style="width: 100%; margin-top: 8px;"
                @click="createTask"
                :disabled="!canCreateTask || isCreating"
              >
                <span v-if="isCreating" class="spinner"></span>
                <span v-else>{{ updatingTaskId ? 'RETRY' : 'NEW' }}</span>
                {{ isCreating ? t('config.creating') : (updatingTaskId ? t('config.updateTask') : t('config.createTask')) }}
              </button>
            </div>
          </div>

          <!-- Right -->
          <div class="card">
            <div class="card-header">
              <div class="card-icon">📋</div>
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
              <div class="task-item" v-for="task in pagedTasks" :key="task.id">
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
                    v-if="task.status === 'pending'"
                    class="btn btn-primary btn-sm"
                    @click="startTask(task.id)"
                    :title="t('tasks.start')"
                  >
                    ▶
                  </button>
                  <span v-if="task.status === 'processing'" class="task-progress-badge">
                    {{ isQueuedTask(task) ? t('tasks.waiting') : `${task.progress}%` }}
                  </span>
                  <div v-if="task.status === 'success'" class="download-dropdown" :class="{ open: openDownloadMenu === task.id }">
                    <button
                      class="btn btn-primary btn-sm dropdown-trigger"
                      :title="t('tasks.downloadMenu')"
                      @click.stop="toggleDownloadMenu(task.id)"
                    >
                      <span class="action-icon">?</span>
                    </button>
                    <div v-if="openDownloadMenu === task.id" class="dropdown-menu">
                      <a class="dropdown-item" :href="getDownloadUrl(task.id)" @click="closeDownloadMenu">
                        {{ t('tasks.download') }}
                      </a>
                      <a class="dropdown-item" :href="getKeystoreUrl(task.id)" @click="closeDownloadMenu">
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
                    v-if="task.status === 'failed'"
                    class="btn btn-warning btn-sm"
                    @click="retryTask(task.id)"
                    :title="t('tasks.retry')"
                  >
                    🔄
                  </button>
                  <button
                    v-if="isCancelableTask(task) && task.status !== 'processing' && !isQueuedTask(task)"
                    class="btn btn-warning btn-sm"
                    @click="cancelTask(task.id)"
                    title="取消"
                  >
                    X
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

            <div v-else class="empty-state">
              <div class="empty-icon">📭</div>
              <div class="empty-text">{{ t('tasks.noTasks') }}</div>
              <div class="empty-hint">{{ t('tasks.createFirst') }}</div>
            </div>

            <div v-if="totalTaskPages > 1" class="pagination">
              <button class="btn btn-ghost btn-sm" :disabled="currentTaskPage <= 1" @click="goToTaskPage(currentTaskPage - 1)">
                ‹
              </button>
              <button
                v-for="page in taskPageNumbers"
                :key="page"
                class="btn btn-ghost btn-sm"
                :class="{ active: page === currentTaskPage }"
                @click="goToTaskPage(page)"
              >
                {{ page }}
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
        </div>
      </div>
    </main>

    <!-- Cropper dialog -->
    <Teleport to="body">
      <div v-if="showCropper" class="cropper-overlay" @click.self="closeCropper">
        <div class="cropper-dialog">
          <div class="cropper-dialog-header">
            <h3>✂️ {{ t('cropper.title') }}</h3>
            <button class="cropper-close-btn" @click="closeCropper">✕</button>
          </div>
          <div class="cropper-dialog-body">
            <Cropper
              ref="cropperRef"
              class="cropper-component"
              :src="cropperImageSrc"
              :stencil-props="{ aspectRatio: 1 }"
              :resize-image="{ adjustStencil: false }"
              image-restriction="stencil"
              :stencil-size="{ width: 400, height: 400 }"
              :canvas="{ width: 512, height: 512 }"
            />
          </div>
          <div class="cropper-dialog-footer">
            <div class="cropper-hint">{{ t('cropper.hint') }}</div>
            <div class="cropper-actions">
              <button class="btn btn-secondary btn-sm" @click="closeCropper">{{ t('cropper.cancel') }}</button>
              <button class="btn btn-primary btn-sm" @click="cropImage">{{ t('cropper.confirm') }}</button>
            </div>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- Logs dialog -->
    <Teleport to="body">
      <div v-if="showLogs" class="logs-overlay" @click.self="closeLogs">
        <div class="logs-dialog">
          <div class="logs-dialog-header">
            <h3>📋 {{ t('logs.title') }}</h3>
            <button class="logs-close-btn" @click="closeLogs">✕</button>
          </div>
          <div class="logs-dialog-body" ref="logsContainer">
            <div v-if="taskLogs.length === 0" class="logs-empty">{{ t('logs.noLogs') }}</div>
            <div v-else class="logs-content">
              <div
                v-for="(log, index) in taskLogs"
                :key="index"
                class="log-line"
                :class="{ 'log-error': log.includes('ERROR') || log.includes('错误'), 'log-success': log.includes('成功') || log.includes('完成') }"
              >
                {{ log }}
              </div>
            </div>
          </div>
          <div class="logs-dialog-footer">
            <button class="btn btn-secondary btn-sm" @click="refreshLogs">↻</button>
            <span class="logs-count">{{ taskLogs.length }}</span>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- Donation dialog -->
    <Teleport to="body">
      <div v-if="showDonation" class="donation-overlay" @click.self="closeDonation">
        <div class="donation-dialog">
          <div class="donation-dialog-header">
            <h3>💛 {{ t('donation.title') }}</h3>
            <button class="donation-close-btn" @click="closeDonation">✕</button>
          </div>
          <div class="donation-dialog-body">
            <div class="donation-message">{{ t('donation.message') }}</div>
            <div class="donation-sub">{{ t('donation.subMessage') }}</div>
            <div class="donation-qr-grid">
              <div class="donation-qr-card">
                <div class="donation-qr-title">{{ t('donation.alipay') }}</div>
                <img :src="alipayQr" alt="Alipay" class="donation-qr-image" />
              </div>
              <div class="donation-qr-card">
                <div class="donation-qr-title">{{ t('donation.wechat') }}</div>
                <img :src="wechatQr" alt="WeChat" class="donation-qr-image" />
              </div>
            </div>
          </div>
          <div class="donation-dialog-footer">
            <label class="settings-checkbox">
              <input type="checkbox" v-model="donationHideChecked" />
              {{ t('donation.hide') }}
            </label>
            <button class="btn btn-secondary btn-sm" @click="closeDonation">{{ t('settings.cancel') }}</button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- Settings -->
    <Teleport to="body">
      <div v-if="showSettings" class="settings-overlay" @click.self="closeSettings">
        <div class="settings-dialog">
          <div class="settings-dialog-header">
            <h3>{{ t('settings.title') }}</h3>
            <button class="settings-close-btn" @click="closeSettings">x</button>
          </div>

          <div class="settings-dialog-body">
            
            <div class="settings-section">
              <div class="settings-section-title">
                <span class="section-title-icon">💬</span>
                {{ t('settings.feedbackSection') }}
              </div>
              <div class="settings-hint">
                {{ t('settings.feedbackDevice', { cpu: deviceInfo.cpu || '-', cores: deviceInfo.cores || '-', ram: deviceInfo.ram || '-', os: deviceInfo.os || '-' }) }}
                <span class="recommend-spec">{{ t('settings.recommendedSpec') }}</span>
              </div>
              <div class="form-group">
                <textarea
                  class="form-input"
                  rows="3"
                  v-model="feedbackContent"
                  :placeholder="t('settings.feedbackPlaceholder')"
                ></textarea>
              </div>
              <div class="flex-row-center">
                <input
                  type="file"
                  multiple
                  accept="image/*"
                  ref="feedbackFileInput"
                  @change="handleFeedbackFiles"
                  v-show="false"
                />
                <button class="btn btn-secondary btn-sm" @click="triggerFeedbackFileSelect">
                  {{ t('settings.selectImages') }}
                </button>
                <div class="settings-hint" style="margin-left: 12px;">
                  {{ feedbackImages.length ? t('settings.imagesSelected', { count: feedbackImages.length }) : t('settings.noImagesSelected') }}
                </div>
                <button
                  class="btn btn-primary btn-sm ml-auto"
                  @click="submitFeedback"
                  :disabled="feedbackSubmitting"
                >
                  {{ feedbackSubmitting ? t('settings.feedbackSubmitting') : t('settings.feedbackSubmit') }}
                </button>
              </div>
              <div class="settings-hint">{{ t('settings.feedbackHint') }}</div>
            </div>
          </div>

          <div class="settings-dialog-footer">
            <button class="btn btn-secondary btn-sm" @click="closeSettings">{{ t('settings.cancel') }}</button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- Toast -->
    <Transition name="toast">
      <div v-if="toast.show" class="toast" :class="toast.type">
        <span>{{ toast.type === 'success' ? 'OK' : 'X' }}</span>
        <span>{{ toast.message }}</span>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { Cropper } from 'vue-advanced-cropper'
import 'vue-advanced-cropper/dist/style.css'
import * as api from './api'
import appLogo from './assets/icon.png'
const alipayQr = new URL('./pics/支付宝.png', import.meta.url).href
const wechatQr = new URL('./pics/微信.png', import.meta.url).href
import { messages, getSavedLanguage, saveLanguage, getSavedTheme, saveTheme, createI18n } from './i18n'

// Theme / Language
const currentTheme = ref(getSavedTheme())
const currentLang = ref(getSavedLanguage())
const showLangMenu = ref(false)
const openDownloadMenu = ref(null)
const languages = [
  { code: 'en', label: 'English' },
  { code: 'zh-CN', label: '简体中文' },
  { code: 'zh-TW', label: '繁體中文' }
]
const currentLangLabel = computed(() => {
  const lang = languages.find((l) => l.code === currentLang.value)
  return lang ? lang.label : 'Language'
})

const i18n = ref(createI18n(currentLang.value))
const t = (key, params) => i18n.value.t(key, params)

const applyTheme = (theme) => {
  if (theme === 'light') document.documentElement.classList.add('light-theme')
  else document.documentElement.classList.remove('light-theme')
}

const toggleTheme = () => {
  const newTheme = currentTheme.value === 'dark' ? 'light' : 'dark'
  currentTheme.value = newTheme
  saveTheme(newTheme)
  applyTheme(newTheme)
}

const changeLanguage = (lang) => {
  currentLang.value = lang
  saveLanguage(lang)
  i18n.value = createI18n(lang)
  showLangMenu.value = false
}

const toggleDownloadMenu = (taskId) => {
  openDownloadMenu.value = openDownloadMenu.value === taskId ? null : taskId
}
const closeDownloadMenu = () => {
  openDownloadMenu.value = null
}

const handleClickOutside = (e) => {
  if (!e.target.closest('.lang-switch')) showLangMenu.value = false
  if (!e.target.closest('.download-dropdown')) closeDownloadMenu()
}

// Modes & feature state
const mode = ref('convert') // convert | web
const webUrl = ref('')
const enableAds = ref(false)
const adConfig = ref({ appId: '', appKey: '', placementId: '' })
const enablePermissions = ref(false)
const codeCopied = ref(false)

const jsTemplate = `// 1. 定义广告API (h5api) - 需添加到您的网页中
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

const copyJsCode = () => {
  navigator.clipboard.writeText(jsTemplate).then(() => {
    codeCopied.value = true
    setTimeout(() => (codeCopied.value = false), 2000)
  })
}

const permissionsList = [
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
const normalizePermissionForUi = (permission) => {
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
const normalizePermissionsForUi = (permissions) => {
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

// Task flow
const currentStep = ref(1)
const isDragging = ref(false)
const fileInput = ref(null)
const iconInput = ref(null)
const keystoreInput = ref(null)
const uploadedKeystore = ref(null)
const keystoreUploadError = ref('')
const uploadedFile = ref(null)
const uploadProgress = ref(0)
const isCreating = ref(false)

// Tasks & queue
const tasks = ref([])
const queueStatus = ref({ queue_size: 0, running_count: 0, max_concurrent: 1 })
let pollInterval = null

// Settings
const showSettings = ref(false)
const announcements = ref([])
const deviceInfo = ref({ cpu: '', ram: '', os: '', cores: '' })
const feedbackContent = ref('')
const feedbackImages = ref([])
const feedbackFileInput = ref(null)
const feedbackSubmitting = ref(false)
const showDonation = ref(false)
const donationHideChecked = ref(false)
const donationAutoDisabled = ref(localStorage.getItem('apk_builder_donation_hide') === '1')
const previousVersionName = ref('')

// Logs
const showLogs = ref(false)
const taskLogs = ref([])
const currentLogTaskId = ref(null)
const logsContainer = ref(null)

// Update existing task
const updatingTaskId = ref(null)
const updatingTask = ref(null)

// Icon / Cropper
const appIcon = ref(null)
const appIconFile = ref(null)
const uploadedIcon = ref(null)
const iconError = ref('')
const showCropper = ref(false)
const cropperRef = ref(null)
const cropperImageSrc = ref('')

// Window controls (Electron)
const isMaximized = ref(false)
const windowControlsAvailable = computed(() => Boolean(window.windowControls))

const minimizeWindow = () => window.windowControls?.minimize?.()
const toggleMaximizeWindow = async () => {
  await window.windowControls?.toggleMaximize?.()
  if (window.windowControls?.isMaximized) {
    isMaximized.value = await window.windowControls.isMaximized()
  }
}
const closeWindow = () => window.windowControls?.close?.()

// Config
const config = ref({
  app_name: '',
  package_name: '',
  version_name: '1.0.0',
  version_code: 1,
  output_format: 'apk',
  orientation: 'portrait',
  double_click_exit: true,
  status_bar_hidden: false,
  status_bar_style: 'light',
  status_bar_color: 'transparent',
  permissions: ['INTERNET', 'ACCESS_NETWORK_STATE'],
  keystore_alias: '',
  keystore_password: '',
  key_password: ''
})

// Toast
const toast = ref({ show: false, type: 'success', message: '' })
const showToast = (message, type = 'success') => {
  toast.value = { show: true, type, message }
  setTimeout(() => (toast.value.show = false), 3000)
}

const isValidPackageName = (value) => {
  if (!value) return false
  const trimmed = String(value).trim()
  return /^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$/.test(trimmed)
}

const isValidUrl = (value) => {
  if (!value) return false
  try {
    const url = new URL(value)
    return url.protocol === 'http:' || url.protocol === 'https:'
  } catch {
    return false
  }
}

const isValidHostName = (value) => {
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

const isValidPort = (value) => {
  if (!value) return true
  const port = Number(value)
  return Number.isInteger(port) && port >= 1 && port <= 65535
}

const isValidWebUrl = (value) => {
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

const webUrlError = computed(() => {
  if (!webUrl.value) return ''
  return isValidWebUrl(webUrl.value) ? '' : t('web.validUrlError')
})

const packageNameError = computed(() => {
  if (!config.value.package_name) return ''
  return isValidPackageName(config.value.package_name) ? '' : t('config.packageNameRule')
})

const keystorePasswordError = computed(() => {
  const value = String(config.value.keystore_password || '')
  if (!value) return ''
  return value.length >= 6 ? '' : t('config.keystorePasswordRule')
})

const keyPasswordError = computed(() => {
  const value = String(config.value.key_password || '')
  if (!value) return ''
  return value.length >= 6 ? '' : t('config.keyPasswordRule')
})

const isKeystoreUploaded = computed(() => Boolean(uploadedKeystore.value))

const canCreateTask = computed(() => {
  const shouldCheckKeystore = !isKeystoreUploaded.value
  const common =
    config.value.app_name &&
    config.value.package_name &&
    !packageNameError.value &&
    (!shouldCheckKeystore || (!keystorePasswordError.value && !keyPasswordError.value)) &&
    (appIcon.value || uploadedIcon.value)

  if (mode.value === 'convert') {
    return common && uploadedFile.value
  }
  const basicWeb = common && webUrl.value && !webUrlError.value
  if (enableAds.value) {
    return basicWeb && adConfig.value.appId && adConfig.value.appKey && adConfig.value.placementId
  }
  return basicWeb
})

const resolveWebUrl = async (input) => {
  const raw = String(input || '').trim()
  if (!raw) return ''
  const hasScheme = /^https?:\/\//i.test(raw)
  const candidates = hasScheme ? [raw] : [`https://${raw}`, `http://${raw}`]
  for (const candidate of candidates) {
    try {
      const result = await api.probeUrl(candidate)
      if (result?.ok) return candidate
    } catch (_) {
      // ignore and try next
    }
  }
  return ''
}

const getTaskTime = (task) => task.updated_at || task.created_at
const sortedTasks = computed(() => (
  [...tasks.value].sort((a, b) => new Date(getTaskTime(b)) - new Date(getTaskTime(a)))
))
const taskPageSize = 10
const currentTaskPage = ref(1)
const totalTaskPages = computed(() => Math.max(1, Math.ceil(sortedTasks.value.length / taskPageSize)))
const pagedTasks = computed(() => {
  const start = (currentTaskPage.value - 1) * taskPageSize
  return sortedTasks.value.slice(start, start + taskPageSize)
})
const taskPageNumbers = computed(() => Array.from({ length: totalTaskPages.value }, (_, i) => i + 1))
const goToTaskPage = (page) => {
  const clamped = Math.max(1, Math.min(totalTaskPages.value, Number(page || 1)))
  currentTaskPage.value = clamped
}
const taskStats = computed(() => {
  const total = tasks.value.length
  const success = tasks.value.filter((t) => t.status === 'success').length
  return { total, success }
})

const dismissedAnnouncementId = ref(localStorage.getItem('apk_builder_announcement_id'))
const activeAnnouncement = ref(null)
const resolveActiveAnnouncement = () => {
  const dismissedId = dismissedAnnouncementId.value
  activeAnnouncement.value = announcements.value.find((item) => String(item.id) !== dismissedId) || null
}

// Helpers
const formatFileSize = (bytes) => {
  if (!bytes && bytes !== 0) return '-'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}
const formatDate = (dateStr) => {
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}
const parseVersionParts = (value) => {
  const raw = String(value || '').trim()
  if (!raw) return [0]
  return raw.split('.').map((part) => {
    const n = Number(part)
    return Number.isFinite(n) ? Math.max(0, Math.floor(n)) : 0
  })
}
const compareVersion = (a, b) => {
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
const bumpPatchVersion = (value) => {
  const parts = parseVersionParts(value)
  if (!parts.length) return '1.0.1'
  while (parts.length < 3) parts.push(0)
  parts[parts.length - 1] += 1
  return parts.join('.')
}
const getStatusText = (status) => {
  const map = { pending: t('status.pending'), processing: t('status.processing'), success: t('status.success'), failed: t('status.failed') }
  return map[status] || status
}
const getTaskIcon = (status) => {
  const map = { pending: '⏳', processing: '⚙️', success: '✅', failed: '❌' }
  return map[status] || '📦'
}
const getDownloadUrl = (taskId) => api.getDownloadUrl(taskId)
const getKeystoreUrl = (taskId) => api.getKeystoreUrl(taskId)
const isQueuedTask = (task) => {
  if (task?.status === 'pending') return true
  if (task?.status !== 'processing') return false
  return String(task?.message || '').includes('排队')
}
const isCancelableTask = (task) => task?.status === 'pending' || task?.status === 'processing'

// Upload
const triggerFileInput = () => fileInput.value?.click?.()
const handleFileSelect = async (event) => {
  const file = event.target.files[0]
  if (file) await uploadFile(file)
}
const handleDrop = async (event) => {
  isDragging.value = false
  const file = event.dataTransfer.files[0]
  if (file && file.name.endsWith('.zip')) await uploadFile(file)
  else showToast('请上传 ZIP 文件', 'error')
}
const uploadFile = async (file) => {
  try {
    uploadProgress.value = 0
    const result = await api.uploadFile(file, (progress) => (uploadProgress.value = progress))
    uploadedFile.value = result
    currentStep.value = 2
    showToast(t('toast.uploadSuccess'), 'success')
  } catch (error) {
    showToast(t('toast.uploadFailed') + ': ' + (error.response?.data?.detail || error.message), 'error')
  }
}

// Icon cropper flow
const handleIconSelect = async (event) => {
  const file = event.target.files[0]
  if (!file) return
  iconError.value = ''
  if (file.type !== 'image/png') {
    iconError.value = '请上传 PNG 格式的图片'
    return
  }
  cropperImageSrc.value = URL.createObjectURL(file)
  showCropper.value = true
}
const closeCropper = () => {
  showCropper.value = false
  if (cropperImageSrc.value) {
    URL.revokeObjectURL(cropperImageSrc.value)
    cropperImageSrc.value = ''
  }
  if (iconInput.value) iconInput.value.value = ''
}
const cropImage = async () => {
  if (!cropperRef.value) return
  const { canvas } = cropperRef.value.getResult()
  if (!canvas) return
  const outputCanvas = document.createElement('canvas')
  outputCanvas.width = 1024
  outputCanvas.height = 1024
  const ctx = outputCanvas.getContext('2d')
  ctx.drawImage(canvas, 0, 0, 1024, 1024)
  outputCanvas.toBlob(async (blob) => {
    if (!blob) return
    const croppedFile = new File([blob], 'logo.png', { type: 'image/png' })
    appIconFile.value = croppedFile
    if (appIcon.value && !appIcon.value.startsWith('/api/')) URL.revokeObjectURL(appIcon.value)
    appIcon.value = URL.createObjectURL(blob)
    try {
      const result = await api.uploadIcon(croppedFile)
      uploadedIcon.value = result
      showToast('图标设置成功', 'success')
    } catch (error) {
      showToast('图标上传失败: ' + (error.response?.data?.detail || error.message), 'error')
    }
    closeCropper()
  }, 'image/png', 1.0)
}

// Tasks
const refreshTasks = async () => {
  try {
    tasks.value = await api.getTasks()
    try {
      queueStatus.value = await api.getQueueStatus()
    } catch {
      // ignore
    }
  } catch (e) {
    // ignore
  }
}
const startPolling = () => {
  if (pollInterval) return
  pollInterval = setInterval(async () => {
    await refreshTasks()
    const hasProcessing = tasks.value.some((t) => t.status === 'processing')
    if (!hasProcessing) stopPolling()
  }, 2000)
}
const stopPolling = () => {
  if (pollInterval) {
    clearInterval(pollInterval)
    pollInterval = null
  }
}

const startTask = async (taskId) => {
  try {
    await api.startTask(taskId)
    showToast(t('toast.taskStarted'), 'success')
    await refreshTasks()
    startPolling()
  } catch (error) {
    showToast('启动失败: ' + (error.response?.data?.detail || error.message), 'error')
  }
}
const retryTask = async (taskId) => {
  try {
    await api.retryTask(taskId)
    showToast(t('toast.taskRetried'), 'success')
    await refreshTasks()
  } catch (error) {
    showToast('重试失败: ' + (error.response?.data?.detail || error.message), 'error')
  }
}
const cancelTask = async (taskId) => {
  if (!confirm('确定要取消这个任务吗？')) return
  try {
    await api.cancelTask(taskId)
    showToast('任务已取消', 'success')
    await refreshTasks()
  } catch (error) {
    showToast('取消失败: ' + (error.response?.data?.detail || error.message), 'error')
  }
}
const deleteTask = async (taskId) => {
  if (!confirm('确定要删除这个任务吗？')) return
  try {
    await api.deleteTask(taskId)
    showToast(t('toast.taskDeleted'), 'success')
    await refreshTasks()
  } catch (error) {
    showToast('删除失败: ' + (error.response?.data?.detail || error.message), 'error')
  }
}

const useTaskConfig = (task) => {
  updatingTaskId.value = task.id
  updatingTask.value = task

  mode.value = task.mode || 'convert'
  webUrl.value = task.web_url || ''
  enableAds.value = false
  adConfig.value = { appId: '', appKey: '', placementId: '' }

  const normalizedPermissions = normalizePermissionsForUi(task.config?.permissions || [])
  previousVersionName.value = task.config.version_name || '1.0.0'

  config.value = {
    ...config.value,
    app_name: task.config.app_name,
    package_name: task.config.package_name,
    version_name: bumpPatchVersion(task.config.version_name || '1.0.0'),
    version_code: (task.config.version_code || 1) + 1,
    output_format: task.config.output_format ?? 'apk',
    orientation: task.config.orientation ?? 'portrait',
    double_click_exit: task.config.double_click_exit ?? true,
    status_bar_hidden: task.config.status_bar_hidden ?? false,
    status_bar_style: task.config.status_bar_style ?? 'light',
    status_bar_color: task.config.status_bar_color ?? 'transparent',
    permissions: normalizedPermissions.length ? normalizedPermissions : ['INTERNET', 'ACCESS_NETWORK_STATE'],
    keystore_alias: task.config.keystore_alias || '',
    keystore_password: task.config.keystore_password || '',
    key_password: task.config.key_password || ''
  }

  enablePermissions.value = normalizedPermissions.length > 0

  if (task.icon_filename) {
    uploadedIcon.value = { filename: task.icon_filename, reused: true }
    appIcon.value = api.getIconUrl(task.id)
  } else {
    uploadedIcon.value = null
  uploadedKeystore.value = null
  keystoreUploadError.value = ''
  if (keystoreInput.value) keystoreInput.value.value = ''
    appIcon.value = null
  }
  uploadedKeystore.value = null
  keystoreUploadError.value = ''
  if (keystoreInput.value) keystoreInput.value.value = ''

  uploadedFile.value = { filename: 'project.zip', reused: true, original_name: '使用上一版本的项目文件', size: 0 }
  uploadProgress.value = 100
  currentStep.value = 1
}

// Create/Update task
const createTask = async () => {
  if (!canCreateTask.value) return
  if (packageNameError.value) {
    showToast(packageNameError.value, 'error')
    return
  }
  if (!isKeystoreUploaded.value && keystorePasswordError.value) {
    showToast(keystorePasswordError.value, 'error')
    return
  }
  if (!isKeystoreUploaded.value && keyPasswordError.value) {
    showToast(keyPasswordError.value, 'error')
    return
  }
  isCreating.value = true
  try {
    let normalizedWebUrl = webUrl.value
    if (mode.value === 'web') {
      normalizedWebUrl = await resolveWebUrl(webUrl.value)
      if (!normalizedWebUrl) {
        showToast(t('web.urlUnreachable'), 'error')
        return
      }
      if (normalizedWebUrl !== webUrl.value) {
        webUrl.value = normalizedWebUrl
      }
    }
  if (updatingTaskId.value) {
      if (compareVersion(config.value.version_name, previousVersionName.value) < 0) {
        showToast(t('toast.versionError'), 'error')
        return
      }
      const updateData = {
        filename: uploadedFile.value?.reused ? null : uploadedFile.value?.filename || null,
        icon_filename: uploadedIcon.value?.reused ? null : uploadedIcon.value?.filename || null,
        version_name: config.value.version_name,
        version_code: config.value.version_code,
        output_format: config.value.output_format,
        orientation: config.value.orientation,
        double_click_exit: config.value.double_click_exit,
        status_bar_hidden: config.value.status_bar_hidden,
        status_bar_style: config.value.status_bar_style,
        status_bar_color: config.value.status_bar_color,
        permissions: enablePermissions.value ? config.value.permissions : []
      }
      await api.updateTask(updatingTaskId.value, updateData)
      currentStep.value = 3
      showToast(`"${config.value.app_name}" 已更新至 v${config.value.version_name}`, 'success')
    } else {
      const taskData = {
        mode: mode.value,
        web_url: mode.value === 'web' ? normalizedWebUrl : null,
        ad_config: mode.value === 'web' && enableAds.value ? adConfig.value : null,
        filename: mode.value === 'convert' ? uploadedFile.value.filename : null,
        icon_filename: uploadedIcon.value?.filename || null,
        keystore_filename: uploadedKeystore.value?.filename || null,
        config: {
          app_name: config.value.app_name,
          package_name: config.value.package_name.trim(),
          version_name: config.value.version_name,
          version_code: config.value.version_code,
          output_format: config.value.output_format,
          orientation: config.value.orientation,
          double_click_exit: config.value.double_click_exit,
          status_bar_hidden: config.value.status_bar_hidden,
          status_bar_style: config.value.status_bar_style,
          status_bar_color: config.value.status_bar_color,
          permissions: enablePermissions.value ? config.value.permissions : [],
          keystore_alias: config.value.keystore_alias || null,
          keystore_password: config.value.keystore_password || null,
          key_password: config.value.key_password || null
        }
      }
      const created = await api.createTask(taskData)
      currentStep.value = 3
      showToast(t('toast.taskCreated'), 'success')
      try {
        await api.startTask(created.id)
        await refreshTasks()
        startPolling()
      } catch (error) {
        showToast('启动失败: ' + (error.response?.data?.detail || error.message), 'error')
      }
    }
    resetForm()
    await refreshTasks()
  } catch (error) {
    showToast('操作失败: ' + (error.response?.data?.detail || error.message), 'error')
  } finally {
    isCreating.value = false
  }
}

const resetForm = () => {
  webUrl.value = ''
  enableAds.value = false
  enablePermissions.value = false
  adConfig.value = { appId: '', appKey: '', placementId: '' }
  uploadedFile.value = null
  uploadProgress.value = 0
  if (appIcon.value && !appIcon.value.startsWith('/api/')) URL.revokeObjectURL(appIcon.value)
  appIcon.value = null
  appIconFile.value = null
  uploadedIcon.value = null
  uploadedKeystore.value = null
  keystoreUploadError.value = ''
  if (keystoreInput.value) keystoreInput.value.value = ''
  iconError.value = ''
  updatingTaskId.value = null
  updatingTask.value = null
  previousVersionName.value = ''
  config.value = {
    app_name: '',
    package_name: '',
    version_name: '1.0.0',
    version_code: 1,
    output_format: 'apk',
    orientation: 'portrait',
    double_click_exit: true,
    status_bar_hidden: false,
    status_bar_style: 'light',
    status_bar_color: 'transparent',
    permissions: ['INTERNET', 'ACCESS_NETWORK_STATE'],
    keystore_alias: '',
    keystore_password: '',
    key_password: ''
  }
  currentStep.value = 1
}

// Logs
const viewLogs = async (taskId) => {
  currentLogTaskId.value = taskId
  showLogs.value = true
  await refreshLogs()
}
const closeLogs = () => {
  showLogs.value = false
  currentLogTaskId.value = null
  taskLogs.value = []
}
const refreshLogs = async () => {
  if (!currentLogTaskId.value) return
  try {
    const result = await api.getTaskLogs(currentLogTaskId.value, 500)
    taskLogs.value = result.logs || []
    setTimeout(() => {
      if (logsContainer.value) logsContainer.value.scrollTop = logsContainer.value.scrollHeight
    }, 50)
  } catch {
    taskLogs.value = []
  }
}

// Settings
const openSettings = () => {
  showSettings.value = true
}

const closeSettings = () => (showSettings.value = false)
const fetchAnnouncements = async () => {
  try {
    const result = await api.getAdminAnnouncements()
    announcements.value = Array.isArray(result) ? result : (result?.items || [])
    resolveActiveAnnouncement()
  } catch {
    announcements.value = []
    resolveActiveAnnouncement()
  }
}

const dismissAnnouncement = () => {
  if (activeAnnouncement.value) {
    const id = String(activeAnnouncement.value.id)
    localStorage.setItem('apk_builder_announcement_id', id)
    dismissedAnnouncementId.value = id
    resolveActiveAnnouncement()
  }
}

const loadSystemInfo = async () => {
  try {
    const result = await api.getSystemInfo()
    deviceInfo.value = result || deviceInfo.value
  } catch {
    // ignore
  }
}

const triggerFeedbackFileSelect = () => {
  feedbackFileInput.value?.click?.()
}

const handleFeedbackFiles = (event) => {
  const files = Array.from(event.target.files || [])
  const maxSize = 10 * 1024 * 1024
  const filtered = files.filter((file) => file.size <= maxSize).slice(0, 5)
  if (filtered.length < files.length) {
    showToast(t('toast.feedbackFileLimit'), 'error')
  }
  feedbackImages.value = filtered
}

const submitFeedback = async () => {
  if (!feedbackContent.value) {
    showToast(t('toast.feedbackEmpty'), 'error')
    return
  }
  feedbackSubmitting.value = true
  try {
    await api.submitFeedback({
      client_id: api.getClientId(),
      content: feedbackContent.value,
      device_info: { ...deviceInfo.value },
      images: feedbackImages.value
    })
    feedbackContent.value = ''
    feedbackImages.value = []
    showToast(t('toast.feedbackSent'), 'success')
  } catch (error) {
    showToast(t('toast.feedbackFailed'), 'error')
  } finally {
    feedbackSubmitting.value = false
  }
}

const refreshAll = async () => {
  await refreshTasks()
  await fetchAnnouncements()
  await loadSystemInfo()
}

const openDonation = (fromAuto) => {
  if (fromAuto && donationAutoDisabled.value) return
  donationHideChecked.value = false
  showDonation.value = true
}
const closeDonation = () => {
  if (donationHideChecked.value) {
    localStorage.setItem('apk_builder_donation_hide', '1')
    donationAutoDisabled.value = true
  }
  showDonation.value = false
}
const taskStatusCache = ref(new Map())
const taskStatusReady = ref(false)
watch(
  tasks,
  (next) => {
    const prev = taskStatusCache.value
    const updates = new Map(prev)
    let newSuccess = null
    for (const task of next) {
      const prevStatus = prev.get(task.id)
      updates.set(task.id, task.status)
      if (taskStatusReady.value && task.status === 'success' && prevStatus !== 'success') {
        newSuccess = task
        break
      }
    }
    taskStatusCache.value = updates
    if (taskStatusReady.value && newSuccess && !showDonation.value) {
      openDonation(true)
    }
    taskStatusReady.value = true
  },
  { deep: true }
)

watch(sortedTasks, () => {
  if (currentTaskPage.value > totalTaskPages.value) {
    goToTaskPage(totalTaskPages.value)
  }
})

onMounted(async () => {
  applyTheme(currentTheme.value)
  document.addEventListener('click', handleClickOutside)
  await refreshTasks()
  await fetchAnnouncements()
  await loadSystemInfo()
  if (window.windowControls?.isMaximized) {
    try {
      isMaximized.value = await window.windowControls.isMaximized()
    } catch {
      // ignore
    }
  }
})

onUnmounted(() => {
  stopPolling()
  document.removeEventListener('click', handleClickOutside)
  if (appIcon.value && !appIcon.value.startsWith('/api/')) URL.revokeObjectURL(appIcon.value)
  if (cropperImageSrc.value) URL.revokeObjectURL(cropperImageSrc.value)
})
</script>

<style scoped>
.toast-enter-active,
.toast-leave-active {
  transition: all 0.3s ease;
}
.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translateY(20px);
}
</style>

<style>
/* Mode Tabs */
.mode-tabs {
  display: flex;
  gap: 16px;
  margin-bottom: 24px;
  background: var(--bg-surface);
  padding: 6px;
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-color);
  width: fit-content;
}
.mode-tab {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 24px;
  border-radius: var(--radius-md);
  border: none;
  background: transparent;
  color: var(--text-sub);
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}
.mode-tab:hover {
  color: var(--text-main);
  background: var(--bg-hover);
}
.mode-tab.active {
  background: var(--primary-gradient);
  color: white;
  box-shadow: var(--shadow-sm);
}
.mode-icon { font-size: 16px; }

/* Panels */
.ad-config-panel,
.permissions-panel {
  background: rgba(0, 0, 0, 0.2);
  border-radius: var(--radius-md);
  padding: 16px;
  border: 1px solid var(--border-color);
  animation: slideDown 0.3s ease;
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
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-md);
  padding: 6px;
  display: none;
  z-index: 10;
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
</style>
