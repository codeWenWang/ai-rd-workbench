# Model Comparison and Provider Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将模型对比结果持久化到对话消息流，并为模型配置增加完整的查看、编辑和删除能力。

**Architecture:** 在消息表增加通用 JSON 元数据列，对比助手消息用该列保存两个模型结果；对比 API 负责会话持久化并返回可读模型名称。模型配置通过新增 PATCH 接口更新数据库和加密密钥，前端使用管理抽屉维护供应商。

**Tech Stack:** FastAPI、SQLAlchemy、SQLite、原生 JavaScript、CSS、Node.js test runner、pytest

---

### Task 1: 模型配置编辑 API

**Files:**
- Modify: `backend/tests/unit/infrastructure/test_model_gateway.py`
- Modify: `backend/tests/integration/test_project_api.py`
- Modify: `backend/app/infrastructure/db/repositories.py`
- Modify: `backend/app/application/models.py`
- Modify: `backend/app/api/model_providers.py`

- [ ] **Step 1: 写失败测试**

测试重命名、修改模型信息、API Key 留空保留旧密钥，以及 PATCH 响应不包含明文密钥。

```python
updated = use_case.update(provider.id, name="DeepSeek V4", model_name="deepseek-v4", api_key="")
assert updated.name == "DeepSeek V4"
assert secrets.get(provider.secret_ref) == "sk-provider-secret"

response = client.patch(f"/api/model-providers/{provider_id}", json={"name": "新名称"})
assert response.status_code == 200
assert response.json()["name"] == "新名称"
assert "api_key" not in response.json()
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `backend/.venv/Scripts/python.exe -m pytest tests/unit/infrastructure/test_model_gateway.py tests/integration/test_project_api.py -q`

Expected: FAIL，缺少 `update` 和 PATCH 路由。

- [ ] **Step 3: 实现最小更新链路**

仓储更新非空字段；用例校验合并后的配置，仅在 `api_key.strip()` 非空时更新加密密钥；API 清除 `model_gateway` 和 `chat_use_case` 缓存。

- [ ] **Step 4: 验证测试通过**

Run: `backend/.venv/Scripts/python.exe -m pytest tests/unit/infrastructure/test_model_gateway.py tests/integration/test_project_api.py -q`

Expected: PASS。

### Task 2: 对比回合持久化

**Files:**
- Modify: `backend/tests/integration/test_project_api.py`
- Modify: `backend/tests/unit/projects/test_project_repository.py`
- Modify: `backend/app/domain/entities.py`
- Modify: `backend/app/infrastructure/db/models.py`
- Modify: `backend/app/infrastructure/db/session.py`
- Modify: `backend/app/infrastructure/db/repositories.py`
- Modify: `backend/app/application/chat.py`
- Modify: `backend/app/api/model_providers.py`

- [ ] **Step 1: 写失败测试**

```python
result = client.post("/api/models/compare", json={
    "message": "比较模型", "model_ids": [first_id, second_id], "session_id": session_id,
})
assert result.json()["session_id"] == session_id
assert result.json()["items"][0]["provider_name"] == "模型 A"
messages = client.get(f"/api/conversations/{session_id}/messages").json()["items"]
assert [item["role"] for item in messages] == ["user", "assistant"]
assert messages[-1]["metadata"]["type"] == "model_comparison"
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `backend/.venv/Scripts/python.exe -m pytest tests/integration/test_project_api.py tests/unit/projects/test_project_repository.py -q`

Expected: FAIL，消息没有元数据且对比接口不持久化。

- [ ] **Step 3: 实现消息元数据和对比持久化**

`messages.metadata_json` 默认 `{}`，旧数据库通过 `PRAGMA table_info(messages)` 自动执行 `ALTER TABLE`。`Message` 实体暴露 `metadata`；对比用例创建/复用会话，保存用户消息和带 `model_comparison` 元数据的助手消息。

- [ ] **Step 4: 验证测试通过**

Run: `backend/.venv/Scripts/python.exe -m pytest tests/integration/test_project_api.py tests/unit/projects/test_project_repository.py -q`

Expected: PASS。

### Task 3: 对话内对比展示和模型管理面板

**Files:**
- Modify: `frontend/workbench.test.mjs`
- Modify: `frontend/js/api.test.mjs`
- Modify: `frontend/index.html`
- Modify: `frontend/js/api.js`
- Modify: `frontend/js/chat.js`
- Modify: `frontend/js/models.js`
- Modify: `frontend/css/style.css`

- [ ] **Step 1: 写失败测试**

断言页面不再存在独立 `comparison-results`，聊天模块支持 `model_comparison` 消息，模型模块调用更新和删除 API，CSS 为消息内对比回合提供双栏与移动端单栏布局。

```javascript
assert.doesNotMatch(html, /id="comparison-results"/);
assert.match(chatSource, /model_comparison/);
assert.match(chatSource, /comparison-turn/);
assert.match(modelsSource, /updateModelProvider/);
assert.match(modelsSource, /deleteModelProvider/);
assert.match(css, /\.comparison-turn/);
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `node --test frontend/workbench.test.mjs frontend/js/api.test.mjs`

Expected: FAIL，仍存在独立结果区且缺少模型更新调用。

- [ ] **Step 3: 实现消息内对比组件**

`normalizeMessage()` 读取 `metadata.type`；`messageNode()` 为 `model_comparison` 创建带标题和双模型卡片的助手消息。`sendComparison()` 先确保会话、追加用户消息和加载态对比消息，再用 API 响应更新该消息。

- [ ] **Step 4: 实现模型管理抽屉**

“模型设置”打开已配置模型列表，提供“添加模型”“编辑”“删除”。编辑表单 API Key 非必填并显示“留空保持原密钥”。操作完成后刷新两个模型选择器和管理抽屉。

- [ ] **Step 5: 验证前端测试通过**

Run: `node --test frontend/*.test.mjs frontend/js/*.test.mjs`

Expected: 全部通过。

### Task 4: 回归与浏览器验收

**Files:**
- Test: `backend/tests`
- Test: `frontend/*.test.mjs`
- Test: `frontend/js/*.test.mjs`

- [ ] **Step 1: 运行完整测试**

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest
cd ..
node --test frontend\*.test.mjs frontend\js\*.test.mjs
```

Expected: 后端和前端全部通过。

- [ ] **Step 2: 浏览器验收**

使用两个固定假模型验证：对比问题和结果位于消息列表、标题无 UUID、刷新后恢复、移动端堆叠；打开模型设置验证添加、重命名和删除。

- [ ] **Step 3: 提交并推送**

```powershell
git add backend frontend
git commit -m "feat: 优化模型对比与配置管理"
git push origin main
```
