import { inject, provide } from 'vue'

const appStateKey = Symbol('appState')

export function provideAppState(appState) {
  provide(appStateKey, appState)
}

export function useAppStateContext() {
  const appState = inject(appStateKey, null)

  if (!appState) {
    throw new Error('应用状态未初始化')
  }

  return appState
}
