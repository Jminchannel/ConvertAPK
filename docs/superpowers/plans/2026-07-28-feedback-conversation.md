# 反馈会话 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** 为指定客户端实现启动时一次性显示的管理端反馈回复会话，并支持双方图片附件。

**Architecture:** 管理端以 feedback 作为工单、feedback_messages 作为消息流。用户端后端通过现有 adminhub 代理受保护的收件箱、会话、已读和附件请求；用户端前端只在初始化时取一次收件箱并使用本地队列显示未读消息。

**Tech Stack:** FastAPI、SQLAlchemy、PostgreSQL JSONB、Vue 3、Axios、Vite、Docker Compose。

## Global Constraints

- 不实现定时轮询、SSE、WebSocket 或后台刷新。
- 所有新增注释使用中文，文件为 UTF-8 无 BOM。
- 单条消息最多 5 张图片、每张最大 10MB，只接受 JPEG、PNG、WEBP、GIF 并解码验证。
- 明文工单访问凭据只在创建反馈响应中返回一次；数据库、日志和 URL 中不得记录。
- 历史反馈不补发凭据、不回投客户端，管理端必须标识该限制。
- 主仓库与管理端仓库独立提交、推送和部署。

---

### Task 1: 管理端会话模型与启动迁移

**Files:**

- Modify: admin/backend/app/models.py
- Modify: admin/backend/app/main.py
- Create: admin/backend/tests/test_feedback_conversation.py

**Interfaces:**

- Produces: Feedback.client_access_token_hash、Feedback.client_access_enabled、FeedbackMessage。
- Produces: create_feedback_access_token() 和 verify_feedback_access_token()。

- [ ] **Step 1: 写入失败测试**

~~~python
def test_feedback_token_is_hashed_and_verifiable():
    token, token_hash = create_feedback_access_token()
    assert token != token_hash
    assert verify_feedback_access_token(token_hash, token)
~~~

- [ ] **Step 2: 运行测试确认失败**

Run: backend/.venv/Scripts/python.exe -m unittest discover -s backend/tests -p "test_feedback_conversation.py" -v

Expected: FAIL，模型和凭据函数不存在。

- [ ] **Step 3: 实现模型、哈希凭据与幂等迁移**

~~~python
class FeedbackMessage(Base):
    __tablename__ = "feedback_messages"
    id = Column(Integer, primary_key=True)
    feedback_id = Column(Integer, ForeignKey("feedback.id"), nullable=False)
    sender_type = Column(String(16), nullable=False)
    content = Column(Text, nullable=False, default="")
    content_i18n_json = Column(JSONB, nullable=True)
    image_paths_json = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    client_read_at = Column(DateTime, nullable=True)
    admin_read_at = Column(DateTime, nullable=True)
~~~

使用 secrets.token_urlsafe(32) 和 SHA-256；用 hmac.compare_digest 验证。启动迁移仅补充列和索引，不为旧数据生成凭据。

- [ ] **Step 4: 运行模型测试与编译检查**

Run: backend/.venv/Scripts/python.exe -m unittest discover -s backend/tests -p "test_feedback_conversation.py" -v; backend/.venv/Scripts/python.exe -m compileall -q app

Expected: PASS。

- [ ] **Step 5: 提交持久化改动**

~~~powershell
git -C admin add backend/app/models.py backend/app/main.py backend/tests/test_feedback_conversation.py
git -C admin commit -m "feat: add feedback conversation persistence"
~~~

### Task 2: 管理端安全会话与附件接口

**Files:**

- Modify: admin/backend/app/routes/client_feedback.py
- Modify: admin/backend/app/routes/admin_feedback.py
- Modify: admin/backend/app/schemas.py
- Modify: admin/backend/app/utils.py
- Modify: admin/backend/tests/test_feedback_conversation.py

**Interfaces:**

- Consumes: FeedbackMessage 和工单凭据函数。
- Produces: 管理端消息读取/发送、客户端收件箱、回复、已读和附件接口。

- [ ] **Step 1: 写入失败测试，覆盖错误凭据和跨工单消息**

~~~python
def test_inbox_excludes_wrong_ticket_token(client):
    response = client.post("/api/client/feedback/inbox", json={
        "client_id": "client_a",
        "tickets": [{"feedback_id": 1, "access_token": "wrong"}],
    }, headers=client_token_headers())
    assert response.status_code == 200
    assert response.json() == []
~~~

- [ ] **Step 2: 运行测试确认失败**

Run: backend/.venv/Scripts/python.exe -m unittest discover -s backend/tests -p "test_feedback_conversation.py" -v

Expected: FAIL，新路由未注册。

- [ ] **Step 3: 实现客户端令牌接口和附件验证**

