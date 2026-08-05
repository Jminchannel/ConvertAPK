# 职责边界与工程化保障 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复当前前端缺失构建区的回归，拆分前后端集中职责，并让质量门禁可在本地和 GitHub Actions 执行。

**Architecture:** 前端保持 `App.vue -> AppShell -> feature` 视图结构，`useAppState` 逐步改为组装器。后端保持 `app.main:app` 入口，把端点注册移动到资源路由模块；路由调用服务与共享运行态，不改变公开 API。CI 只执行仓库中定义的脚本。

**Tech Stack:** Vue 3、Vite、ESLint、Vitest、FastAPI、Pydantic、unittest、GitHub Actions。

## Global Constraints

- 不改变 `/api/*` 的路径、方法、请求响应字段或任务状态语义。
- 不引入 TypeScript、Pinia、Vue Router 或新的后端框架。
- 所有新增注释使用中文，文件使用 UTF-8 无 BOM。
- 不读取或修改原始脏 `main` 工作区的内容。
- 每个生产变更先有失败测试，再实现最小改动。

---

### Task 1: 修复已发布前端构建区回归

**Files:**
- Modify: `.gitignore`
- Create: `apps/web/frontend/src/features/build/BuildWorkspace.vue`
- Modify: `apps/web/frontend/tests/app-shell-structure.test.mjs`

**Interfaces:**
- Consumes: `useAppStateContext()` 返回的既有顶层状态与方法。
- Produces: `BuildWorkspace`，供 `AppShell.vue` 的 `<BuildWorkspace />` 使用。

- [ ] **Step 1: 保留失败断言并确认缺失组件复现**

```js
assert.equal(existsSync(resolve(sourceRoot, 'features/build/BuildWorkspace.vue')), true)
```

- [ ] **Step 2: 运行失败测试**

Run: `node --test tests/app-shell-structure.test.mjs`
Expected: FAIL，指出 `features/build/BuildWorkspace.vue should exist`。

- [ ] **Step 3: 从 `e64c1b9:web/frontend/src/App.vue` 的构建区恢复组件，并将 `.gitignore` 的 `build/` 改为根目录规则 `/build/`**

```vue
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
```

- [ ] **Step 4: 验证恢复后的页面结构和生产构建**

Run: `node --test tests/app-shell-structure.test.mjs && npm run build`
Expected: PASS，且 Vite 退出码为 0。

- [ ] **Step 5: 提交回归修复**

```bash
git add .gitignore apps/web/frontend/src/features/build/BuildWorkspace.vue apps/web/frontend/tests/app-shell-structure.test.mjs
git commit -m "fix: restore build workspace source"
```

### Task 2: 建立前端质量门禁

**Files:**
- Modify: `apps/web/frontend/package.json`
- Modify: `apps/web/frontend/vite.config.js`
- Create: `apps/web/frontend/eslint.config.js`
- Create: `apps/web/frontend/tests/unit/app-state-context.test.mjs`

**Interfaces:**
- Consumes: `provideAppState(appState)` 与 `useAppStateContext()`。
- Produces: `npm run lint`、`npm run test:unit`、`npm run test`、`npm run check`。

- [ ] **Step 1: 写出缺少质量脚本的失败测试**

```js
assert.equal(typeof packageJson.scripts.check, 'string')
assert.equal(typeof packageJson.scripts.lint, 'string')
assert.equal(typeof packageJson.scripts['test:unit'], 'string')
```

- [ ] **Step 2: 运行测试确认失败**

Run: `node --test tests/unit/tooling-contract.test.mjs`
Expected: FAIL，因为 `lint`、`test:unit`、`check` 尚不存在。

- [ ] **Step 3: 新增 ESLint/Vitest 配置和脚本，并为状态上下文写单元测试**

```json
{
  "scripts": {
    "lint": "eslint src tests",
    "test:unit": "vitest run",
    "test": "node --test tests/app-shell-structure.test.mjs && vitest run",
    "check": "npm run lint && npm run test && npm run build"
  }
}
```

- [ ] **Step 4: 安装锁定依赖并运行质量门禁**

Run: `npm install && npm run check`
Expected: PASS。

- [ ] **Step 5: 提交前端质量门禁**

```bash
git add apps/web/frontend
git commit -m "build: add frontend quality checks"
```

### Task 3: 将前端状态按领域抽取

**Files:**
- Create: `apps/web/frontend/src/features/ui/composables/useUiState.js`
- Create: `apps/web/frontend/src/features/auth/composables/useAuthState.js`
- Create: `apps/web/frontend/src/features/tasks/composables/useTaskState.js`
- Create: `apps/web/frontend/src/features/uploads/composables/useUploadState.js`
- Modify: `apps/web/frontend/src/composables/useAppState.js`
- Test: `apps/web/frontend/tests/unit/*.test.mjs`

**Interfaces:**
- Consumes: API 模块、现有 ref、`showToast(message, type)` 和翻译函数。
- Produces: 同名状态和操作方法，供 `useAppState` 合并后继续被页面组件使用。

- [ ] **Step 1: 为每个领域写失败的导入与最小行为测试**

```js
import { createTaskState } from '../../src/features/tasks/composables/useTaskState.js'

test('任务状态只暴露任务相关状态和操作', () => {
  const taskState = createTaskState({ api: {}, showToast() {} })
  assert.ok('tasks' in taskState)
  assert.ok('refreshTasks' in taskState)
})
```

- [ ] **Step 2: 运行 Vitest 确认模块未定义而失败**

Run: `npm run test:unit`
Expected: FAIL，提示对应 composable 无法导入。

