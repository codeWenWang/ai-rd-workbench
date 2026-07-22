import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';


test('sidebar follows a compact Codex-style navigation and workspace hierarchy', async () => {
  const html = await readFile(new URL('./index.html', import.meta.url), 'utf8');
  const start = html.indexOf('<aside class="sidebar"');
  const end = html.indexOf('</aside>', start);
  const sidebar = html.slice(start, end);

  assert.match(sidebar, /id="sidebar-collapse"/);
  assert.match(sidebar, /id="new-conversation"/);
  assert.match(sidebar, /id="add-project"/);
  assert.match(sidebar, /id="sidebar-projects"/);
  assert.match(sidebar, /id="conversation-list"/);
  assert.match(sidebar, /id="settings-menu"/);
  assert.match(sidebar, /id="theme-toggle"/);
  assert.match(sidebar, /id="diagnostics-toggle"/);
  assert.doesNotMatch(sidebar, /id="project-selector"/);
  assert.doesNotMatch(sidebar, /项目问答/);
  assert.doesNotMatch(sidebar, /id="analysis-nav"/);
  assert.doesNotMatch(sidebar, /href="\/docs"/);
  assert.doesNotMatch(html, /class="conversation-panel"/);
  assert.match(html, /id="remove-project"/);
  assert.match(html, /class="[^"]*overview-analysis/);
  assert.match(html, /data-view="architecture"/);
  assert.match(html, /data-view="flow"/);
  assert.match(html, /data-view="sequence"/);
  assert.match(html, /data-view="project-api"/);
});


test('composer owns the primary model switcher next to the send button', async () => {
  const html = await readFile(new URL('./index.html', import.meta.url), 'utf8');
  const composerStart = html.indexOf('<form id="chat-form"');
  const composerEnd = html.indexOf('</form>', composerStart);
  const composer = html.slice(composerStart, composerEnd);

  assert.match(composer, /id="chat-model"/);
  assert.match(composer, /class="composer-model"/);
  assert.match(composer, /id="send-message"/);
});


test('sidebar uses one scroll region and a project parent beside daily conversations', async () => {
  const html = await readFile(new URL('./index.html', import.meta.url), 'utf8');
  const css = await readFile(new URL('./css/style.css', import.meta.url), 'utf8');

  assert.match(html, /class="sidebar-scroll"/);
  assert.match(html, /id="project-root-toggle"/);
  assert.match(html, /id="project-source-list"/);
  assert.match(css, /\.sidebar-scroll\s*\{[^}]*overflow-y:\s*auto/);
  assert.match(css, /\.project-source-toggle[^}]*display:\s*flex/);
  assert.match(css, /\.project-source-toggle[^}]*\.source-chevron[^}]*opacity:\s*0/);
});


test('collapsed project parent removes its layout height and keeps daily conversations directly below', async () => {
  const css = await readFile(new URL('./css/style.css', import.meta.url), 'utf8');

  assert.match(css, /\.history-section\.projects-collapsed \.project-source-list\s*\{[^}]*display:\s*none/);
  assert.doesNotMatch(css, /\.history-section\.projects-collapsed \.project-source-list\s*\{[^}]*grid-template-rows:\s*0fr/);
});


test('all hierarchy chevrons sit immediately after their labels', async () => {
  const html = await readFile(new URL('./index.html', import.meta.url), 'utf8');
  const chatSource = await readFile(new URL('./js/chat.js', import.meta.url), 'utf8');
  const css = await readFile(new URL('./css/style.css', import.meta.url), 'utf8');

  assert.match(html, /<strong id="history-title">项目<\/strong><span class="root-chevron"/);
  assert.match(chatSource, /<strong>\$\{ui\.escape\(source\.label\)\}<\/strong><span class="source-chevron"/);
  assert.match(chatSource, /<strong>日常对话<\/strong><span class="daily-chevron"/);
  assert.match(css, /\.project-root-toggle[^}]*display:\s*inline-flex/);
  assert.match(css, /\.project-source-toggle[^}]*display:\s*flex/);
});


test('project row itself toggles conversations and changes folder state without a separate arrow button', async () => {
  const chatSource = await readFile(new URL('./js/chat.js', import.meta.url), 'utf8');

  assert.doesNotMatch(chatSource, /className = 'project-history-open'/);
  assert.match(chatSource, /className = 'project-history-toggle'/);
  assert.match(chatSource, /project-history-toggle[\s\S]*folder-glyph[\s\S]*groupData\.name/);
  assert.match(chatSource, /toggle\.addEventListener\('click'[\s\S]*setProjectGroupExpanded/);
});


test('composer is a raised two-row surface with compact model and send controls', async () => {
  const css = await readFile(new URL('./css/style.css', import.meta.url), 'utf8');

  assert.match(css, /\.composer-shell[^}]*padding-bottom:\s*max\(30px/);
  assert.match(css, /\.composer\s*\{[^}]*grid-template-rows:\s*auto\s+32px/);
  assert.match(css, /\.composer textarea[^}]*grid-column:\s*1\s*\/\s*-1/);
  assert.match(css, /\.composer-model select[^}]*height:\s*28px/);
});