~~~python
@router.post("/inbox")
def list_unread_feedback_messages(
    payload: FeedbackInboxRequest,
    db: Session = Depends(db_session),
    _: None = Depends(require_client_token),
):
    return serialize_authorized_unread_messages(payload, db)

@router.post("/{feedback_id}/messages/{message_id}/read")
def mark_feedback_message_read(
    feedback_id: int,
    message_id: int,
    payload: FeedbackTicketAccessPayload,
    db: Session = Depends(db_session),
    _: None = Depends(require_client_token),
):
    return mark_authorized_message_read(feedback_id, message_id, payload, db)
~~~

上传时先完成全部图片解码、数量、大小和路径验证，再落库创建消息；失败时清理本次文件。附件下载只接受消息 ID 和受校验凭据，使用 FileResponse 返回。

- [ ] **Step 4: 实现管理员 JWT 会话接口**

GET /api/admin/feedback/{feedback_id}/messages 返回原始反馈与后续消息，并确认客户端消息已读。POST 接收三语正文和图片，创建管理员消息。无客户端凭据的历史工单返回 client_access_enabled=false。

- [ ] **Step 5: 运行管理端测试和编译检查**

Run: backend/.venv/Scripts/python.exe -m unittest discover -s backend/tests -p "test_feedback_conversation.py" -v; backend/.venv/Scripts/python.exe -m compileall -q app

Expected: PASS。

- [ ] **Step 6: 提交管理端接口改动**

~~~powershell
git -C admin add backend/app/routes/client_feedback.py backend/app/routes/admin_feedback.py backend/app/schemas.py backend/app/utils.py backend/tests/test_feedback_conversation.py
git -C admin commit -m "feat: add secure feedback message APIs"
~~~

### Task 3: 管理端会话页面与图片回复

**Files:**

- Modify: admin/frontend/src/api.js
- Modify: admin/frontend/src/App.vue
- Create: admin/frontend/src/feedbackConversation.js

**Interfaces:**

- Consumes: 管理端会话读取和发送接口。
- Produces: 展开会话、图片预览、三语管理员回复与历史工单状态提示。

- [ ] **Step 1: 写入失败的语言回退断言**

~~~javascript
import { selectMessageText } from "./src/feedbackConversation.js"
console.assert(selectMessageText({ "zh-CN": "中文", en: "English" }, "en") === "English")
~~~

- [ ] **Step 2: 运行断言确认失败**

Run: node -e "import('./src/feedbackConversation.js').then(() => process.exit(0)).catch(() => process.exit(1))"

Expected: FAIL，模块不存在。

- [ ] **Step 3: 实现 API、会话状态与图片发送**

新增读取和发送消息 API。反馈列表可展开消息时间线，消息图片以 Blob URL 预览并在关闭时释放。可回投工单显示三语回复框和图片选择；历史工单只展示历史并显示不可回投提示。

- [ ] **Step 4: 运行模块断言和生产构建**

Run: node -e "import('./src/feedbackConversation.js').then(() => process.exit(0))"; npm run build

Expected: PASS。

- [ ] **Step 5: 提交管理端前端改动**

~~~powershell
git -C admin add frontend/src/api.js frontend/src/App.vue frontend/src/feedbackConversation.js
git -C admin commit -m "feat: add feedback conversation management UI"
~~~

### Task 4: 用户端后端 adminhub 代理

**Files:**

- Modify: web/backend/admin_client.py
- Modify: web/backend/main.py
- Create: web/backend/tests/test_feedback_proxy.py

**Interfaces:**

