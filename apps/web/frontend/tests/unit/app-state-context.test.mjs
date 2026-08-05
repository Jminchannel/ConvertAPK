import { createApp, h } from 'vue'
import { describe, expect, it } from 'vitest'
import { provideAppState, useAppStateContext } from '../../src/app/appStateContext.js'

describe('应用状态上下文', () => {
  it('在同一应用中读取提供的状态对象', () => {
    const state = { currentTheme: 'dark' }
    let injectedState
    const Child = {
      setup() {
        injectedState = useAppStateContext()
        return () => null
      },
    }
    const app = createApp({
      setup() {
        provideAppState(state)
        return () => h(Child)
      },
    })

    const mountTarget = document.createElement('div')
    app.mount(mountTarget)

    expect(injectedState).toBe(state)
    app.unmount()
  })
})
