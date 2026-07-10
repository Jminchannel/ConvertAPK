# 公网 IP 构建限额功能开关实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在管理端增加默认关闭的全局公网 IP 构建限额开关，并让用户端后端只在环境变量和管理端开关同时开启时执行 IP 限额。

**Architecture:** 复用管理端 `FeatureToggle` 和 `/api/client/features` 下发链路。管理端数据库字段与接口均默认 `false`，用户端后端缓存并读取该字段；管理端不可达或缺少字段时保持关闭，其他 clientId、用户和付费额度逻辑不变。

**Tech Stack:** FastAPI、SQLAlchemy、PostgreSQL、Vue 3、Docker Compose。

## Global Constraints

- 所有新增代码与注释使用 UTF-8 无 BOM，新增注释使用中文。
- 字段名固定为 `build_ip_quota_enabled`，默认值固定为 `false`。
- 环境变量 `BUILD_IP_QUOTA_ENABLED` 保留为紧急总开关。
- 不修改用户端前端、构建器、模板和无关管理端文件。
- 主仓库与管理端仓库均从干净隔离工作树发布。
- 远程工作树不执行 `git reset` 或全仓覆盖，先备份再覆盖目标文件。
- 根据当前工作区协作约束，不增加或运行本地测试；使用 Docker 构建、接口响应和实际任务启动结果完成部署验证。

---

### Task 1: 管理端后端全局开关

**Files:**
- Modify: `admin/backend/app/models.py`
- Modify: `admin/backend/app/schemas.py`
- Modify: `admin/backend/app/main.py`
- Modify: `admin/backend/app/routes/admin_feature_flags.py`
- Modify: `admin/backend/app/routes/client_features.py`

**Interfaces:**
- Produces: `FeatureToggle.build_ip_quota_enabled: bool`
- Produces: `/api/admin/feature-flags` 请求和响应字段 `build_ip_quota_enabled`
- Produces: `/api/client/features` 响应字段 `build_ip_quota_enabled`

- [ ] **Step 1: 增加模型和模式字段**

```python
build_ip_quota_enabled = Column(Boolean, nullable=False, default=False)
```

```python
build_ip_quota_enabled: bool = False
```

- [ ] **Step 2: 增加启动时数据库字段补齐**

```python
if "build_ip_quota_enabled" not in feature_columns:
    conn.execute(
        text(
            "ALTER TABLE feature_toggles "
            "ADD COLUMN build_ip_quota_enabled BOOLEAN NOT NULL DEFAULT FALSE"
        )
    )
```

- [ ] **Step 3: 接入管理员读写接口**

```python
build_ip_quota_enabled=False
```

```python
build_ip_quota_enabled=bool(getattr(toggle, "build_ip_quota_enabled", False))
```

```python
toggle.build_ip_quota_enabled = bool(payload.build_ip_quota_enabled)
```

- [ ] **Step 4: 接入客户端功能接口**

```python
global_build_ip_quota_enabled = bool(getattr(toggle, "build_ip_quota_enabled", False)) if toggle else False
```

```python
build_ip_quota_enabled=global_build_ip_quota_enabled
```

### Task 2: 管理端页面开关

**Files:**
- Modify: `admin/frontend/src/App.vue`

**Interfaces:**
- Consumes: `build_ip_quota_enabled` from admin feature-flags API
- Produces: 管理端“公网 IP 构建限额”全局开关

- [ ] **Step 1: 增加页面状态和接口映射**

```javascript
build_ip_quota_enabled: false,
```

读取和保存都使用严格布尔值，缺失字段按 `false` 处理。

- [ ] **Step 2: 增加开关界面**

```html
<div class="list-item">
  <div>
    <div class="list-title">公网 IP 构建限额</div>
    <div class="muted small">关闭后仅保留 clientId、用户和付费额度限制；重新开启前请确保真实公网 IP 代理配置正确。</div>
  </div>
  <label class="switch-inline">
    <input type="checkbox" v-model="featureFlags.build_ip_quota_enabled" />
    <span>{{ featureFlags.build_ip_quota_enabled ? "开启" : "关闭" }}</span>
  </label>
</div>
```

### Task 3: 用户端后端执行开关

**Files:**
- Modify: `web/backend/admin_client.py`
- Modify: `web/backend/main.py`

**Interfaces:**
- Consumes: `/api/client/features.build_ip_quota_enabled`
- Produces: `_check_build_ip_quota()` 仅在双重开关开启时执行

- [ ] **Step 1: 缓存管理端开关**

```python
"build_ip_quota_enabled": False,
```

```python
if "build_ip_quota_enabled" in data:
    result["build_ip_quota_enabled"] = bool(data.get("build_ip_quota_enabled"))
```

- [ ] **Step 2: 在读取 IP 状态前短路关闭状态**

```python
feature_flags = fetch_feature_flags(client_id=client_id)
if not bool(feature_flags.get("build_ip_quota_enabled", False)):
    return None
```

### Task 4: 提交并推送两个仓库

**Files:**
- Main repository commit: design、plan、`web/backend/admin_client.py`、`web/backend/main.py`
- Admin repository commit: 五个后端文件和 `frontend/src/App.vue`

- [ ] **Step 1: 提交管理端仓库**

```bash
git add backend/app/models.py backend/app/schemas.py backend/app/main.py backend/app/routes/admin_feature_flags.py backend/app/routes/client_features.py frontend/src/App.vue
git commit -m "feat: add IP quota feature toggle"
git push origin HEAD:main
```

- [ ] **Step 2: 提交主仓库并推送**

```bash
git add docs/superpowers web/backend/admin_client.py web/backend/main.py
git commit -m "feat: control IP quota from admin"
git push origin HEAD:main
```

### Task 5: 远程最小部署

**Files:**
- Overlay: `/data/ConvertAPK-Desktop/web/backend/admin_client.py`
- Overlay: `/data/ConvertAPK-Desktop/web/backend/main.py`
- Overlay: `/data/ConvertAPK-Desktop/admin/backend/app/models.py`
- Overlay: `/data/ConvertAPK-Desktop/admin/backend/app/schemas.py`
- Overlay: `/data/ConvertAPK-Desktop/admin/backend/app/main.py`
- Overlay: `/data/ConvertAPK-Desktop/admin/backend/app/routes/admin_feature_flags.py`
- Overlay: `/data/ConvertAPK-Desktop/admin/backend/app/routes/client_features.py`
- Overlay: `/data/ConvertAPK-Desktop/admin/frontend/src/App.vue`

- [ ] **Step 1: 备份远程目标文件并覆盖**

备份目录使用 `.codex-backup/ip-quota-feature-toggle-<timestamp>`，仅复制上述文件。

- [ ] **Step 2: 重建受影响服务**

```bash
docker compose build admin-backend admin-frontend backend
docker compose up -d admin-backend admin-frontend backend
```

- [ ] **Step 3: 明确保持线上开关关闭**

管理端启动迁移后将 `feature_toggles.build_ip_quota_enabled` 更新为 `FALSE`，避免已有数据行出现不确定状态。

- [ ] **Step 4: 验证线上结果**

确认三个容器为运行状态；确认管理员功能接口和客户端功能接口返回 `build_ip_quota_enabled: false`；确认原任务启动不再因 IP 限额返回 429，并保持其他构建配额逻辑生效。
