import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';


test('sidebar owns project workspace, conversations, theme, and bottom diagnostics', async () => {
  const html = await readFile(new URL('./index.html', import.meta.url), 'utf8');
  const start = html.indexOf('<aside class="sidebar"');
  const end = html.indexOf('</aside>', start);
  const sidebar = html.slice(start, end);

  assert.match(sidebar, /id="sidebar-collapse"/);
  assert.match(sidebar, /id="new-conversation"/);
  assert.match(sidebar, /id="project-selector"/);
  assert.match(sidebar, /id="add-project"/);
  assert.match(sidebar, /class="analysis-nav collapsed"/);
  assert.match(sidebar, /id="analysis-toggle"[^>]*aria-expanded="false"/);
  assert.match(sidebar, /id="analysis-menu"/);
  assert.match(sidebar, /data-view="architecture"/);
  assert.match(sidebar, /data-view="flow"/);
  assert.match(sidebar, /data-view="sequence"/);
  assert.match(sidebar, /data-view="project-api"/);
  assert.match(sidebar, /id="conversation-list"/);
  assert.match(sidebar, /id="theme-toggle"/);
  assert.match(sidebar, /id="diagnostics-toggle"/);
  assert.doesNotMatch(sidebar, /href="\/docs"/);
  assert.doesNotMatch(html, /class="conversation-panel"/);
  assert.match(html, /id="remove-project"/);
});


test('platform brand uses the new name and a graphical logo without an edition subtitle', async () => {
  const html = await readFile(new URL('./index.html', import.meta.url), 'utf8');

  assert.match(html, /<title>AI研发赋能平台<\/title>/);
  assert.match(html, /aria-label="AI研发赋能平台首页"/);
  assert.match(html, /<strong>AI研发赋能平台<\/strong>/);
  assert.match(html, /class="brand-logo"/);
  assert.match(html, /<svg[^>]*viewBox="0 0 32 32"/);
  assert.doesNotMatch(html, /本地单人增强版/);
  assert.doesNotMatch(html, /研发知识工作台/);
});


test('dark theme keeps the platform logo on a dark high-contrast surface', async () => {
  const css = await readFile(new URL('./css/style.css', import.meta.url), 'utf8');
  const darkBrand = css.match(/html\[data-theme="dark"\] \.brand-mark\s*\{([^}]*)\}/)?.[1] || '';

  assert.match(darkBrand, /background:\s*#[0-9a-f]{6}/i);
  assert.match(darkBrand, /border-color:/);
  assert.doesNotMatch(darkBrand, /var\(--text\)/);
});


test('assistant messages render as an avatar-free content stream', async () => {
  const chatSource = await readFile(new URL('./js/chat.js', import.meta.url), 'utf8');
  const css = await readFile(new URL('./css/style.css', import.meta.url), 'utf8');

  assert.doesNotMatch(chatSource, /assistant-avatar/);
  assert.doesNotMatch(css, /\.assistant-avatar/);
  assert.match(css, /\.message\.assistant \.message-content\s*\{[^}]*width:\s*100%/s);
});


test('model comparison uses cards without a decorative left rule', async () => {
  const css = await readFile(new URL('./css/style.css', import.meta.url), 'utf8');
  const comparisonTurn = css.match(/\.comparison-turn\s*\{([^}]*)\}/)?.[1] || '';
  const comparisonRules = [...css.matchAll(/\.comparison-turn\s*\{([^}]*)\}/g)].map(match => match[1]).join('\n');

  assert.doesNotMatch(comparisonTurn, /border-left/);
  assert.match(comparisonTurn, /padding:\s*2px 0/);
  assert.doesNotMatch(comparisonRules, /padding-left/);
  assert.match(css, /\.message\.comparison-message\s*\{[^}]*width:\s*min\(860px,\s*100%\)/s);
});


