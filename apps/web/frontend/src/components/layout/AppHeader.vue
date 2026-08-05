<template>
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
          <button
            v-if="!isMobileShell && isBuildPaymentModeEnabled"
            class="btn btn-secondary btn-sm no-drag"
            @click="openBuildPaymentModal"
          >
            <span class="action-icon">￥</span>
            <span class="action-label">购买额度</span>
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

</template>

<script>
import { defineComponent } from 'vue'
import { useAppStateContext } from '../../app/appStateContext'

export default defineComponent({
  name: 'AppHeader',
  setup() {
    return useAppStateContext()
  }
})
</script>
