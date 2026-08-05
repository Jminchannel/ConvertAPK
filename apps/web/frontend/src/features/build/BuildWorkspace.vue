<template>
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
                    :class="{ 'input-locked': updatingTaskId, 'input-error': prohibitedGenerationError }"
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
                  <div v-if="config.status_bar_hidden" class="form-hint">
                    {{ t('config.statusBarColorHiddenHint') }}
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
                <div class="form-hint warning">{{ t('config.prohibitedGenerationHint') }}</div>
                <label class="settings-checkbox task-compliance-ack">
                  <input type="checkbox" v-model="taskComplianceAck" />
                  {{ t('config.taskComplianceAckLabel') }}
                </label>
                <div v-if="prohibitedGenerationError" class="form-error">{{ prohibitedGenerationError }}</div>
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
</template>

<script>
import { defineComponent } from 'vue'
import { useAppStateContext } from '../../app/appStateContext'

export default defineComponent({
  name: 'BuildWorkspace',
  setup() {
    return useAppStateContext()
  }
})
</script>