- [ ] **Step 3: 逐个移动现有状态和方法，`useAppState` 只创建共享依赖并展开各领域返回值**

```js
return {
  ...uiState,
  ...authState,
  ...taskState,
  ...uploadState,
}
```

- [ ] **Step 4: 运行单元测试、结构测试与生产构建**

Run: `npm run check`
Expected: PASS。

- [ ] **Step 5: 提交前端领域拆分**

```bash
git add apps/web/frontend/src apps/web/frontend/tests
git commit -m "refactor: split frontend state domains"
```

### Task 4: 将后端路由从应用入口拆出

**Files:**
- Create: `apps/web/backend/app/api/__init__.py`
- Create: `apps/web/backend/app/api/routes/auth.py`
- Create: `apps/web/backend/app/api/routes/uploads.py`
- Create: `apps/web/backend/app/api/routes/tasks.py`
- Create: `apps/web/backend/app/api/routes/operations.py`
- Create: `apps/web/backend/app/api/routes/adminhub.py`
- Modify: `apps/web/backend/app/main.py`
- Test: `tests/test_backend_route_contract.py`

**Interfaces:**
- Consumes: 已有 Pydantic 模型、服务函数和共享运行态访问器。
- Produces: `registerApiRoutes(app: FastAPI) -> None`，由 `app.main` 调用一次。

- [ ] **Step 1: 扩展路由契约测试，要求入口只注册路由模块**

```python
source = (BACKEND_DIR / 'app' / 'main.py').read_text(encoding='utf-8')
self.assertIn('register_api_routes(app)', source)
self.assertNotIn('@app.post("/api/tasks")', source)
```

- [ ] **Step 2: 运行路由契约测试确认失败**

Run: `python -m unittest tests/test_backend_route_contract.py -v`
Expected: FAIL，因为 `main.py` 仍定义业务端点。

- [ ] **Step 3: 先迁移 operations/adminhub，再迁移 auth/uploads/tasks；每个路由使用 APIRouter 并保留原装饰器路径与响应模型**

```python
router = APIRouter()

def register_api_routes(app: FastAPI) -> None:
    app.include_router(operations.router)
    app.include_router(adminhub.router)
    app.include_router(auth.router)
    app.include_router(uploads.router)
    app.include_router(tasks.router)
```

- [ ] **Step 4: 执行后端回归与路由契约测试**

Run: `python -m unittest tests/test_backend_route_contract.py -v && python -m unittest discover -s apps/web/backend/tests -v`
Expected: PASS，且已发布路由集合不变。

- [ ] **Step 5: 提交后端路由拆分**

```bash
git add apps/web/backend/app tests
git commit -m "refactor: split backend api routes"
```

### Task 5: 增加 GitHub Actions 与统一验证

**Files:**
- Create: `.github/workflows/quality.yml`
- Modify: `CONTRIBUTING.md`
- Test: `.github/workflows/quality.yml` 配置契约测试

**Interfaces:**
- Consumes: `apps/web/frontend/package.json` 的 `check` 脚本与现有 Python unittest 命令。
- Produces: 推送 `main`、PR 与手动触发时运行的 `quality` 工作流。

- [ ] **Step 1: 写出工作流契约测试**

```python
self.assertIn('npm run check', workflow)
self.assertIn('python -m unittest', workflow)
self.assertIn('docker compose -f docker-compose.yml config --no-interpolate', workflow)
```

- [ ] **Step 2: 运行测试确认工作流缺失**

Run: `python -m unittest tests/test_quality_workflow_contract.py -v`
Expected: FAIL，因为工作流文件不存在。

- [ ] **Step 3: 新增 quality 工作流，安装 Node 20 与 Python 3.12，并运行前后端、构建器、Compose 和生产依赖审计**

```yaml
- run: npm ci
  working-directory: apps/web/frontend
- run: npm run check
  working-directory: apps/web/frontend
- run: python -m unittest discover -s apps/web/backend/tests -v
- run: python -m unittest discover -s workers/apk-worker/tests -v
```

- [ ] **Step 4: 本地验证工作流契约和完整检查集**

Run: `python -m unittest tests/test_quality_workflow_contract.py -v && npm run check`
Expected: PASS。

- [ ] **Step 5: 提交 CI 与贡献文档**

```bash
git add .github CONTRIBUTING.md tests
git commit -m "ci: enforce quality checks"
```

### Task 6: 最终集成验证

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md`

**Interfaces:**
- Consumes: 前端 `check`、后端/构建器 unittest、Compose 配置。
- Produces: 与 CI 一致的本地验证说明。

- [ ] **Step 1: 写出 README/AGENTS 命令契约测试**

```python
self.assertIn('npm run check', readme)
self.assertIn('app/api/routes', agents)
```

- [ ] **Step 2: 运行测试确认文档尚未更新**

Run: `python -m unittest tests/test_documentation_contract.py -v`
Expected: FAIL。

- [ ] **Step 3: 更新文档中的模块职责与验证命令**

```text
前端：cd apps/web/frontend && npm run check
后端：python -m unittest discover -s apps/web/backend/tests -v
```

- [ ] **Step 4: 运行全部验证**

Run: `python -m unittest discover -s tests -v && python -m unittest discover -s apps/web/backend/tests -v && python -m unittest discover -s workers/apk-worker/tests -v && npm run check && docker compose -f docker-compose.yml config --no-interpolate`
Expected: PASS。

- [ ] **Step 5: 提交最终文档与验证**

```bash
git add README.md AGENTS.md tests
git commit -m "docs: document quality workflow"
```
