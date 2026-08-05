import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import test from 'node:test'

const frontendRoot = resolve(import.meta.dirname, '..')
const packageJson = JSON.parse(readFileSync(resolve(frontendRoot, 'package.json'), 'utf8'))

test('前端提供统一质量检查脚本', () => {
  assert.equal(typeof packageJson.scripts.lint, 'string')
  assert.equal(typeof packageJson.scripts['test:unit'], 'string')
  assert.equal(typeof packageJson.scripts.test, 'string')
  assert.equal(typeof packageJson.scripts.check, 'string')
})