test('stylesheet defines collapsed sidebar, dark theme, and safe composer', async () => {
  const css = await readFile(new URL('./css/style.css', import.meta.url), 'utf8');

  assert.match(css, /html\[data-theme="dark"\]/);
  assert.match(css, /\.app-shell\.sidebar-collapsed/);
  assert.match(css, /\.composer-shell/);
  assert.match(css, /padding-bottom:\s*max\(/);
  assert.match(css, /\.composer-shell\s*\{[^}]*grid-row:\s*4/s);
  assert.match(css, /\.analysis-nav\.collapsed \.analysis-menu/);
  assert.match(css, /\.analysis-nav\.collapsed \.analysis-menu\s*\{[^}]*visibility:\s*hidden/s);
  assert.match(css, /\.analysis-nav:not\(\.collapsed\) \.analysis-chevron/);
  assert.doesNotMatch(css, /\.alert-stack:empty\s*\{[^}]*display:\s*none/s);
});


test('project analysis navigation defaults closed and toggles locally', async () => {
  const appSource = await readFile(new URL('./js/app.js', import.meta.url), 'utf8');

  assert.match(appSource, /function setAnalysisExpanded\(expanded\)/);
  assert.match(appSource, /setAnalysisExpanded\(false\)/);
  assert.match(appSource, /analysis-toggle[\s\S]*setAnalysisExpanded/);
});


test('project analysis descriptions are module-oriented and framework-neutral', async () => {
  const html = await readFile(new URL('./index.html', import.meta.url), 'utf8');

  assert.match(html, /展示项目模块、职责与依赖关系/);
  assert.match(html, /展示代表性入口到核心模块的主要路径/);
  assert.match(html, /展示代表性场景中的组件调用顺序/);
  assert.match(html, /来自静态分析的已识别接口/);
  assert.doesNotMatch(html, /FastAPI 路由资料/);
});


test('mobile architecture keeps a readable canvas inside its scroll container', async () => {
  const artifactsSource = await readFile(new URL('./js/artifacts.js', import.meta.url), 'utf8');
  const css = await readFile(new URL('./css/style.css', import.meta.url), 'utf8');

  assert.match(artifactsSource, /artifact-\$\{view\.dataset\.artifactType\}/);
  assert.match(css, /@media \(max-width: 760px\)[\s\S]*\.artifact-diagram\.artifact-architecture[\s\S]*min-width:\s*520px/);
  assert.match(css, /\.artifact-diagram\.artifact-architecture svg[\s\S]*max-width:\s*100%/);
});


test('dark Mermaid diagrams use high-contrast connectors and rerender on theme changes', async () => {
  globalThis.localStorage ??= { getItem: () => null, setItem: () => {} };
  const artifacts = await import(`./js/artifacts.js?test=${Date.now()}`);
  const appSource = await readFile(new URL('./js/app.js', import.meta.url), 'utf8');
  const artifactsSource = await readFile(new URL('./js/artifacts.js', import.meta.url), 'utf8');
  const css = await readFile(new URL('./css/style.css', import.meta.url), 'utf8');

  assert.equal(typeof artifacts.mermaidThemeConfig, 'function');
  const config = artifacts.mermaidThemeConfig('dark');
  assert.equal(config.theme, 'base');
  assert.match(config.themeVariables.lineColor, /^#[0-9a-f]{6}$/i);
  assert.match(config.themeVariables.signalColor, /^#[0-9a-f]{6}$/i);
  assert.match(config.themeVariables.signalTextColor, /^#[0-9a-f]{6}$/i);
  assert.notEqual(config.themeVariables.lineColor, config.themeVariables.background);
  assert.match(appSource, /ui\.emit\('theme:changed', theme\)/);
  assert.match(artifactsSource, /ui\.on\('theme:changed', renderAll\)/);
  assert.match(css, /html\[data-theme="dark"\] \.artifact-diagram svg marker path/);
  assert.match(css, /html\[data-theme="dark"\] \.artifact-diagram svg \.messageText/);
});


test('project connection supports local GitHub and Gitee sources', async () => {
  const projectsSource = await readFile(new URL('./js/projects.js', import.meta.url), 'utf8');
  const apiSource = await readFile(new URL('./js/api.js', import.meta.url), 'utf8');

  assert.match(projectsSource, /name: 'source_type'/);
  assert.match(projectsSource, /\['github', 'GitHub'/);
  assert.match(projectsSource, /\['gitee', 'Gitee'/);
  assert.match(projectsSource, /requiredWhen: \{ source_type: 'local' \}/);
  assert.match(projectsSource, /requiredWhen: \{ source_type: 'github' \}/);
  assert.match(projectsSource, /requiredWhen: \{ source_type: 'gitee' \}/);
  assert.match(projectsSource, /repository_url/);
  assert.match(projectsSource, /source_uri/);
  assert.match(projectsSource, /GitHub/);
  assert.match(projectsSource, /Gitee/);
  assert.match(apiSource, /createProject:[^\n]*timeout:\s*210000/);
});


test('project operation alerts replace stale messages and expose scan progress', async () => {
  const appSource = await readFile(new URL('./js/app.js', import.meta.url), 'utf8');
  const projectsSource = await readFile(new URL('./js/projects.js', import.meta.url), 'utf8');
  const css = await readFile(new URL('./css/style.css', import.meta.url), 'utf8');

  assert.match(appSource, /container\.replaceChildren\(box\)/);
  assert.doesNotMatch(appSource, /container\.append\(box\)/);
  assert.match(projectsSource, /正在扫描项目/);
  assert.match(projectsSource, /本次扫描完成/);
  assert.match(projectsSource, /toLocaleTimeString\('zh-CN'/);
  assert.match(css, /\.inline-alert\.progress/);
});


test('project analysis and workspace share one project state module', async () => {
  const appSource = await readFile(new URL('./js/app.js', import.meta.url), 'utf8');
  const artifactsSource = await readFile(new URL('./js/artifacts.js', import.meta.url), 'utf8');
  const chatSource = await readFile(new URL('./js/chat.js', import.meta.url), 'utf8');
  const projectImport = source => source.match(/from ['"](\.\/projects\.js\?v=[^'"]+)['"]/)?.[1];

  assert.equal(projectImport(artifactsSource), projectImport(appSource));
  assert.equal(projectImport(chatSource), projectImport(appSource));
});


test('memory candidates only expose pending suggestions', async () => {
  const module = await import(`./js/memories.js?test=${Date.now()}`);

  assert.equal(typeof module.pendingCandidates, 'function');
  assert.deepEqual(
    module.pendingCandidates([
      { id: 'pending', status: 'pending' },
      { id: 'rejected', status: 'rejected' },
      { id: 'confirmed', status: 'confirmed' },
    ]).map(item => item.id),
    ['pending'],
  );
});


test('selecting a recent conversation requests the chat view', async () => {
  const appSource = await readFile(new URL('./js/app.js', import.meta.url), 'utf8');
  const chatSource = await readFile(new URL('./js/chat.js', import.meta.url), 'utf8');

  assert.match(appSource, /showView:\s*switchView/);
  assert.match(chatSource, /async function selectConversation[\s\S]*?ui\.showView\('chat'\)/);
});


test('recent conversations render generic items and collapsible project groups', async () => {
  const chatSource = await readFile(new URL('./js/chat.js', import.meta.url), 'utf8');
  const css = await readFile(new URL('./css/style.css', import.meta.url), 'utf8');

  assert.match(chatSource, /import \{ groupConversations \}/);
  assert.match(chatSource, /expandedProjectIds/);
  assert.match(chatSource, /project-history-group/);
  assert.match(chatSource, /project-history-toggle/);
  assert.match(chatSource, /aria-expanded/);
  assert.match(chatSource, /api\.conversations\(\)/);
  assert.match(css, /\.project-history-group\.collapsed \.project-conversation-panel/);
  assert.match(css, /\.project-history-chevron/);
});


test('workspace selection and deletion remain inside the matching conversation group', async () => {
  const chatSource = await readFile(new URL('./js/chat.js', import.meta.url), 'utf8');

  assert.match(chatSource, /preferredProjectId/);
  assert.match(chatSource, /normalizeProjectId/);
  assert.match(chatSource, /fallbackProjectId/);
  assert.match(chatSource, /project:changed[\s\S]*preferredProjectId/);
});


test('chat keeps model comparison inside the message timeline', async () => {
  const html = await readFile(new URL('./index.html', import.meta.url), 'utf8');
  const chatSource = await readFile(new URL('./js/chat.js', import.meta.url), 'utf8');
  const css = await readFile(new URL('./css/style.css', import.meta.url), 'utf8');

  assert.match(html, /id="chat-model"/);
  assert.match(html, /id="compare-models"/);
  assert.match(html, /id="model-settings"/);
  assert.doesNotMatch(html, /id="comparison-results"/);
  assert.match(chatSource, /model_comparison/);
  assert.match(chatSource, /comparison-turn/);
  assert.match(css, /\.comparison-turn/);
  assert.match(css, /@media \(max-width: 760px\)[\s\S]*\.comparison-grid/);
});


test('model settings manages existing providers', async () => {
  const modelsSource = await readFile(new URL('./js/models.js', import.meta.url), 'utf8');
  const css = await readFile(new URL('./css/style.css', import.meta.url), 'utf8');

  assert.match(modelsSource, /function openModelManager/);
  assert.match(modelsSource, /updateModelProvider/);
  assert.match(modelsSource, /deleteModelProvider/);
  assert.match(modelsSource, /留空保持原密钥/);
  assert.match(css, /\.model-provider-list/);
});