- Consumes: 管理端 /api/client/feedback/* 与 X-Client-Token。
- Produces: 用户端创建、收件箱、回复、已读和 Blob 附件代理接口。

- [ ] **Step 1: 写入失败测试**

~~~python
def test_inbox_proxy_forwards_ticket_credentials(monkeypatch):
    captured = {}
    monkeypatch.setattr(admin_client, "_request_json", lambda *args, **kwargs: captured.update(kwargs) or [])
    admin_client.fetch_feedback_inbox("client_a", [{"feedback_id": 7, "access_token": "secret"}])
    assert captured["payload"]["tickets"][0]["access_token"] == "secret"
~~~

- [ ] **Step 2: 运行测试确认失败**

Run: D:/Apps/ConvertAPK-EXE/web/backend/.venv/Scripts/python.exe -m unittest discover -s web/backend/tests -p "test_feedback_proxy.py" -v

Expected: FAIL，新代理函数不存在。

- [ ] **Step 3: 实现管理端客户端 API 适配器**

submit_feedback() 返回 {ok, feedback_id, access_token}。新增收件箱、回复、已读和二进制附件函数；日志只记录反馈/消息 ID，不记录凭据。

- [ ] **Step 4: 实现 adminhub 路由并限制代理上传**

创建请求使用显式 JSON/表单模型；图片在读取前验证数量和累计大小。附件用 StreamingResponse 返回已校验的内容类型，错误凭据或错误归属转换为 403/404。

- [ ] **Step 5: 运行用户端所有后端测试**

Run: D:/Apps/ConvertAPK-EXE/web/backend/.venv/Scripts/python.exe -m unittest discover -s web/backend/tests -p "test_*.py" -v

Expected: PASS。

- [ ] **Step 6: 提交主仓库后端改动**

~~~powershell
git add web/backend/admin_client.py web/backend/main.py web/backend/tests/test_feedback_proxy.py
git commit -m "feat: proxy secure feedback conversations"
~~~

### Task 5: 用户端启动收件箱、弹窗与会话回复

**Files:**

- Modify: web/frontend/src/api/index.js
- Modify: web/frontend/src/composables/useAppState.js
- Modify: web/frontend/src/App.vue
- Modify: web/frontend/src/style.css
- Create: web/frontend/src/utils/feedbackConversation.js
- Create: web/frontend/tests/feedbackConversation.test.mjs

**Interfaces:**

- Consumes: adminhub 创建、收件箱、已读、回复和附件接口。
- Produces: 本地凭据、单次启动收件箱、右下角弹窗队列和会话回复界面。

- [ ] **Step 1: 写入失败的单次启动和语言回退测试**

~~~javascript
const guard = createFeedbackInboxGuard()
console.assert(guard.consume() === true)
console.assert(guard.consume() === false)
console.assert(selectAdminMessageText({ "zh-CN": "中文" }, "en") === "中文")
~~~

- [ ] **Step 2: 运行测试确认失败**

Run: node web/frontend/tests/feedbackConversation.test.mjs

Expected: FAIL，辅助模块不存在。

- [ ] **Step 3: 保存凭据并实现一次收件箱请求**

创建反馈成功后保存工单 ID 与凭据。loadFeedbackInboxOnce() 使用布尔守卫确保本应用实例只调用一次，关闭、回复和前台切换均不会触发新的收件箱请求。

- [ ] **Step 4: 实现弹窗队列、已读确认和会话图片回复**

未读消息按时间排队且一次只显示一条。关闭和回复入口均确认已读；回复支持文字、图片和纯图片，成功后本地追加消息但不刷新收件箱。图片通过 POST Blob 下载，不将凭据放入 URL。

- [ ] **Step 5: 运行前端测试与生产构建**

Run: node web/frontend/tests/feedbackConversation.test.mjs; cd web/frontend; npm run build

Expected: PASS。

- [ ] **Step 6: 提交主仓库前端改动**

~~~powershell
git add web/frontend/src/api/index.js web/frontend/src/composables/useAppState.js web/frontend/src/App.vue web/frontend/src/style.css web/frontend/src/utils/feedbackConversation.js web/frontend/tests/feedbackConversation.test.mjs
git commit -m "feat: show feedback replies on client startup"
~~~

### Task 6: 完整验证、推送与远程 Docker 部署

**Files:**

- Verify: docker-compose.yml
- Verify: admin/backend/Dockerfile
- Verify: admin/frontend/Dockerfile

**Interfaces:**

- Consumes: 两个仓库的已提交分支与远程 Docker Compose 项目。
- Produces: 两个远程分支、线上迁移、四个重建服务和健康检查结果。

- [ ] **Step 1: 运行完整验证**

Run: D:/Apps/ConvertAPK-EXE/web/backend/.venv/Scripts/python.exe -m unittest discover -s web/backend/tests -p "test_*.py" -v; cd admin/backend; ./.venv/Scripts/python.exe -m unittest discover -s tests -p "test_*.py" -v; cd ../frontend; npm run build; cd ../../web/frontend; npm run build

Expected: 所有存在的测试通过，两个 Vite 构建成功。

- [ ] **Step 2: 检查精确改动并推送两个分支**

~~~powershell
git status --short
git -C admin status --short
git push -u origin codex/feedback-conversation
git -C admin push -u origin codex/feedback-conversation
~~~

Expected: 不包含构建产物、.venv、存储文件或凭据；两个分支均推送成功。

- [ ] **Step 3: 备份并应用线上精确补丁**

先通过 SSH 核对 /data/ConvertAPK-Desktop 与其 admin 子仓库状态，备份本次涉及源文件；然后从已推送提交生成和验证精确补丁，避免覆盖线上脏改动。

- [ ] **Step 4: 重建服务并验证健康**

Run: docker compose -p convertapk-desktop up -d --no-deps --build backend frontend admin-backend admin-frontend

Expected: 四项服务均为 Up，数据库启动迁移无异常，8000、9001、8080 和 9002 的健康请求成功。
