# Project Analysis Collapsible Navigation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将四个项目分析入口放入默认收起、可手动展开的侧边栏分组。

**Architecture:** 保留现有单页视图切换机制，只调整侧边栏导航语义结构。`frontend/js/app.js` 负责当前页面生命周期内的展开状态，`frontend/css/style.css` 负责子菜单动画和整体侧边栏收起时的兼容行为。

**Tech Stack:** HTML5、原生 JavaScript、CSS、Node.js test runner

---

### Task 1: 定义折叠导航行为测试

**Files:**
- Modify: `frontend/workbench.test.mjs`

- [ ] **Step 1: 写入失败测试**

在侧边栏结构测试中断言 `analysis-toggle` 默认 `aria-expanded="false"`，`analysis-nav` 默认包含 `collapsed`，并新增测试断言 JavaScript 包含 `setAnalysisExpanded` 和点击切换逻辑，CSS 包含折叠菜单与箭头旋转规则。

```javascript
assert.match(sidebar, /id="analysis-toggle"[^>]*aria-expanded="false"/);
assert.match(sidebar, /class="analysis-nav collapsed"/);
assert.match(sidebar, /id="analysis-menu"/);
assert.match(appSource, /function setAnalysisExpanded\(expanded\)/);
assert.match(appSource, /analysis-toggle[\s\S]*setAnalysisExpanded/);
assert.match(css, /\.analysis-nav\.collapsed \.analysis-menu/);
assert.match(css, /\.analysis-nav:not\(\.collapsed\) \.analysis-chevron/);
```

- [ ] **Step 2: 验证测试按预期失败**

Run: `node --test frontend/workbench.test.mjs`

Expected: FAIL，指出缺少 `analysis-toggle` 或默认折叠结构。

### Task 2: 实现导航结构与交互

**Files:**
- Modify: `frontend/index.html`
- Modify: `frontend/js/app.js`
- Modify: `frontend/css/style.css`

- [ ] **Step 1: 调整 HTML 结构**

用一级按钮和子菜单容器替换静态标题：

```html
<div class="analysis-nav collapsed" id="analysis-nav">
  <button id="analysis-toggle" class="nav-item analysis-toggle" type="button"
          aria-expanded="false" aria-controls="analysis-menu" title="展开项目分析">
    <span class="nav-icon" aria-hidden="true">⌘</span>
    <span class="sidebar-label">项目分析</span>
    <span class="analysis-chevron" aria-hidden="true">›</span>
  </button>
  <div id="analysis-menu" class="analysis-menu">
    <!-- 保留四个现有 data-view 按钮 -->
  </div>
</div>
```

- [ ] **Step 2: 添加状态切换逻辑**

在 `initialize()` 中绑定按钮，并在每次加载时调用 `setAnalysisExpanded(false)`：

```javascript
function setAnalysisExpanded(expanded) {
  el('analysis-nav').classList.toggle('collapsed', !expanded);
  el('analysis-toggle').setAttribute('aria-expanded', String(expanded));
  el('analysis-toggle').title = expanded ? '收起项目分析' : '展开项目分析';
}
```

- [ ] **Step 3: 添加动画和侧边栏兼容样式**

```css
.analysis-menu {
  display: grid;
  gap: 2px;
  max-height: 190px;
  opacity: 1;
  overflow: hidden;
  transition: max-height .18s ease, opacity .15s ease;
}
.analysis-nav.collapsed .analysis-menu { max-height: 0; opacity: 0; pointer-events: none; }
.analysis-chevron { transition: transform .18s ease; }
.analysis-nav:not(.collapsed) .analysis-chevron { transform: rotate(90deg); }
.app-shell.sidebar-collapsed .analysis-menu { display: none; }
```

- [ ] **Step 4: 验证前端测试通过**

Run: `node --test frontend/workbench.test.mjs`

Expected: PASS。

### Task 3: 完整回归验证

**Files:**
- Test: `frontend/*.test.mjs`
- Test: `frontend/js/*.test.mjs`
- Test: `backend/tests`

- [ ] **Step 1: 运行全部前端测试**

Run: `node --test frontend/*.test.mjs frontend/js/*.test.mjs`

Expected: 全部通过，无失败。

- [ ] **Step 2: 运行后端测试**

Run: `backend/.venv/Scripts/python.exe -m pytest` from `backend`

Expected: `81 passed`。

- [ ] **Step 3: 检查差异并提交**

```powershell
git diff --check
git add frontend/index.html frontend/js/app.js frontend/css/style.css frontend/workbench.test.mjs
git commit -m "feat: 折叠项目分析导航"
```
