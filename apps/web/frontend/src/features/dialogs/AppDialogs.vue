<template>
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
            <p v-if="complianceNotice.intro" class="compliance-intro">{{ complianceNotice.intro }}</p>
            <p
              v-for="(paragraph, paragraphIndex) in complianceNotice.paragraphs || []"
              :key="`compliance-paragraph-${paragraphIndex}`"
              class="compliance-intro compliance-custom-paragraph"
            >
              {{ paragraph }}
            </p>
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
            <div v-if="complianceNotice.legalReferences" class="compliance-law">{{ complianceNotice.legalReferences }}</div>
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
            <div v-if="isBuildPaymentModeEnabled" class="settings-section build-payment-section">
              <div class="settings-section-title">
                <span class="section-title-icon">￥</span>
                构建额度
              </div>
              <div class="settings-hint">
                当前剩余：{{ buildQuotaContext.remaining_balance ?? '-' }} 次；累计消耗：{{ buildQuotaContext.consumed_total ?? 0 }} 次
              </div>
              <div class="build-payment-actions">
                <input
                  v-if="buildQuotaContext.build_code_enabled"
                  v-model="buildCodeInput"
                  class="form-input"
                  placeholder="输入构建码"
                  @keyup.enter="redeemCurrentBuildCode"
                />
                <button
                  v-if="buildQuotaContext.build_code_enabled"
                  class="btn btn-secondary btn-sm"
                  @click="redeemCurrentBuildCode"
                  :disabled="buildCodeRedeeming"
                >
                  {{ buildCodeRedeeming ? '兑换中...' : '兑换' }}
                </button>
                <button class="btn btn-primary btn-sm" @click="openBuildPaymentModal">
                  购买额度
                </button>
              </div>
            </div>

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

    <Teleport to="body">
      <div
        v-if="showBuildPaymentModal"
        class="build-payment-overlay"
        role="dialog"
        aria-modal="true"
        aria-labelledby="build-payment-title"
        @click.self="closeBuildPaymentModal"
        @keydown.esc.stop="closeBuildPaymentModal"
        tabindex="-1"
      >
        <div class="build-payment-dialog">
          <div class="build-payment-dialog-header">
            <div>
              <h3 id="build-payment-title">购买构建额度</h3>
              <p>当前剩余 {{ buildQuotaContext.remaining_balance ?? '-' }} 次，支付成功后自动到账。</p>
            </div>
            <button class="build-payment-close-btn" @click="closeBuildPaymentModal" aria-label="Close">✕</button>
          </div>
          <div class="build-payment-dialog-body">
            <div v-if="buildPaymentPlansLoading" class="settings-hint">正在加载套餐...</div>
            <div v-else-if="buildPaymentPlansError" class="settings-hint build-payment-error">
              {{ buildPaymentPlansError }}
            </div>
            <div v-else>
              <div v-if="!buildPaymentAlipayConfigured" class="build-payment-warning">
                支付宝支付暂未配置完成，请联系管理员。
              </div>
              <div class="build-payment-grid">
                <div v-for="plan in buildPaymentPlans" :key="plan.plan_id" class="build-payment-plan">
                  <div class="build-payment-plan-name">{{ plan.name }}</div>
                  <div class="build-payment-plan-price">￥{{ (Number(plan.amount_cents || 0) / 100).toFixed(2) }}</div>
                  <div class="build-payment-plan-meta">{{ plan.grant_count }} 次构建额度</div>
                  <button
                    class="btn btn-primary btn-sm"
                    @click="startAlipayBuildPayment(plan.plan_id)"
                    :disabled="buildPaymentCreating || !buildPaymentAlipayConfigured"
                  >
                    {{ buildPaymentCreating ? '创建订单中...' : '支付宝支付' }}
                  </button>
                </div>
              </div>
              <div v-if="!buildPaymentPlans.length" class="settings-hint">暂无可购买套餐</div>
            </div>
            <div v-if="buildPaymentOrder" class="build-payment-status">
              <div>订单：{{ buildPaymentOrder.order_no }}</div>
              <div>状态：{{ buildPaymentOrder.status }}</div>
              <div v-if="buildPaymentPolling">正在等待支付宝支付结果...</div>
            </div>
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

</template>

<script>
import { defineComponent } from 'vue'
import { Cropper } from 'vue-advanced-cropper'
import 'vue-advanced-cropper/dist/style.css'
import { useAppStateContext } from '../../app/appStateContext'
import ConfirmDialog from '../../components/ConfirmDialog.vue'

export default defineComponent({
  name: 'AppDialogs',
  components: { Cropper, ConfirmDialog },
  setup() {
    return useAppStateContext()
  }
})
</script>
