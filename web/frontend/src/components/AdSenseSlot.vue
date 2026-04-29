<template>
  <aside v-if="shouldRenderShell" class="adsense-slot" :class="variantClass" aria-label="Advertisement">
    <div class="adsense-label">{{ label }}</div>
    <ins
      v-if="shouldRenderAd"
      ref="adElement"
      class="adsbygoogle"
      :style="adStyle"
      :data-ad-client="clientId"
      :data-ad-slot="resolvedSlotId"
      :data-ad-format="adFormat"
      :data-full-width-responsive="fullWidthResponsive"
    ></ins>
    <div v-else class="adsense-preview">
      <span>{{ previewText }}</span>
    </div>
  </aside>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'

const props = defineProps({
  slotName: {
    type: String,
    default: 'home'
  },
  slotId: {
    type: String,
    default: ''
  },
  label: {
    type: String,
    default: 'Advertisement'
  },
  previewText: {
    type: String,
    default: 'Ad space'
  },
  adFormat: {
    type: String,
    default: 'auto'
  },
  fullWidthResponsive: {
    type: String,
    default: 'true'
  },
  minHeight: {
    type: Number,
    default: 120
  },
  variant: {
    type: String,
    default: 'wide'
  }
})

const adElement = ref(null)
const loadedSlotId = ref('')
const clientId = computed(() => import.meta.env.VITE_ADSENSE_CLIENT || 'ca-pub-6847615621445179')
const enabledFlag = computed(() => String(import.meta.env.VITE_ADSENSE_ENABLED ?? 'true').toLowerCase())
const isEnabled = computed(() => enabledFlag.value !== 'false' && enabledFlag.value !== '0')
const isDesktopShell = computed(() => typeof window !== 'undefined' && Boolean(window.windowControls))
const slotEnvKey = computed(() => `VITE_ADSENSE_${props.slotName.toUpperCase().replace(/[^A-Z0-9]+/g, '_')}_SLOT`)
const resolvedSlotId = computed(() => props.slotId || import.meta.env[slotEnvKey.value] || '')
const shouldRenderAd = computed(() => (
  import.meta.env.PROD &&
  isEnabled.value &&
  !isDesktopShell.value &&
  Boolean(clientId.value) &&
  Boolean(resolvedSlotId.value)
))
const shouldRenderShell = computed(() => shouldRenderAd.value || import.meta.env.DEV)
const variantClass = computed(() => `adsense-slot-${props.variant}`)
const adStyle = computed(() => `display:block;min-height:${props.minHeight}px`)

const ensureAdsenseScript = () => {
  if (typeof document === 'undefined') return
  if (document.getElementById('google-adsense-script')) return
  const script = document.createElement('script')
  script.id = 'google-adsense-script'
  script.async = true
  script.crossOrigin = 'anonymous'
  script.src = `https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=${encodeURIComponent(clientId.value)}`
  document.head.appendChild(script)
}

const requestAd = async () => {
  if (!shouldRenderAd.value || loadedSlotId.value === resolvedSlotId.value) return
  ensureAdsenseScript()
  await nextTick()
  try {
    window.adsbygoogle = window.adsbygoogle || []
    window.adsbygoogle.push({})
    loadedSlotId.value = resolvedSlotId.value
  } catch (error) {
    loadedSlotId.value = ''
  }
}

onMounted(requestAd)
watch(resolvedSlotId, requestAd)
</script>
