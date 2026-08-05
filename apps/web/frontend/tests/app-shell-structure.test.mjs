import assert from 'node:assert/strict'
import { readFileSync, existsSync } from 'node:fs'
import { resolve } from 'node:path'
import test from 'node:test'

const sourceRoot = resolve(import.meta.dirname, '..', 'src')

test('根入口仅负责创建状态并加载应用壳', () => {
  const appSource = readFileSync(resolve(sourceRoot, 'App.vue'), 'utf8')

  assert.match(appSource, /provideAppState/)
  assert.match(appSource, /AppShell/)
  assert.doesNotMatch(appSource, /class="header"/)
  assert.doesNotMatch(appSource, /class="task-board-card"/)
})

test('应用壳按页面区域拆分组件', () => {
  const requiredFiles = [
    'app/AppShell.vue',
    'app/appStateContext.js',
    'components/layout/AppHeader.vue',
    'features/build/BuildWorkspace.vue',
    'features/tasks/TaskWorkspace.vue',
    'features/dialogs/AppDialogs.vue',
  ]

  for (const relativeFile of requiredFiles) {
    assert.equal(existsSync(resolve(sourceRoot, relativeFile)), true, `${relativeFile} should exist`)
  }
})
