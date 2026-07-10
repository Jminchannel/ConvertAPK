# 公网 IP 构建限额功能开关设计

## 目标

在管理端“功能开关”中新增全局“公网 IP 构建限额”开关，并默认关闭。关闭后所有用户跳过公网 IP 限额，但现有 clientId、登录用户、每日构建次数、付费额度和风控审核继续正常生效。

## 现状与约束

- 公网 IP 限额目前由用户端后端 `POST /api/tasks/{task_id}/start` 强制执行。
- 管理端已有统一 `FeatureToggle`、管理员读写接口和 `/api/client/features` 客户端读取链路，应复用该架构。
- 用户端后端已经通过 `fetch_feature_flags()` 获取并缓存管理端开关，缓存时间约 5 秒。
- 环境变量 `BUILD_IP_QUOTA_ENABLED` 保留为紧急总开关。
- 当前反向代理尚未正确传递真实公网 IP，重新启用 IP 限额前必须先修复代理链。

## 方案选择

采用“数据库全局开关 + 环境变量总开关”的组合方案。

最终生效条件：

```text
BUILD_IP_QUOTA_ENABLED=true
且
管理端 build_ip_quota_enabled=true
```

未采用仅环境变量方案，因为它无法通过管理端操作且需要重启服务。未采用独立配置表方案，因为会重复现有 `FeatureToggle` 能力并增加维护成本。

## 管理端设计

### 数据与接口

- 在 `FeatureToggle` 增加布尔字段 `build_ip_quota_enabled`，数据库默认值为 `false`。
- 在现有启动时字段补齐逻辑中增加该列，兼容已有 PostgreSQL 数据库，无需手工执行迁移脚本。
- `FeatureFlagsItem` 与 `FeatureFlagsUpdateRequest` 增加同名字段，缺省值为 `false`。
- `/api/admin/feature-flags` 的读取和更新接口返回并保存该字段。
- `/api/client/features` 返回该字段，供用户端后端读取。

涉及文件：

- `admin/backend/app/models.py`
- `admin/backend/app/schemas.py`
- `admin/backend/app/main.py`
- `admin/backend/app/routes/admin_feature_flags.py`
- `admin/backend/app/routes/client_features.py`

### 管理端页面

在现有“功能开关”区域增加开关项：

- 名称：`公网 IP 构建限额`
- 说明：`关闭后仅保留 clientId、用户和付费额度限制；重新开启前请确保真实公网 IP 代理配置正确。`
- 初始值：`关闭`

复用现有功能开关读取、编辑和保存流程，不新增独立页面或 API。

涉及文件：

- `admin/frontend/src/App.vue`

## 用户端后端设计

- `fetch_feature_flags()` 的默认结果增加 `build_ip_quota_enabled: false`。
- 管理端返回该字段时进行布尔值规范化并写入短时缓存。
- `_check_build_ip_quota()` 在读取和修改 IP 计数之前检查环境变量与管理端开关；任一关闭就直接返回，不执行 IP 额度判断，也不写入 IP 使用次数。
- 管理端不可达、响应缺少字段或响应异常时，按 `false` 处理，避免误伤正常构建。
- clientId、用户每日次数和付费额度仍在原有后端启动路径执行，不受该开关影响。

涉及文件：

- `web/backend/admin_client.py`
- `web/backend/main.py`

## 状态与异常处理

- 关闭开关不会删除 `/app/data/build-ip-quota-state.json`，便于保留诊断依据。
- 开关关闭期间不增加 IP 计数。
- 当天重新开启时会继续使用已有计数，因此在修复真实 IP 代理链后，应先评估并按需清理当天错误的 `172.18.0.1` 记录。
- 管理端保存失败时保持原值并显示现有错误提示，不在客户端侧自行猜测开启状态。

## 测试与验收

- 管理端后端：验证默认值为关闭、更新后可持久化、客户端接口包含该字段。
- 用户端后端：验证管理端关闭或不可达时跳过 IP 限额，开启且环境变量开启时仍执行原有限额。
- 管理端前端：验证开关加载、保存和刷新后的状态一致。
- 远程部署：先将线上数据库值明确设置为 `false`，再更新服务；确认任务启动不再因 IP 限额返回 429，同时其他配额逻辑保持不变。

## 发布范围

- 管理端后端与管理端前端需要更新。
- 用户端后端需要更新。
- 用户端前端、构建器和 Android 模板无需修改。
- 远程工作树存在本地改动，发布时必须先备份目标文件并采用最小文件覆盖，不执行仓库级强制重置。
