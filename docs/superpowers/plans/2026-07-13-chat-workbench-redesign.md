# Chat Workbench Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将本地研发知识工作台改造成可折叠侧栏、集中会话历史、明暗主题和现代对话流的中文单人 AI 工作台。

**Architecture:** 保留 FastAPI 静态托管与原生 ES modules。HTML 负责稳定信息结构，CSS 变量负责主题和响应式，现有模块继续负责各自业务；后端仅增加首条消息自动命名和中文 `/docs`。

**Tech Stack:** FastAPI, SQLite, 原生 HTML/CSS/JavaScript, Node test runner, pytest, Headless Chrome

---

### Task 1: Regression Tests

**Files:**
- Modify: `frontend/asset-version.test.mjs`
- Create: `frontend/workbench.test.mjs`
- Modify: `backend/tests/integration/test_backend_flow.py`

- [ ] 写测试断言侧栏包含会话历史、折叠按钮、主题按钮和 API 入口。
- [ ] 写测试断言候选列表只保留 `pending` 状态。
- [ ] 写集成测试断言首条用户消息后会话标题不再是 `New conversation`。
- [ ] 写集成测试断言 `/docs` 返回中文页面。
- [ ] 运行 `node --test *.test.mjs js/api.test.mjs` 和目标 pytest，确认测试因功能缺失而失败。

### Task 2: Memory Behavior

**Files:**
- Modify: `frontend/js/memories.js`
- Modify: `frontend/js/api.js`

- [ ] 导出并使用 `pendingCandidates(items)`，只渲染待确认项。
- [ ] 拒绝成功后按 id 立即移除候选并重新渲染。
- [ ] 删除 SQLite 和 Pinecone 中已确认的乱码记忆。
- [ ] 运行前端测试确认候选行为通过。

### Task 3: Conversation Titles

**Files:**
- Modify: `backend/app/application/chat.py`
- Test: `backend/tests/integration/test_backend_flow.py`

- [ ] 在写入首条用户消息时生成不超过 24 个字符的主题标题。
- [ ] 保留用户手动重命名标题，不覆盖已有非默认标题。
- [ ] 运行目标测试和后端全量测试。

### Task 4: Sidebar And Chat Layout

**Files:**
- Modify: `frontend/index.html`
- Modify: `frontend/js/app.js`
- Modify: `frontend/js/chat.js`
- Rewrite: `frontend/css/style.css`

- [ ] 将会话列表移动进侧栏并增加独立滚动容器。
- [ ] 增加桌面折叠、移动抽屉、主题切换和 API 导航。
- [ ] 在会话条目上增加重命名和删除按钮。
- [ ] 重做用户/助手消息和底部输入区，确保输入区始终完整可见。
- [ ] 增加浅色、深色 CSS 变量和圆角控件规则。
- [ ] 升级静态资源版本号并运行 Node 测试。

### Task 5: Chinese API Page

**Files:**
- Create: `frontend/docs.html`
- Modify: `backend/app/main.py`
- Test: `backend/tests/integration/test_backend_flow.py`

- [ ] 禁用默认 Swagger `/docs` 路由并让 `/docs` 返回中文 API 概览。
- [ ] 保留 `/openapi.json`，在概览页提供链接。
- [ ] 运行目标测试确认中文内容和 200 响应。

### Task 6: Verification

**Files:**
- No production changes expected

- [ ] 运行全部 Node 测试和 `node --check frontend/js/*.js`。
- [ ] 运行 `backend/.venv/Scripts/python.exe -m pytest -q`。
- [ ] 使用全新 Chrome profile 渲染桌面浅色、桌面深色和移动端截图。
- [ ] 检查侧栏滚动、消息布局、候选拒绝、主题持久化和输入区边界。
