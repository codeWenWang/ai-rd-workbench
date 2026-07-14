# Project Conversation History Groups Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将最近对话按“通用对话”和项目折叠组展示，并让工作区切换只决定主区域默认打开的对话。

**Architecture:** 新增无界面的纯分组模块，把 `project_id` 为空的对话和项目对话分开；聊天模块继续负责 DOM、折叠状态和会话操作。对话列表始终全量读取，项目模块仅提供按 ID 查名称的只读能力，不修改后端数据模型。

**Tech Stack:** Vanilla JavaScript ES modules, CSS, Node.js test runner, FastAPI static frontend

---

### Task 1: Conversation grouping contract

**Files:**
- Create: `frontend/js/conversation-groups.js`
- Create: `frontend/conversation-groups.test.mjs`

- [ ] **Step 1: Write the failing grouping test**

Create a Node test that passes generic conversations and conversations from two projects to `groupConversations()`, then asserts that generic records stay in `general`, records sharing a `project_id` share one group, project names are resolved through the callback, and missing projects use `已移除项目`.

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test frontend/conversation-groups.test.mjs`

Expected: FAIL because `frontend/js/conversation-groups.js` does not exist.

- [ ] **Step 3: Implement the pure grouping function**

Implement `groupConversations(conversations, projectNameForId)` using a `Map`, preserving API order for both conversations and project groups.

- [ ] **Step 4: Run test to verify it passes**

Run: `node --test frontend/conversation-groups.test.mjs`

Expected: all grouping tests PASS.

### Task 2: Collapsible project history UI

**Files:**
- Modify: `frontend/js/projects.js`
- Modify: `frontend/js/chat.js`
- Modify: `frontend/css/style.css`
- Modify: `frontend/workbench.test.mjs`

- [ ] **Step 1: Add failing source-contract tests**

Assert that chat imports `groupConversations`, maintains `expandedProjectIds`, renders `.project-history-group` and `.project-history-toggle` with `aria-expanded`, and loads conversations without a project query. Assert that CSS contains the collapsed panel and rotating chevron states.

- [ ] **Step 2: Run frontend tests to verify failure**

Run: `node --test frontend/*.test.mjs`

Expected: new history grouping assertions FAIL while existing tests remain green.

- [ ] **Step 3: Expose project lookup and render grouped rows**

Export `projectById(projectId)` from `projects.js`. In `chat.js`, extract conversation row construction, render generic rows under `通用对话`, render project sections with name/count/chevron, and keep expanded IDs in a page-lifetime `Set`.

- [ ] **Step 4: Add responsive collapse styles**

Style project toggles as compact rounded sidebar buttons. Animate the nested panel with CSS grid rows, rotate the chevron, indent project conversations, and preserve keyboard focus and mobile usability.

- [ ] **Step 5: Run frontend tests**

Run: `node --test frontend/*.test.mjs`

Expected: all frontend tests PASS.

### Task 3: Workspace selection and same-group fallback

**Files:**
- Modify: `frontend/js/chat.js`
- Modify: `frontend/workbench.test.mjs`

- [ ] **Step 1: Add failing behavior-contract tests**

Assert that `loadConversations` accepts a preferred project, chooses only a matching project or generic conversation, and deletion falls back only to a conversation with the same `project_id`.

- [ ] **Step 2: Implement global loading with workspace preference**

Always call `api.conversations()` without filtering. On workspace changes, clear the current selection and select the newest conversation whose normalized `project_id` matches the selected workspace; if none exists, show the empty conversation state while retaining all sidebar groups.

- [ ] **Step 3: Implement same-group deletion fallback**

When deleting the active conversation, choose the newest remaining conversation from the deleted conversation's workspace only. Keep the active project group expanded when selecting or creating a project conversation.

- [ ] **Step 4: Run frontend tests**

Run: `node --test frontend/*.test.mjs`

Expected: all frontend tests PASS.

### Task 4: Cache busting and end-to-end verification

**Files:**
- Modify: `frontend/index.html`
- Modify: `frontend/js/app.js`

- [ ] **Step 1: Update frontend asset versions**

Bump the CSS, app, chat, projects, and conversation-groups module query versions together so browsers do not mix old and new modules.

- [ ] **Step 2: Run full automated tests**

Run: `node --test frontend/*.test.mjs`

Run: `E:\桌面\AI赋能平台\backend\.venv\Scripts\python.exe -m pytest backend/tests -q`

Expected: all frontend and backend tests PASS.

- [ ] **Step 3: Verify in a browser**

Start the application on an unused localhost port. Create or reuse generic and “测试项目” conversations, then verify project groups default collapsed, expand/collapse smoothly, selecting a project conversation enters chat, switching workspaces keeps all groups visible, new project conversations join the correct group, and desktop/mobile layouts remain usable.

- [ ] **Step 4: Review and commit**

Run `git diff --check`, inspect the scoped diff, remove temporary browser artifacts, then commit the tested implementation.
