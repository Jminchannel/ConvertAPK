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
        :aria-label="appBootLoadingTitle"
      >
        <div class="app-boot-panel">
          <div class="app-boot-orbit" aria-hidden="true">
            <span class="app-boot-ring app-boot-ring-a"></span>
            <span class="app-boot-ring app-boot-ring-b"></span>
            <span class="app-boot-spark app-boot-spark-a"></span>
            <span class="app-boot-spark app-boot-spark-b"></span>
            <span class="app-boot-spark app-boot-spark-c"></span>
            <span class="app-boot-core">
              <span class="app-boot-core-mark">&lt;/&gt;</span>
            </span>
          </div>
          <div class="app-boot-copy">
            <div class="app-boot-kicker">ConvertAPK</div>
            <div class="app-boot-title">{{ appBootLoadingTitle }}</div>
            <div class="app-boot-text">{{ appBootLoadingText }}</div>
          </div>
          <div class="app-boot-progress" aria-hidden="true">
            <span></span>
          </div>
        </div>
      </div>
    </Transition>

    <!-- Header -->
    <header class="header">
      <div class="container header-content">
        <div class="logo">
          <div>
            <div class="logo-text">{{ t('header.title') }}</div>
            <div class="logo-subtitle">{{ t('header.subtitle') }}</div>
          </div>
        </div>

        <a
          v-if="isMobileShell"
          class="mobile-header-star-btn no-drag"
          :href="githubRepoUrl"
          target="_blank"
          rel="noopener noreferrer"
          :title="t('github.starTitle')"
          :aria-label="t('github.starTitle')"
        >
          <span class="github-star-visual" aria-hidden="true">
            <span class="github-star-core">&#x2605;</span>
            <span class="github-star-orbit github-star-orbit-a"></span>
            <span class="github-star-orbit github-star-orbit-b"></span>
            <span class="github-star-spark github-star-spark-a"></span>
            <span class="github-star-spark github-star-spark-b"></span>
            <span class="github-star-spark github-star-spark-c"></span>
          </span>
          <span v-if="hasGithubStarCount" class="mobile-header-star-count">{{ githubStarCountText }}</span>
        </a>

        <button
          v-if="isMobileShell"
          class="mobile-header-theme-btn no-drag"
          @click="toggleTheme"
          :title="currentTheme === 'dark' ? t('theme.light') : t('theme.dark')"
          :aria-label="currentTheme === 'dark' ? t('theme.light') : t('theme.dark')"
        >
          <span v-if="currentTheme === 'dark'">&#x2600;</span>
          <span v-else>&#x1F319;</span>
        </button>


        <div class="header-actions no-drag">
          <!-- Theme -->
          <div v-if="!isMobileShell" class="theme-switch">
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
          <div v-if="!isMobileShell" class="lang-switch">
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

          <a
            v-if="!isMobileShell"
            class="btn btn-secondary btn-sm no-drag github-star-btn"
            :href="githubRepoUrl"
            target="_blank"
            rel="noopener noreferrer"
            :title="t('github.starTitle')"
            :aria-label="t('github.starTitle')"
          >
            <span class="github-star-visual" aria-hidden="true">
              <span class="github-star-core">&#x2605;</span>
              <span class="github-star-orbit github-star-orbit-a"></span>
              <span class="github-star-orbit github-star-orbit-b"></span>
              <span class="github-star-spark github-star-spark-a"></span>
              <span class="github-star-spark github-star-spark-b"></span>
              <span class="github-star-spark github-star-spark-c"></span>
            </span>
            <span class="action-label">{{ t('github.star') }}</span>
            <span v-if="hasGithubStarCount" class="github-star-count">{{ githubStarCountText }}</span>
          </a>

          <button class="btn btn-primary btn-sm no-drag mobile-hide" @click="openDonation(false)">
            <span class="action-icon">&#x1F496;</span>
            <span class="action-label">{{ t('donation.button') }}</span>
          </button>
          <button v-if="!isMobileShell" class="btn btn-ghost btn-sm no-drag" @click="openSettings">
            <span class="action-icon">&#9881;</span>
            <span class="action-label">{{ t('settings.title') }}</span>
          </button>
          <nav v-if="!isMobileShell" class="header-legal-links no-drag" :aria-label="siteContent.nav.help">
            <a href="/help.html">{{ siteContent.nav.help }}</a>
            <a href="/privacy.html">{{ siteContent.nav.privacy }}</a>
            <a href="/terms.html">{{ siteContent.nav.terms }}</a>
          </nav>
          <div v-if="!isMobileShell && (isLoggedIn || isAuthEntryEnabled)" class="header-auth-inline no-drag">
            <button
              v-if="!isLoggedIn && isAuthEntryEnabled"
              class="auth-entry-btn no-drag"
              @click="openAuthModal('login')"
            >
              <span class="auth-entry-dot" aria-hidden="true"></span>
              <span class="action-label">{{ t('auth.entry') }}</span>
            </button>
            <div v-else class="auth-user-chip no-drag">
              <button class="auth-user-main" @click="openAuthModal('login')">
                <span class="auth-user-email">{{ authDisplayName }}</span>
              </button>
              <button class="auth-user-logout" @click="logoutCurrentUser">{{ t('auth.logout') }}</button>
            </div>
          </div>
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
          <!-- Left -->
          <div class="stack mobile-page mobile-page-build" :class="isMobileShell ? mobilePageAnimClass : ''" v-show="!isMobileShell || mobileTab === 'build'">
            <!-- 新手引导 -->
            <div class="card starter-card" v-if="tasks.length === 0 && !updatingTaskId">
              <div class="starter-hero">
                <div class="starter-copy-wrap">
                  <div class="starter-kicker">{{ t('onboarding.kicker') }}</div>
                  <h2 class="starter-title">{{ t('onboarding.title') }}</h2>
                  <p class="starter-copy">{{ t('onboarding.subtitle') }}</p>
                </div>
                <button class="btn btn-primary btn-sm starter-cta" @click="openFirstTaskGuide">
                  <span class="action-icon" aria-hidden="true">↑</span>
                  {{ t('onboarding.primaryAction') }}
                </button>
              </div>

              <div class="starter-flow" :aria-label="t('onboarding.flowLabel')">
                <div class="starter-flow-item">
                  <div class="starter-flow-num">1</div>
                  <div>
                    <div class="starter-flow-title">{{ t('onboarding.stepUploadTitle') }}</div>
                    <div class="starter-flow-text">{{ t('onboarding.stepUploadText') }}</div>
                  </div>
                </div>
                <div class="starter-flow-item">
                  <div class="starter-flow-num">2</div>
                  <div>
                    <div class="starter-flow-title">{{ t('onboarding.stepConfigTitle') }}</div>
                    <div class="starter-flow-text">{{ t('onboarding.stepConfigText') }}</div>
                  </div>
                </div>
                <div class="starter-flow-item">
                  <div class="starter-flow-num">3</div>
                  <div>
                    <div class="starter-flow-title">{{ t('onboarding.stepBuildTitle') }}</div>
                    <div class="starter-flow-text">{{ t('onboarding.stepBuildText') }}</div>
                  </div>
                </div>
              </div>

              <div class="starter-materials">
                <div class="starter-materials-title">{{ t('onboarding.materialsTitle') }}</div>
                <div class="starter-chip-row">
                  <span class="starter-chip">{{ t('onboarding.materialZip') }}</span>
                  <span class="starter-chip">{{ t('onboarding.materialName') }}</span>
                  <span class="starter-chip">{{ t('onboarding.materialPackage') }}</span>
                  <span class="starter-chip">{{ t('onboarding.materialIcon') }}</span>
                </div>
              </div>
            </div>

            <!-- Guide (convert only) -->
            <div class="card guide-card" v-if="mode === 'convert'">
              <div class="card-header">
                <div class="card-icon">i</div>
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

            <!-- ZIP 上传（项目与桌面；原生 Android 由项目入口自动识别） -->
            <div class="card upload-card" v-if="mode === 'convert' || mode === 'desktop'" ref="convertUploadSection">
              <div class="card-header">
                <div class="card-icon">↑</div>
                <div>
                  <div class="card-title">{{ mode === 'desktop' ? t('upload.desktopTitle') : t('upload.title') }}</div>
                  <div class="card-subtitle">{{ mode === 'desktop' ? t('upload.desktopSubtitle') : t('upload.subtitle') }}</div>
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
                  <div class="upload-icon">↑</div>
                  <div class="upload-text">{{ mode === 'desktop' ? t('upload.desktopDragDrop') : t('upload.dragDrop') }}</div>
                  <div class="upload-hint">{{ mode === 'desktop' ? t('upload.desktopHint') : t('upload.hint') }}</div>
                </template>
                <template v-else>
                  <div class="upload-icon">✓</div>
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

            <!-- HTML Upload (html only) -->
            <div class="card upload-card" v-if="mode === 'html'" ref="htmlUploadSection">
              <div class="card-header">
                <div class="card-icon">&lt;/&gt;</div>
                <div>
                  <div class="card-title">{{ t('html.title') }}</div>
                  <div class="card-subtitle">{{ t('html.subtitle') }}</div>
                </div>
              </div>

              <div class="html-mode-switch">
                <button
                  class="html-mode-btn"
                  :class="{ active: htmlInputMode === 'file' }"
                  @click="setHtmlInputMode('file')"
                >
                  {{ t('html.modeFile') }}
                </button>
                <button
                  class="html-mode-btn"
                  :class="{ active: htmlInputMode === 'edit' }"
                  @click="setHtmlInputMode('edit')"
                >
                  {{ t('html.modeEdit') }}
                </button>
              </div>

              <div v-if="htmlInputMode === 'file'">
                <div
                  class="upload-zone"
                  :class="{ dragover: isHtmlDragging, 'has-file': uploadedHtmlFile }"
                  @dragover.prevent="isHtmlDragging = true"
                  @dragleave.prevent="isHtmlDragging = false"
                  @drop.prevent="handleHtmlDrop"
                >
                  <input
                    type="file"
                    class="file-input-overlay"
                    ref="htmlInput"
                    @change="handleHtmlSelect"
                    accept=".html,.htm"
                  />

                  <template v-if="!uploadedHtmlFile">
                    <div class="upload-icon">&lt;/&gt;</div>
                    <div class="upload-text">{{ t('html.dragDrop') }}</div>
                    <div class="upload-hint">{{ t('html.hint') }}</div>
                  </template>
                  <template v-else>
                    <div class="upload-icon">✓</div>
                    <div class="upload-text">{{ t('html.ready') }}</div>
                    <div class="upload-file-info">
                      <span class="upload-file-name">{{ uploadedHtmlFile.original_name }}</span>
                      <span class="upload-file-size">{{ formatFileSize(uploadedHtmlFile.size) }}</span>
                    </div>
                  </template>

                  <div v-if="htmlUploadProgress > 0 && htmlUploadProgress < 100" class="progress-bar" style="margin-top: 16px;">
                    <div class="progress-fill" :style="{ width: htmlUploadProgress + '%' }"></div>
                  </div>
                </div>
                <div v-if="uploadedHtmlFile" class="html-preview-inline-action">
                  <button class="btn btn-secondary btn-sm" @click="previewCurrentHtml">
                    {{ t('html.preview') }}
                  </button>
                </div>
              </div>

              <div v-else class="html-editor-panel">
                <div class="html-editor-toolbar">
                  <div class="html-editor-meta">
                    <div class="html-editor-title">{{ t('html.editorTitle') }}</div>
                  </div>
                  <div class="html-editor-actions">
                    <button class="btn btn-secondary btn-sm" @click="previewCurrentHtml">
                      {{ t('html.preview') }}
                    </button>
                    <button class="btn btn-ghost btn-sm" @click="openHtmlEditorModal">
                      {{ t('html.fullscreen') }}
                    </button>
                    <button class="btn btn-primary btn-sm" @click="saveEditorHtml" :disabled="!canSaveEditorHtml">
                      {{ t('html.editorSave') }}
                    </button>
                  </div>
                </div>

                <div v-if="isHtmlUploading" class="progress-bar">
                  <div class="progress-fill" :style="{ width: htmlUploadProgress + '%' }"></div>
                </div>

                <div v-if="!showHtmlEditorModal" class="html-editor-shell">
                  <div v-if="htmlEditorLoading" class="html-editor-loading">{{ t('html.editorLoading') }}</div>
                  <div class="html-editor-container" ref="htmlEditorContainer"></div>
                </div>
                <div v-else class="html-editor-inline-placeholder">
                  <div class="html-editor-inline-text">{{ t('html.editorModalOpen') }}</div>
                  <button class="btn btn-secondary btn-sm" @click="closeHtmlEditorModal">
                    {{ t('html.exitFullscreen') }}
                  </button>
                </div>

                <div class="html-editor-status-row">
                  <div class="html-editor-status" :class="{ dirty: htmlEditorDirty }">
                    {{ htmlEditorDirty || !hasSavedHtmlContent ? t('html.editorUnsaved') : t('html.editorSaved') }}
                  </div>
                  <div class="html-editor-issues" :class="{ 'has-issues': htmlEditorMarkers.length }">
                    {{ htmlEditorMarkers.length ? t('html.issues', { count: htmlEditorMarkers.length }) : t('html.noIssues') }}
                  </div>
                </div>

                <div v-if="htmlEditorMarkers.length" class="html-error-list">
                  <div
                    v-for="(marker, index) in htmlEditorMarkers"
                    :key="index"
                    class="html-error-item"
                    :class="isHtmlErrorMarker(marker) ? 'error' : 'warning'"
                    @click="revealHtmlMarker(marker)"
                  >
                    <span class="html-error-badge">{{ htmlMarkerLabel(marker) }}</span>
                    <span class="html-error-loc">L{{ marker.startLineNumber }}:{{ marker.startColumn }}</span>
                    <span class="html-error-msg">{{ marker.message }}</span>
                  </div>
                </div>
              </div>

            </div>

            <!-- Web URL (web only) -->
            <div class="card upload-card" v-if="mode === 'web'" ref="webUrlSection">
              <div class="card-header">
                <div class="card-icon">◎</div>
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
            <div class="card config-card">
              <div class="card-header">
                <div class="card-icon">⚙</div>
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
                <div class="card-header-actions">
                  <div
                    v-if="mode === 'convert' || mode === 'web' || mode === 'html'"
                    class="quickgen-switch"
                    :class="{ disabled: updatingTaskId }"
                    :title="t('config.quickGenerateHint')"
                  >
                    <button
                      type="button"
                      class="quickgen-option"
                      :class="{ active: !quickGenerate }"
                      :disabled="!!updatingTaskId"
                      @click="exitQuickGenerate"
                    >
                      {{ t('config.quickGenerateModeCustom') }}
                    </button>
                    <button
                      type="button"
                      class="quickgen-option"
                      :class="{ active: quickGenerate }"
                      :disabled="!!updatingTaskId"
                      @click="enterQuickGenerate"
                    >
                      {{ t('config.quickGenerateModeQuick') }}
                    </button>
                  </div>

                  <button
                    v-if="updatingTaskId"
                    class="btn btn-ghost btn-sm"
                    @click="resetForm"
                    :title="t('config.cancelUpdate')"
                  >
                  ✕ {{ t('config.cancelUpdate') }}
                </button>
                </div>
              </div>

              <div
                v-if="mode === 'convert' || mode === 'html'"
                class="cdn-localize-banner"
                :class="{ 'is-warning': cdnLocalizeAdvised }"
              >
                <div class="cdn-localize-banner-content">
                  <div class="cdn-localize-banner-title">{{ t('cdnLocalize.title') }}</div>
                  <div v-if="cdnScanLoading" class="cdn-localize-banner-subtitle">{{ t('cdnLocalize.scanning') }}</div>
                  <div v-else-if="hasCdnExternalLinks" class="cdn-localize-banner-subtitle">
                    {{ t('cdnLocalize.detected', { total: cdnLinkItems.length, selected: cdnSelectedCount }) }}
                  </div>
                  <div v-else class="cdn-localize-banner-subtitle">
                    {{ t('cdnLocalize.noLinks') }}
                  </div>
                </div>
                <div class="cdn-localize-banner-actions">
                  <label class="settings-checkbox" style="margin: 0;">
                    <input type="checkbox" v-model="cdnLocalizeEnabled" @change="handleCdnLocalizeEnabledChange" />
                    {{ t('cdnLocalize.enable') }}
                  </label>
                  <button class="btn btn-ghost btn-sm" @click="rescanExternalLinks({ openModal: false })" :disabled="cdnScanLoading">
                    {{ t('cdnLocalize.rescan') }}
                  </button>
                  <button class="btn btn-primary btn-sm" @click="openCdnLocalizeModal" :disabled="cdnScanLoading || !hasCdnExternalLinks">
                    {{ t('cdnLocalize.selectLinks') }}
                  </button>
                </div>
              </div>

              <div v-if="quickGenerate" class="quickgen-panel">
                <div class="quickgen-head">
                  <div class="quickgen-title">{{ t('config.quickGenerateEnabled') }}</div>
                  <div class="quickgen-subtitle">{{ t('config.quickGenerateDesc') }}</div>
                </div>
              </div>

              <template v-if="!quickGenerate">
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
                    <span class="icon-placeholder-icon">▧</span>
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
              <div class="grid grid-2" :class="{ 'desktop-basic-grid': mode === 'desktop' }">
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



              <div class="grid" :class="mode === 'desktop' ? 'desktop-meta-grid' : 'grid-3'">
                <div class="form-group desktop-field-version-name">
                  <label class="form-label">{{ t('config.versionName') }}</label>
                  <input type="text" class="form-input" v-model="config.version_name" placeholder="1.0.0" />
                </div>
                <div class="form-group desktop-field-version-code">
                  <label class="form-label">{{ t('config.versionCode') }}</label>
                  <input type="number" class="form-input" v-model.number="config.version_code" placeholder="1" :min="1" />
                  <div v-if="keystoreUpgradeVersionError" class="form-error">{{ keystoreUpgradeVersionError }}</div>
                  <div v-else-if="keystoreUpgradeVersionHint" class="form-hint">{{ keystoreUpgradeVersionHint }}</div>
                </div>
                <div v-if="mode !== 'desktop'" class="form-group">
                  <label class="form-label">{{ t('config.outputFormat') }}</label>
                  <select class="form-input form-select" v-model="config.output_format">
                    <option value="apk">{{ t('config.apk') }}</option>
                    <option value="aab">{{ t('config.aab') }}</option>
                  </select>
                </div>
                <div v-else class="form-group desktop-field-installer">
                  <label class="form-label">{{ t('config.desktopRuntime') }}</label>
                  <select class="form-input form-select" v-model="config.desktop_runtime">
                    <option value="tauri">tauri(推荐)</option>
                    <option value="electron">{{ t('config.desktopRuntimeElectron') }}</option>
                  </select>
                </div>
                <div v-if="mode === 'desktop'" class="form-group desktop-field-installer">
                  <label class="form-label">{{ t('config.desktopInstallerMode') }}</label>
                  <select class="form-input form-select" v-model="config.desktop_installer_mode">
                    <option value="portable">{{ t('config.desktopInstallerPortable') }}</option>
                  </select>
                </div>
                <div v-if="mode === 'desktop' && config.desktop_runtime !== 'tauri'" class="form-group desktop-port-group">
                  <label class="form-label">{{ t('config.desktopPort') }}</label>
                  <div class="desktop-port-row">
                    <input
                      type="number"
                      class="form-input"
                      v-model.number="config.desktop_port"
                      :placeholder="t('config.desktopPortPlaceholder')"
                      :min="1024"
                      :max="65535"
                      step="1"
                    />
                    <button type="button" class="btn btn-ghost btn-sm" @click="assignRandomDesktopPort">
                      {{ t('config.desktopPortRandom') }}
                    </button>
                  </div>
                  <div v-if="desktopPortError" class="form-error">{{ desktopPortError }}</div>
                  <div v-else class="form-hint">{{ t('config.desktopPortHint') }}</div>
                </div>
              </div>

              <template v-if="mode !== 'desktop'">
              <div class="divider"></div>

              <!-- APK style -->
              <div class="card-header" style="margin-bottom: 16px; padding: 0;">
                <div class="card-icon" style="width: 36px; height: 36px; font-size: 16px;">◇</div>
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

              <div class="grid grid-2" v-if="mode === 'html'">
                <div class="form-group">
                  <label class="form-label">{{ t('config.downloadMode') }}</label>
                  <select class="form-input form-select" v-model="config.download_mode">
                    <option value="silent">{{ t('config.downloadModeSilent') }}</option>
                    <option value="picker">{{ t('config.downloadModePicker') }}</option>
                  </select>
                </div>
                <div class="form-group">
                  <label class="form-label">{{ t('config.webFillMode') }}</label>
                  <select class="form-input form-select" v-model="config.web_fill_mode">
                    <option value="contain">{{ t('config.webFillModeContain') }}</option>
                    <option value="cover">{{ t('config.webFillModeCover') }}</option>
                  </select>
                </div>
              </div>

              <div class="grid grid-2" v-if="mode === 'web'">
                <div class="form-group">
                  <label class="form-label">{{ t('config.webviewUserAgent') }}</label>
                  <select class="form-input form-select" v-model="config.webview_user_agent">
                    <option value="android">{{ t('config.webviewUserAgentAndroid') }}</option>
                    <option value="pc">{{ t('config.webviewUserAgentPc') }}</option>
                  </select>
                </div>
              </div>

              <div class="grid grid-2 status-bar-settings" v-if="mode === 'convert' || mode === 'web' || mode === 'html'">
                <div class="form-group">
                  <label class="form-label">{{ t('config.statusBarColor') }}</label>
                  <div class="status-bar-color-row" :class="{ 'is-disabled': config.status_bar_hidden }">
                    <input
                      type="color"
                      class="status-bar-color-picker"
                      :value="statusBarColorPickerValue"
                      :disabled="config.status_bar_hidden"
                      @input="handleStatusBarColorPickerInput"
                    />
                    <input
                      type="text"
                      class="form-input status-bar-color-text"
                      v-model.trim="config.status_bar_color"
                      placeholder="#FFFFFF"
                      maxlength="9"
                      :disabled="config.status_bar_hidden"
                      @blur="normalizeStatusBarColorInput"
                    />
                  </div>
                  <div class="form-hint">
                    {{ config.status_bar_hidden ? t('config.statusBarColorHiddenHint') : t('config.statusBarColorHint') }}
                  </div>
                </div>
                <div class="form-group status-bar-toggle-group">
                  <label class="settings-checkbox">
                    <input type="checkbox" v-model="config.status_bar_hidden" />
                    {{ t('config.statusBarHidden') }}
                  </label>
                </div>
              </div>

              <!-- Permissions -->
              <div class="divider"></div>

              <label class="settings-checkbox" style="margin-bottom: 16px;">
                <input type="checkbox" v-model="enablePermissions" />
                {{ t('config.enablePermissions') }}
              </label>

              <div v-if="enablePermissions" class="permissions-panel">
                <div class="card-header" style="margin-bottom: 16px; padding: 0; border: none;">
                  <div class="card-icon" style="width: 36px; height: 36px; font-size: 16px;">✓</div>
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
                <div class="card-icon" style="width: 36px; height: 36px; font-size: 16px;">⌁</div>
                <div>
                  <div class="card-title" style="font-size: 15px;">{{ t('config.signConfig') }}</div>
                  <div class="card-subtitle" style="font-size: 12px; color: var(--text-muted);">{{ t('config.signConfigHint') }}</div>
                </div>

              </div>


              <label class="settings-checkbox keystore-toggle">
                <input type="checkbox" v-model="useCustomKeystore" :disabled="!!updatingTaskId" />
                {{ t('config.keystoreUploadToggle') }}
              </label>

              <div v-if="useCustomKeystore" class="form-group keystore-upload">
                <label class="form-label">{{ t('config.keystoreUpload') }}</label>
                <div class="keystore-upload-card">
                  <input
                    ref="keystoreInput"
                    type="file"
                    class="keystore-file-input"
                    id="keystore-file-input"
                    accept=".jks,.keystore"
                    @change="handleKeystoreSelect"
                    :disabled="isKeystoreUploaded || !!updatingTaskId"
                  />
                  <div class="keystore-upload-main">
                    <div class="keystore-icon">⌁</div>
                    <div class="keystore-meta">
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
                <div v-if="useCustomKeystore" class="form-hint">
                  {{ t('config.keystoreUpgradePackageHint') }}
                </div>
              </div>

              <div class="grid grid-3">

                <div class="form-group">
                  <label class="form-label">{{ t('config.keystoreAlias') }}</label>
                  <input
                    type="text"
                    class="form-input"
                    :class="{ 'input-locked': !!updatingTaskId }"
                    v-model="config.keystore_alias"
                    placeholder="key0"
                    :disabled="!!updatingTaskId"
                  />
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
              </template>

              </template>

              <div v-if="!updatingTaskId" class="task-compliance-panel">
                <div class="task-compliance-title">{{ t('config.taskComplianceTitle') }}</div>
                <label class="settings-checkbox task-compliance-ack">
                  <input type="checkbox" v-model="taskComplianceAck" />
                  {{ t('config.taskComplianceAckLabel') }}
                </label>
                <div v-if="taskComplianceError" class="form-error">{{ taskComplianceError }}</div>
              </div>

              <button
                class="btn btn-primary btn-lg"
                style="width: 100%; margin-top: 8px;"
                @click="createTask"
                :disabled="!canCreateTask || isCreating || nativeAdRequesting"
              >
                <span v-if="isCreating || nativeAdRequesting" class="spinner" aria-hidden="true"></span>
                <span v-else class="btn-badge" aria-hidden="true">{{ updatingTaskId ? t('tasks.retryBadge') : t('tasks.newBadge') }}</span>
                {{ nativeAdRequesting ? t('config.waitingRewardAd') : (isCreating ? t('config.creating') : (isRewardedBuildAdsEnabled ? t('config.rewardedBuildButton') : (updatingTaskId ? t('config.updateTask') : t('config.createTask')))) }}
              </button>
            </div>
          </div>

          <!-- Right -->
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

    <!-- 合规告知弹窗 -->
    <Teleport to="body">
      <div v-if="showComplianceNotice" class="compliance-overlay">
        <div class="compliance-dialog" role="dialog" aria-modal="true" aria-labelledby="compliance-title">
          <div class="compliance-dialog-header">
            <h3 id="compliance-title">{{ complianceNotice.title }}</h3>
          </div>
          <div class="compliance-dialog-body">
            <div class="compliance-effective">
              {{ complianceNotice.effectiveDateLabel }}: {{ complianceNotice.effectiveDate }}
            </div>
            <p class="compliance-intro">{{ complianceNotice.intro }}</p>
            <div
              v-for="(section, sectionIndex) in complianceNotice.sections"
              :key="section.title"
              class="compliance-section"
            >
              <div class="compliance-section-title">{{ section.title }}</div>
              <ul class="compliance-list">
                <li v-for="line in section.lines" :key="line">{{ line }}</li>
              </ul>
            </div>
            <div class="compliance-law">{{ complianceNotice.legalReferences }}</div>
          </div>
          <div class="compliance-dialog-footer">
            <button class="btn btn-secondary btn-sm" @click="rejectComplianceNotice">
              {{ complianceNotice.rejectButton }}
            </button>
            <button class="btn btn-primary btn-sm" @click="acceptComplianceNotice">
              {{ complianceNotice.acceptButton }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- Cropper dialog -->
    <Teleport to="body">
      <div
        v-if="showCropper"
        class="cropper-overlay"
        role="dialog"
        aria-modal="true"
        aria-labelledby="cropper-title"
        @click.self="closeCropper"
        @keydown.esc.stop="closeCropper"
        tabindex="-1"
      >
        <div class="cropper-dialog">
          <div class="cropper-dialog-header">
            <h3 id="cropper-title">✂️ {{ t('cropper.title') }}</h3>
            <button class="cropper-close-btn" @click="closeCropper" aria-label="Close">✕</button>
          </div>
          <div class="cropper-dialog-body">
            <Cropper
              ref="cropperRef"
              class="cropper-component"
              :src="cropperImageSrc"
              :stencil-props="cropperStencilProps"
              :resize-image="{ wheel: true, touch: true, adjustStencil: true }"
              :default-size="cropperDefaultSize"
              image-restriction="stencil"
              :min-width="96"
              :min-height="96"
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
      <div
        v-if="showLogs"
        class="logs-overlay"
        role="dialog"
        aria-modal="true"
        aria-labelledby="logs-title"
        @click.self="closeLogs"
        @keydown.esc.stop="closeLogs"
        tabindex="-1"
      >
        <div class="logs-dialog">
          <div class="logs-dialog-header">
            <h3 id="logs-title">📋 {{ t('logs.title') }}</h3>
            <button class="logs-close-btn" @click="closeLogs" aria-label="Close">✕</button>
          </div>
          <div class="logs-dialog-body" ref="logsContainer">
            <div v-if="logsLoading" class="logs-empty">{{ t('logs.loading') }}</div>
            <div v-else-if="taskLogs.length === 0" class="logs-empty">{{ t('logs.noLogs') }}</div>
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
            <div
              v-if="taskDiagnosisLoading || taskDiagnosisError || taskDiagnosis"
              class="diag-card"
            >
              <div class="diag-header">
                <div class="diag-title">🧠 {{ t('logs.aiTitle') }}</div>
                <button
                  class="btn btn-ghost btn-sm"
                  @click="rerunTaskDiagnosis"
                  :disabled="taskDiagnosisLoading"
                >
                  {{ t('logs.aiRerun') }}
                </button>
              </div>
              <div v-if="taskDiagnosisLoading" class="diag-loading">{{ t('logs.aiLoading') }}</div>
              <div v-else-if="taskDiagnosisError" class="diag-error">{{ taskDiagnosisError }}</div>
              <template v-else-if="taskDiagnosis && taskDiagnosis.status === 'running'">
                <div class="diag-loading">{{ t('logs.aiLoading') }}</div>
              </template>
              <template v-else-if="taskDiagnosis && taskDiagnosis.summary">
                <div class="diag-item">
                  <div class="diag-label">{{ t('logs.aiSummary') }}</div>
                  <div class="diag-value">{{ taskDiagnosis.summary }}</div>
                </div>
                <div class="diag-item" v-if="taskDiagnosis.reason">
                  <div class="diag-label">{{ t('logs.aiReason') }}</div>
                  <div class="diag-value">{{ taskDiagnosis.reason }}</div>
                </div>
                <div class="diag-item" v-if="taskDiagnosis.probable_causes && taskDiagnosis.probable_causes.length">
                  <div class="diag-label">{{ t('logs.aiCauses') }}</div>
                  <div class="diag-value">
                    <div
                      v-for="(cause, index) in taskDiagnosis.probable_causes"
                      :key="`cause_${index}`"
                      class="diag-line"
                    >
                      {{ index + 1 }}. {{ cause }}
                    </div>
                  </div>
                </div>
                <div class="diag-item" v-if="taskDiagnosis.suggestions && taskDiagnosis.suggestions.length">
                  <div class="diag-label">{{ t('logs.aiSolutions') }}</div>
                  <div class="diag-value">
                    <div
                      v-for="(suggestion, index) in taskDiagnosis.suggestions"
                      :key="`suggestion_${index}`"
                      class="diag-line"
                    >
                      {{ index + 1 }}. {{ suggestion }}
                    </div>
                  </div>
                </div>
                <div class="diag-meta">
                  <span>{{ t('logs.aiProvider') }}: {{ taskDiagnosis.provider || 'rule' }}</span>
                  <span v-if="taskDiagnosis.model">{{ t('logs.aiModel') }}: {{ taskDiagnosis.model }}</span>
                  <span v-if="typeof taskDiagnosis.confidence === 'number'">
                    {{ t('logs.aiConfidence') }}: {{ Math.round(taskDiagnosis.confidence * 100) }}%
                  </span>
                </div>
              </template>
              <div v-else class="diag-empty">{{ t('logs.aiEmpty') }}</div>
            </div>
          </div>
          <div class="logs-dialog-footer">
            <button class="btn btn-secondary btn-sm" @click="refreshLogs" :disabled="logsLoading">↻</button>
            <span class="logs-count">
              {{ taskLogs.length }}
              <template v-if="taskLogsHasMore && taskLogsTotal > taskLogs.length">/{{ taskLogsTotal }}</template>
            </span>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- HTML Editor dialog -->
    <Teleport to="body">
      <div
        v-if="showHtmlEditorModal"
        class="html-editor-overlay"
        role="dialog"
        aria-modal="true"
        aria-labelledby="html-editor-title"
        @click.self="closeHtmlEditorModal"
        @keydown.esc.stop="closeHtmlEditorModal"
        tabindex="-1"
      >
        <div class="html-editor-dialog">
          <div class="html-editor-dialog-header">
            <div id="html-editor-title" class="html-editor-dialog-title">{{ t('html.editorTitle') }}</div>
            <div class="html-editor-dialog-actions">
              <button class="btn btn-secondary btn-sm" @click="previewCurrentHtml">
                {{ t('html.preview') }}
              </button>
              <button class="btn btn-primary btn-sm" @click="saveEditorHtml" :disabled="!canSaveEditorHtml">
                {{ t('html.editorSave') }}
              </button>
              <button class="btn btn-secondary btn-sm" @click="closeHtmlEditorModal">
                {{ t('html.exitFullscreen') }}
              </button>
            </div>
          </div>
          <div class="html-editor-dialog-body">
            <div class="html-editor-shell">
              <div v-if="htmlEditorLoading" class="html-editor-loading">{{ t('html.editorLoading') }}</div>
              <div class="html-editor-container html-editor-modal" ref="htmlEditorModalContainer"></div>
            </div>

            <div class="html-editor-status-row">
              <div class="html-editor-status" :class="{ dirty: htmlEditorDirty }">
                {{ htmlEditorDirty || !hasSavedHtmlContent ? t('html.editorUnsaved') : t('html.editorSaved') }}
              </div>
              <div class="html-editor-issues" :class="{ 'has-issues': htmlEditorMarkers.length }">
                {{ htmlEditorMarkers.length ? t('html.issues', { count: htmlEditorMarkers.length }) : t('html.noIssues') }}
              </div>
            </div>

            <div v-if="htmlEditorMarkers.length" class="html-error-list">
              <div
                v-for="(marker, index) in htmlEditorMarkers"
                :key="index"
                class="html-error-item"
                :class="isHtmlErrorMarker(marker) ? 'error' : 'warning'"
                @click="revealHtmlMarker(marker)"
              >
                <span class="html-error-badge">{{ htmlMarkerLabel(marker) }}</span>
                <span class="html-error-loc">L{{ marker.startLineNumber }}:{{ marker.startColumn }}</span>
                <span class="html-error-msg">{{ marker.message }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- HTML 预览弹窗 -->
    <Teleport to="body">
      <div
        v-if="showHtmlPreviewModal"
        class="html-preview-overlay"
        role="dialog"
        aria-modal="true"
        aria-labelledby="html-preview-title"
        @click.self="closeHtmlPreviewModal"
        @keydown.esc.stop="closeHtmlPreviewModal"
        tabindex="-1"
      >
        <div class="html-preview-dialog">
          <div class="html-preview-dialog-header">
            <div id="html-preview-title" class="html-preview-dialog-title">{{ t('html.previewTitle') }}</div>
                  <button class="html-preview-close-btn" @click="closeHtmlPreviewModal" aria-label="Close">✕</button>
          </div>
          <div class="html-preview-dialog-body">
            <div class="html-preview-phone">
              <div class="html-preview-phone-notch"></div>
              <iframe
                class="html-preview-frame"
                :srcdoc="htmlPreviewContent"
                sandbox="allow-scripts allow-forms allow-modals allow-popups allow-downloads"
              ></iframe>
            </div>
          </div>
          <div class="html-preview-dialog-footer">
            <button class="btn btn-secondary btn-sm" @click="closeHtmlPreviewModal">
              {{ t('html.closePreview') }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <Teleport to="body">
      <div
        v-if="showCdnLocalizeModal"
        class="cdn-localize-overlay"
        role="dialog"
        aria-modal="true"
        aria-labelledby="cdn-localize-title"
        @click.self="closeCdnLocalizeModal"
        @keydown.esc.stop="closeCdnLocalizeModal"
        tabindex="-1"
      >
        <div class="cdn-localize-dialog">
          <div class="cdn-localize-dialog-header">
            <div id="cdn-localize-title" class="cdn-localize-dialog-title">{{ t('cdnLocalize.dialogTitle') }}</div>
                  <button class="cdn-localize-close-btn" @click="closeCdnLocalizeModal" aria-label="Close">✕</button>
          </div>
          <div class="cdn-localize-dialog-body">
            <div class="cdn-localize-toolbar">
              <div class="cdn-localize-toolbar-left">
                <button class="btn btn-ghost btn-sm" @click="selectAllCdnLinks">{{ t('cdnLocalize.selectAll') }}</button>
                <button class="btn btn-ghost btn-sm" @click="clearCdnLinkSelection">{{ t('cdnLocalize.clear') }}</button>
              </div>
              <div class="cdn-localize-toolbar-count">{{ t('cdnLocalize.selectedCount', { selected: cdnSelectedCount, total: cdnLinkItems.length }) }}</div>
            </div>

            <div v-if="cdnLinkItems.length" class="cdn-localize-list">
              <label
                v-for="item in cdnLinkItems"
                :key="item.url"
                class="cdn-localize-item"
                :class="{ active: isCdnLinkSelected(item.url) }"
              >
                <input
                  type="checkbox"
                  :checked="isCdnLinkSelected(item.url)"
                  @change="toggleCdnLinkSelection(item.url, $event.target.checked)"
                />
                <div class="cdn-localize-item-content">
                  <div class="cdn-localize-item-url">{{ item.url }}</div>
                  <div class="cdn-localize-item-meta">
                    <span>{{ getCdnTypeLabel(item.type) }}</span>
                    <span>{{ t('cdnLocalize.occurrences', { count: item.occurrences || 0 }) }}</span>
                    <span>{{ t('cdnLocalize.fileCount', { count: item.file_count || 0 }) }}</span>
                  </div>
                  <div v-if="item.files && item.files.length" class="cdn-localize-item-files">
                    {{ item.files.join(' · ') }}
                  </div>
                </div>
              </label>
            </div>
            <div v-else class="empty-state">
              <div class="empty-text">{{ t('cdnLocalize.empty') }}</div>
            </div>
          </div>
          <div class="cdn-localize-dialog-footer">
            <div class="cdn-localize-tip">{{ t('cdnLocalize.tip') }}</div>
            <button class="btn btn-primary btn-sm" @click="closeCdnLocalizeModal">{{ t('cdnLocalize.done') }}</button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- Auth dialog -->
    <Teleport to="body">
      <div
        v-if="showAuthModal"
        class="auth-overlay"
        role="dialog"
        aria-modal="true"
        aria-labelledby="auth-dialog-title"
        @click.self="closeAuthModal"
        @keydown.esc.stop="closeAuthModal"
        tabindex="-1"
      >
        <div class="auth-dialog">
          <div class="auth-dialog-header">
            <div id="auth-dialog-title" class="auth-dialog-title">
              {{ authMode === 'register' ? t('auth.registerTitle') : t('auth.loginTitle') }}
            </div>
            <button class="auth-close-btn" @click="closeAuthModal" aria-label="Close">✕</button>
          </div>

          <div v-if="isAuthEntryEnabled" class="auth-tabs">
            <button
              v-if="isClientLoginEnabled"
              class="auth-tab"
              :class="{ active: authMode === 'login' }"
              @click="switchAuthMode('login')"
            >
              {{ t('auth.loginTab') }}
            </button>
            <button
              v-if="isClientRegisterEnabled"
              class="auth-tab"
              :class="{ active: authMode === 'register' }"
              @click="switchAuthMode('register')"
            >
              {{ t('auth.registerTab') }}
            </button>
          </div>

          <div class="auth-dialog-body">
            <div v-if="authMode === 'login' && isClientSmsLoginEnabled" class="auth-login-methods">
              <button
                class="auth-method-btn"
                :class="{ active: authLoginMethod === 'password' }"
                @click="switchAuthLoginMethod('password')"
              >
                {{ t('auth.loginMethodPassword') }}
              </button>
              <button
                class="auth-method-btn"
                :class="{ active: authLoginMethod === 'sms' }"
                @click="switchAuthLoginMethod('sms')"
              >
                {{ t('auth.loginMethodSms') }}
              </button>
            </div>

            <template v-if="authMode === 'login' && authLoginMethod === 'sms'">
              <div class="form-group">
                <label class="form-label">{{ t('auth.phone') }}</label>
                <input
                  v-model.trim="authForm.phone"
                  type="tel"
                  class="form-input auth-input"
                  :placeholder="t('auth.phonePlaceholder')"
                  autocomplete="tel"
                  @keyup.enter="submitAuthForm"
                />
              </div>
              <div class="form-group">
                <label class="form-label">{{ t('auth.smsCode') }}</label>
                <div class="auth-sms-row">
                  <input
                    v-model.trim="authForm.code"
                    type="text"
                    class="form-input auth-input"
                    :placeholder="t('auth.smsCodePlaceholder')"
                    inputmode="numeric"
                    maxlength="6"
                    autocomplete="one-time-code"
                    @keyup.enter="submitAuthForm"
                  />
                  <button
                    class="btn btn-secondary btn-sm auth-sms-btn"
                    :disabled="authSmsSending || authSubmitting || authSmsCountdown > 0"
                    @click="sendAuthSmsCode"
                  >
                    {{
                      authSmsSending
                        ? t('auth.submitting')
                        : (authSmsCountdown > 0
                          ? t('auth.sendSmsCodeRetry', { seconds: authSmsCountdown })
                          : t('auth.sendSmsCode'))
                    }}
                  </button>
                </div>
              </div>
            </template>

            <template v-else>
              <div class="form-group">
                <label class="form-label">{{ t('auth.email') }}</label>
                <input
                  v-model.trim="authForm.email"
                  type="email"
                  class="form-input auth-input"
                  :placeholder="t('auth.emailPlaceholder')"
                  autocomplete="username"
                  @keyup.enter="submitAuthForm"
                />
              </div>
              <div class="form-group">
                <label class="form-label">{{ t('auth.password') }}</label>
                <input
                  v-model="authForm.password"
                  type="password"
                  class="form-input auth-input"
                  :placeholder="t('auth.passwordPlaceholder')"
                  autocomplete="current-password"
                  @keyup.enter="submitAuthForm"
                />
              </div>
              <div v-if="authMode === 'register'" class="form-group">
                <label class="form-label">{{ t('auth.confirmPassword') }}</label>
                <input
                  v-model="authForm.confirmPassword"
                  type="password"
                  class="form-input auth-input"
                  :placeholder="t('auth.confirmPasswordPlaceholder')"
                  autocomplete="new-password"
                  @keyup.enter="submitAuthForm"
                />
              </div>
            </template>
            <div v-if="authError" class="form-error auth-error">{{ authError }}</div>
          </div>

          <div v-if="isClientLoginEnabled && authMode === 'login' && authLoginMethod === 'password'" class="auth-oauth-wrap">
            <div class="auth-oauth-divider">
              <span>{{ t('auth.orDivider') }}</span>
            </div>
            <button
              class="auth-github-btn"
              :disabled="authSubmitting || githubAuthSubmitting"
              @click="startGithubAuth"
            >
              <span class="auth-github-mark" aria-hidden="true">GH</span>
              <span>{{ githubAuthSubmitting ? t('auth.githubRedirecting') : t('auth.githubSubmit') }}</span>
            </button>
          </div>

          <div class="auth-dialog-footer">
            <button class="btn btn-secondary btn-sm" @click="closeAuthModal">
              {{ t('auth.cancel') }}
            </button>
            <button
              class="btn btn-primary btn-sm auth-submit-btn"
              :class="{ 'auth-submit-shake': authSubmitButtonShake }"
              :disabled="authSubmitting || githubAuthSubmitting || authSmsSending || (authMode === 'login' ? (!isClientLoginEnabled || (authLoginMethod === 'sms' && !isClientSmsLoginEnabled)) : !isClientRegisterEnabled)"
              @click="submitAuthForm"
            >
              {{
                authSubmitting
                  ? t('auth.submitting')
                  : (authMode === 'register' ? t('auth.registerSubmit') : (authLoginMethod === 'sms' ? t('auth.smsLoginSubmit') : t('auth.loginSubmit')))
              }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- Donation dialog -->
    <Teleport to="body">
      <div
        v-if="showDonation"
        class="donation-overlay"
        role="dialog"
        aria-modal="true"
        aria-labelledby="donation-title"
        @click.self="closeDonation"
        @keydown.esc.stop="closeDonation"
        tabindex="-1"
      >
        <div class="donation-dialog">
          <div class="donation-dialog-header">
            <h3 id="donation-title">💛 {{ t('donation.title') }}</h3>
            <button class="donation-close-btn" @click="closeDonation" aria-label="Close">✕</button>
          </div>
          <div class="donation-dialog-body">
            <div class="donation-message">{{ donationDialogPrimaryText }}</div>
            <div v-if="donationDialogSecondaryText" class="donation-sub">{{ donationDialogSecondaryText }}</div>
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
      <div
        v-if="showSettings"
        class="settings-overlay"
        role="dialog"
        aria-modal="true"
        aria-labelledby="settings-title"
        @click.self="closeSettings"
        @keydown.esc.stop="closeSettings"
        tabindex="-1"
      >
        <div class="settings-dialog">
          <div class="settings-dialog-header">
            <h3 id="settings-title">{{ t('settings.title') }}</h3>
            <button class="settings-close-btn" @click="closeSettings" aria-label="Close">✕</button>
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

    <!-- 确认对话框：替代原生 confirm() -->
    <ConfirmDialog
      :visible="confirmDialog.visible"
      :title="confirmDialog.title"
      :message="confirmDialog.message"
      :confirm-text="confirmDialog.confirmText"
      :cancel-text="confirmDialog.cancelText"
      :confirm-type="confirmDialog.confirmType"
      @confirm="closeConfirmDialog(true)"
      @cancel="closeConfirmDialog(false)"
    />

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
import { Cropper } from 'vue-advanced-cropper'
import 'vue-advanced-cropper/dist/style.css'
import { useAppState } from './composables/useAppState'
import AdSenseSlot from './components/AdSenseSlot.vue'
import ConfirmDialog from './components/ConfirmDialog.vue'

export default defineComponent({
  name: 'App',
  components: { Cropper, AdSenseSlot, ConfirmDialog },
  setup() {
    return useAppState()
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

.app-boot-copy {
  display: grid;
  gap: 8px;
  text-align: center;
  min-width: 0;
}

.app-boot-kicker {
  color: #66d4ff;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0;
  text-transform: uppercase;
}

.light-theme .app-boot-kicker {
  color: #2f6fed;
}

.app-boot-title {
  color: #f8fbff;
  font-size: 20px;
  font-weight: 800;
  line-height: 1.25;
  overflow-wrap: anywhere;
}

.light-theme .app-boot-title {
  color: #12213a;
}

.app-boot-text {
  color: rgba(226, 238, 255, 0.72);
  font-size: 13px;
  line-height: 1.6;
  overflow-wrap: anywhere;
}

.light-theme .app-boot-text {
  color: rgba(33, 49, 74, 0.68);
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

  .app-boot-title {
    font-size: 18px;
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
</style>