test('project file tree preserves nested folders and file metadata', async () => {
  globalThis.localStorage ??= { getItem: () => '', setItem: () => {}, removeItem: () => {} };
  const projects = await import(`./js/projects.js?tree-test=${Date.now()}`);

  assert.equal(typeof projects.buildProjectFileTree, 'function');
  const tree = projects.buildProjectFileTree([
    { relative_path: 'src/main/App.java', language: 'java', size_bytes: 120 },
    { relative_path: 'src/test/AppTest.java', language: 'java', size_bytes: 80 },
    { relative_path: 'README.md', language: 'markdown', size_bytes: 20 },
  ]);

  assert.equal(tree[0].name, 'src');
  assert.equal(tree[0].type, 'folder');
  assert.equal(tree[0].children[0].name, 'main');
  assert.equal(tree[0].children[0].children[0].name, 'App.java');
  assert.equal(tree[1].name, 'README.md');
  assert.equal(tree[1].sizeBytes, 20);
});


test('project guide explains capabilities and gives concrete source reading steps', async () => {
  globalThis.localStorage ??= { getItem: () => '', setItem: () => {}, removeItem: () => {} };
  const projects = await import(`./js/projects.js?guide-test=${Date.now()}`);
  const guide = projects.buildProjectGuide(
    { name: '任务平台', source_type: 'local', tech_stack: ['java', 'Spring Boot', 'vue'] },
    [
      { relative_path: 'README.md' },
      { relative_path: 'server/src/DemoApplication.java' },
      { relative_path: 'server/src/TaskController.java' },
      { relative_path: 'server/src/TaskService.java' },
      { relative_path: 'server/src/TaskRepository.java' },
      { relative_path: 'web/src/App.vue' },
    ],
    [{ method: 'GET', path: '/api/tasks' }, { method: 'POST', path: '/api/tasks' }],
  );

  assert.match(guide.summary, /任务平台/);
  assert.match(guide.summary, /Java、Spring Boot、Vue/);
  assert.match(guide.capabilities.join(' '), /2 个接口/);
  assert.deepEqual(guide.readingSteps.slice(0, 3).map(item => item.path), [
    'README.md', 'server/src/DemoApplication.java', 'server/src/TaskController.java',
  ]);
});


test('project tech stack uses backend-first and frontend-second ordering', async () => {
  globalThis.localStorage ??= { getItem: () => '', setItem: () => {}, removeItem: () => {} };
  const projects = await import(`./js/projects.js?stack-order-test=${Date.now()}`);

  assert.deepEqual(
    projects.primaryTechStack(['css', 'javascript', 'spring boot', 'html', 'java', 'sql', 'vue']),
    ['Java', 'Spring Boot', 'HTML', 'CSS', 'JavaScript', 'Vue'],
  );
});


test('project guide explains business roles instead of only scanner capabilities', async () => {
  globalThis.localStorage ??= { getItem: () => '', setItem: () => {}, removeItem: () => {} };
  const projects = await import(`./js/projects.js?business-guide-test=${Date.now()}`);
  const guide = projects.buildProjectGuide(
    { name: '图书管理系统', tech_stack: ['java', 'spring boot', 'vue'] },
    [
      { relative_path: 'README.md' },
      { relative_path: 'server/BookController.java' },
      { relative_path: 'server/BookService.java' },
      { relative_path: 'server/BookRepository.java' },
      { relative_path: 'web/src/Book.vue' },
    ],
    [
      { method: 'GET', path: '/books' },
      { method: 'POST', path: '/borrow' },
      { method: 'PUT', path: '/books/{id}' },
    ],
  );

  assert.equal(guide.businessFunctions.length, 3);
  assert.deepEqual(guide.businessFunctions.map(item => item.role), ['用户端', '管理端', '运维端']);
  assert.match(guide.businessFunctions.map(item => item.description).join(' '), /查书|借阅|归还/);
  assert.match(guide.businessFunctions.map(item => item.description).join(' '), /图书|分类|用户|借阅/);
  assert.match(guide.businessFunctions.map(item => item.description).join(' '), /日志|统计|逾期/);
});


