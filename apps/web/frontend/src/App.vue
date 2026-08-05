<template>
  <AppShell />
</template>

<script>
import { defineComponent } from 'vue'
import { useAppState } from './composables/useAppState'
import AppShell from './app/AppShell.vue'
import { provideAppState } from './app/appStateContext'

export default defineComponent({
  name: 'App',
  components: { AppShell },
  setup() {
    provideAppState(useAppState())
  }
})
</script>