test('project guide is one parent card with nested content panels and a half-width source drawer', async () => {
  const css = await readFile(new URL('./css/style.css', import.meta.url), 'utf8');
  const projects = await readFile(new URL('./js/projects.js', import.meta.url), 'utf8');

  assert.match(css, /\.project-introduction\s*\{[^}]*border:\s*1px solid var\(--line\)/s);
  assert.match(css, /\.guide-summary[^\{]*\{[^}]*border:\s*1px solid var\(--line\)/s);
  assert.match(css, /\.guide-business[^\{]*\{[^}]*border:\s*1px solid var\(--line\)/s);
  assert.match(css, /\.guide-business\s+section\s*\{[^}]*border:\s*1px solid var\(--line\)/s);
  assert.match(css, /\.guide-details\s*>\s*section\s*\{[^}]*border:\s*1px solid var\(--line\)/s);
  assert.match(projects, /guide-business"><h3>业务能力<\/h3>/);
  assert.match(projects, /section-kicker guide-heading">项目导读<\/span>\s*<div class="guide-summary"><h2>这个项目能做什么<\/h2>/s);
  assert.match(css, /\.detail-drawer\.wide\s*\{[^}]*width:\s*min\(50vw,/s);
  assert.doesNotMatch(css, /\.detail-drawer\.wide\s*\{[^}]*78vw/s);
});


test('endpoint source snippet contains controller context and only the selected method', async () => {
  const { sourceSnippet } = await import(`./js/source-snippet.js?endpoint-test=${Date.now()}`);
  const source = `@RestController\n@RequestMapping("/user/category")\npublic class CategoryController {\n\n    @Autowired\n    private CategoryService categoryService;\n\n    @GetMapping("/list")\n    public Result<List<Category>> list(Integer type) {\n        List<Category> list = categoryService.list(type);\n        return Result.success(list);\n    }\n\n    @DeleteMapping("/{id}")\n    public void delete(Long id) { }\n}`;

  const snippet = sourceSnippet(source, 'CategoryController.java:8', { endpoint: true });
  assert.match(snippet, /@RestController/);
  assert.match(snippet, /private CategoryService categoryService;/);
  assert.match(snippet, /@GetMapping\("\/list"\)/);
  assert.match(snippet, /return Result\.success\(list\);/);
  assert.doesNotMatch(snippet, /@DeleteMapping/);

  const compact = `@RestController\npublic class DemoController {\n@GetMapping("/old")\npublic String old() { return "old"; }\n@PostMapping("/new")\npublic String create() { return "new"; }\n}`;
  const compactSnippet = sourceSnippet(compact, 'DemoController.java:5', { endpoint: true });
  assert.match(compactSnippet, /@PostMapping\("\/new"\)/);
  assert.match(compactSnippet, /return "new"/);
  assert.doesNotMatch(compactSnippet, /@GetMapping/);
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
  assert.match(css, /\.project-source-group/);
  assert.match(css, /\.settings-popover/);
  assert.match(css, /\.project-file-tree/);
  assert.match(css, /\.composer-model/);
  assert.doesNotMatch(css, /\.alert-stack:empty\s*\{[^}]*display:\s*none/s);
});


test('project analysis entry points live inside project overview', async () => {
  const appSource = await readFile(new URL('./js/app.js', import.meta.url), 'utf8');
  const html = await readFile(new URL('./index.html', import.meta.url), 'utf8');

  assert.doesNotMatch(appSource, /setAnalysisExpanded/);
  assert.match(appSource, /button\[data-view\]/);
  assert.match(html, /class="[^"]*overview-analysis/);
});


test('project overview has useful initial content before asynchronous project loading finishes', async () => {
  const html = await readFile(new URL('./index.html', import.meta.url), 'utf8');

  assert.match(html, /id="project-stats"[\s\S]*当前项目[\s\S]*未选择/);
  assert.match(html, /id="project-introduction"[\s\S]*选择一个项目/);
  assert.match(html, /id="project-files"[\s\S]*还没有项目文件/);
});

test('project selector is populated before slower project files and routes finish loading', async () => {
  const source = await readFile(new URL('./js/projects.js', import.meta.url), 'utf8');
  const loadProjects = source.match(/async function loadProjects\([\s\S]*?\n}/)?.[0] || '';

  const renderIndex = loadProjects.indexOf('renderProjectSelector()');
  const detailsIndex = loadProjects.indexOf('await loadFiles()');
  assert.ok(renderIndex >= 0, 'loadProjects should render the selector directly');
  assert.ok(detailsIndex >= 0, 'loadProjects should continue loading project details');
  assert.ok(renderIndex < detailsIndex, 'selector must render before project details are awaited');
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


test('all project analysis views keep their header fixed and scroll only the content panel', async () => {
  const html = await readFile(new URL('./index.html', import.meta.url), 'utf8');
  const css = await readFile(new URL('./css/style.css', import.meta.url), 'utf8');

  for (const id of ['architecture', 'flow', 'sequence', 'project-api']) {
    assert.match(html, new RegExp(`id="view-${id}"[\\s\\S]*?<header class="page-header"[\\s\\S]*?class="artifact-content`));
  }
  assert.match(css, /\.artifact-view\.active\s*\{[^}]*display:\s*grid[^}]*grid-template-rows:\s*auto\s+auto\s+minmax\(0,\s*1fr\)[^}]*overflow:\s*hidden/s);
  assert.match(css, /\.artifact-view\s*>\s*\.page-header\s*\{[^}]*flex:\s*0\s+0\s+auto/s);
  assert.match(css, /\.artifact-view\s*>\s*\.artifact-content\s*\{[^}]*min-height:\s*0[^}]*overflow:\s*auto/s);
});


test('folder and file glyphs keep their original shapes with slightly stronger contrast', async () => {
  const css = await readFile(new URL('./css/style.css', import.meta.url), 'utf8');

  assert.match(css, /\.folder-glyph\s*\{[^}]*color:\s*color-mix\([^;]*72%/s);
  assert.match(css, /\.project-history-toggle \.folder-glyph::after\s*\{[^}]*opacity:\s*0/s);
  assert.match(css, /\.project-history-group:not\(\.collapsed\)[^\{]*\.folder-glyph::after\s*\{[^}]*opacity:\s*1/s);
  assert.doesNotMatch(css, /\.file-tree-folder\s*>\s*summary\s+\.folder-glyph::after/);
  assert.match(css, /\.file-glyph\s*\{[^}]*color:\s*color-mix\([^;]*68%/s);
  assert.match(css, /\.file-glyph::after\s*\{[^}]*background:\s*color-mix/s);
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


test('feature sequence follows one-scenario UML conventions without a visible evidence note', async () => {
  globalThis.localStorage ??= { getItem: () => null, setItem: () => {} };
  const artifacts = await import(`./js/artifacts.js?sequence-standard-test=${Date.now()}`);
  const content = artifacts.featureSequence({
    method: 'GET', path: '/users/{id}', handler: 'UserController.get',
    module: 'web', framework: 'Spring MVC', source_path: 'src/UserController.java', line_number: 18,
  });

  assert.match(content, /^sequenceDiagram/m);
  assert.match(content, /actor U as 外部用户/);
  assert.match(content, /participant G as 前端 \/ 网关【web】/);
  assert.match(content, /participant B as 业务服务【UserController】/);
  assert.match(content, /activate G/);
  assert.match(content, /activate B/);
  assert.match(content, /alt 正常流程/);
  assert.match(content, /else 关键异常/);
  assert.match(content, /U->>G: GET \/users\/\{id\}\(id\) : 发起请求/);
  assert.match(content, /G-->>U:/);
  assert.doesNotMatch(content, /Note over/);
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


test('project overview owns analysis selection independently from opening conversations', async () => {
  const appSource = await readFile(new URL('./js/app.js', import.meta.url), 'utf8');
  const artifactsSource = await readFile(new URL('./js/artifacts.js', import.meta.url), 'utf8');
  const chatSource = await readFile(new URL('./js/chat.js', import.meta.url), 'utf8');
  const projectsSource = await readFile(new URL('./js/projects.js', import.meta.url), 'utf8');
  const projectImport = source => source.match(/from ['"](\.\/projects\.js\?v=[^'"]+)['"]/)?.[1];

  assert.equal(projectImport(artifactsSource), projectImport(appSource));
  assert.equal(projectImport(chatSource), projectImport(appSource));
  assert.match(projectsSource, /overview-project-selector/);
  assert.doesNotMatch(chatSource, /project:context-changed/);
  assert.doesNotMatch(artifactsSource, /project:context-changed/);
});


test('daily conversations never inherit the project selected in overview', async () => {
  const chatSource = await readFile(new URL('./js/chat.js', import.meta.url), 'utf8');
  const contextFunction = chatSource.match(/function conversationContextProjectId\(\)[\s\S]*?\n}/)?.[0] || '';
  const createFunction = chatSource.match(/async function createConversation\([^\n]+\)[\s\S]*?\n}/)?.[0] || '';

  assert.match(contextFunction, /normalizeProjectId\(activeConversation\(\)\)/);
  assert.doesNotMatch(contextFunction, /activeProjectId/);
  assert.match(createFunction, /projectId\s*=\s*null/);
  assert.doesNotMatch(createFunction, /projectId\s*=\s*activeProjectId\(\)/);
});


test('project connection fields suppress hints and browser autofill', async () => {
  const appSource = await readFile(new URL('./js/app.js', import.meta.url), 'utf8');
  const projectsSource = await readFile(new URL('./js/projects.js', import.meta.url), 'utf8');

  assert.match(appSource, /input\.autocomplete\s*=\s*field\.autocomplete\s*\|\|\s*'off'/);
  assert.doesNotMatch(projectsSource, /留空时使用目录或仓库名称/);
  assert.doesNotMatch(projectsSource, /https:\/\/github\.com\/owner\/repository/);
  assert.doesNotMatch(projectsSource, /https:\/\/gitee\.com\/owner\/repository/);
});


test('project name explicitly opts out of account autofill suggestions', async () => {
  const projectsSource = await readFile(new URL('./js/projects.js', import.meta.url), 'utf8');

  assert.match(projectsSource, /\{ name: 'project_name', label: '项目名称', autocomplete: 'new-password' \}/);
  assert.match(projectsSource, /name:\s*result\.project_name/);
});


test('architecture evidence is rendered as layer and module groups', async () => {
  const artifactsSource = await readFile(new URL('./js/artifacts.js', import.meta.url), 'utf8');

  assert.match(artifactsSource, /parseEvidenceGroups/);
  assert.match(artifactsSource, /evidence-layer/);
  assert.match(artifactsSource, /evidence-module/);
});


test('api documentation source links open the selected endpoint context', async () => {
  const artifactsSource = await readFile(new URL('./js/artifacts.js', import.meta.url), 'utf8');
  const { renderMarkdown } = await import(`./js/markdown.js?source-link-test=${Date.now()}`);
  const rendered = renderMarkdown('[查看源码](source://src/main/java/demo/PersonController.java:12)');

  assert.match(rendered, /class="source-link"/);
  assert.match(rendered, /source:\/\/src\/main\/java\/demo\/PersonController\.java:12/);
  assert.match(artifactsSource, /source-link/);
  assert.match(artifactsSource, /showEvidence\([^\n]*endpoint:\s*true/);
});


test('knowledge categories are fixed choices and project files use a separate panel', async () => {
  const html = await readFile(new URL('./index.html', import.meta.url), 'utf8');
  const documentsSource = await readFile(new URL('./js/documents.js', import.meta.url), 'utf8');
  const css = await readFile(new URL('./css/style.css', import.meta.url), 'utf8');

  assert.match(documentsSource, /KNOWLEDGE_CATEGORIES/);
  for (const category of ['general', 'backend', 'frontend', 'fullstack', 'architecture', 'devops', 'testing']) {
    assert.match(documentsSource, new RegExp(`['"]${category}['"]`));
  }
  assert.match(documentsSource, /name:\s*['"]category['"][^\n]*type:\s*['"]select['"]/);
  assert.match(html, /class="[^"]*project-files-panel[^"]*"[\s\S]*?<h2>项目文件<\/h2>/);
  assert.match(css, /\.project-files-panel\s*\{/);
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


test('recent conversations render source, project, and daily collapsible groups', async () => {
  const chatSource = await readFile(new URL('./js/chat.js', import.meta.url), 'utf8');
  const css = await readFile(new URL('./css/style.css', import.meta.url), 'utf8');

  assert.match(chatSource, /groupWorkspaceConversations/);
  assert.match(chatSource, /expandedSourceTypes/);
  assert.match(chatSource, /expandedProjectIds/);
  assert.match(chatSource, /project-source-group/);
  assert.match(chatSource, /project-history-group/);
  assert.match(chatSource, /daily-history-group/);
  assert.match(chatSource, /日常对话/);
  assert.match(chatSource, /aria-expanded/);
  assert.match(chatSource, /api\.conversations\(\)/);
  assert.match(css, /\.project-source-group\.collapsed \.project-source-panel/);
  assert.match(css, /\.project-history-group\.collapsed \.project-conversation-panel/);
  assert.match(css, /\.daily-history-group\.collapsed \.daily-conversation-panel/);
});


test('workspace selection and deletion remain inside the matching conversation group', async () => {
  const chatSource = await readFile(new URL('./js/chat.js', import.meta.url), 'utf8');

  assert.match(chatSource, /preferredProjectId/);
  assert.match(chatSource, /normalizeProjectId/);
  assert.match(chatSource, /fallbackProjectId/);
  assert.doesNotMatch(chatSource, /ui\.on\('project:changed'/);
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
