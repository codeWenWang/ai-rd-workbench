import { api, errorText, listFrom } from './api.js?v=20260721.7';

let ui;
const el = id => document.getElementById(id);
const state = { projects: [], activeId: localStorage.getItem('active_project_id') || '', files: [], routes: [] };

export function activeProjectId() {
  return state.activeId;
}

export function activeProject() {
  return state.projects.find(item => item.id === state.activeId) || null;
}

export function projectById(projectId) {
  return state.projects.find(item => item.id === projectId) || null;
}

export function allProjects() {
  return [...state.projects];
}

export function projectFileMetadata(path) {
  const normalized = String(path || '').replace(/:\d+$/, '').replaceAll('\\', '/');
  return state.files.find(file => String(file.relative_path || '').replaceAll('\\', '/') === normalized) || null;
}

const STACK_LABELS = new Map([
  ['java', 'Java'], ['python', 'Python'], ['javascript', 'JavaScript'], ['typescript', 'TypeScript'],
  ['html', 'HTML'], ['css', 'CSS'], ['vue', 'Vue'], ['react', 'React'], ['spring', 'Spring'],
  ['spring boot', 'Spring Boot'], ['springboot', 'Spring Boot'], ['fastapi', 'FastAPI'],
  ['langchain', 'LangChain'], ['langgraph', 'LangGraph'], ['node.js', 'Node.js'],
]);

const STACK_PRIORITY = new Map([
  ['Java', 10], ['Kotlin', 11], ['Go', 12], ['C#', 13], ['Python', 20],
  ['Spring Boot', 30], ['Spring', 31], ['FastAPI', 32], ['Node.js', 33],
  ['LangChain', 34], ['LangGraph', 35],
  ['HTML', 100], ['CSS', 101], ['JavaScript', 102], ['TypeScript', 103],
  ['Vue', 110], ['React', 111],
]);

export function primaryTechStack(values = []) {
  const result = [];
  for (const raw of values) {
    const normalized = String(raw || '').trim().toLowerCase();
    const label = STACK_LABELS.get(normalized);
    if (label && !result.includes(label)) result.push(label);
  }
  return result.sort((left, right) => (STACK_PRIORITY.get(left) ?? 900) - (STACK_PRIORITY.get(right) ?? 900));
}

function firstMatchingPath(files, patterns, used) {
  const item = files.find(file => {
    const path = String(file.relative_path || '');
    return !used.has(path) && patterns.some(pattern => pattern.test(path));
  });
  if (!item) return '';
  used.add(item.relative_path);
  return item.relative_path;
}

export function buildProjectGuide(project, files = [], routes = []) {
  const stack = primaryTechStack(project?.tech_stack || []);
  const stackText = stack.join('、') || '尚待识别的技术栈';
  const routeResources = [...new Set(routes.flatMap(route => String(route.path || '').split('/'))
    .filter(part => part && !/^\{.*\}$/.test(part) && !/^\d+$/.test(part) && !/^(api|v\d+|internal)$/i.test(part)))]
    .slice(0, 5);
  const resourceText = routeResources.join('、');
  const projectText = `${project?.name || ''} ${project?.source_uri || ''} ${files.map(file => file.relative_path || '').join(' ')} ${routes.map(route => route.path || '').join(' ')}`.toLowerCase();
  const businessFunctions = inferBusinessFunctions(projectText, resourceText, routes, files);
  const summary = `${project?.name || '当前项目'} 是一个以 ${stackText} 构建的源码项目。平台已扫描 ${files.length} 个文件${routes.length ? `并识别 ${routes.length} 个接口` : ''}。${businessFunctions[0].intro}`;

  const capabilities = [];
  if (routes.length) capabilities.push(`提供 ${routes.length} 个接口，覆盖 ${resourceText || '项目核心业务'} 的查询和操作流程。`);
  if (files.some(file => /\.(html|vue|jsx|tsx|css)$/i.test(file.relative_path || ''))) capabilities.push('包含用户界面或前端资源，可从页面入口追踪到对应的接口调用。');
  if (files.some(file => /(controller|router|service)/i.test(file.relative_path || ''))) capabilities.push('包含清晰的接口入口和业务处理层，可用于理解一次请求如何进入核心逻辑。');
  if (files.some(file => /(repository|dao|mapper|database|storage)/i.test(file.relative_path || ''))) capabilities.push('包含数据访问或存储模块，可继续追踪业务数据如何读取、修改和持久化。');
  if (!capabilities.length) capabilities.push('当前可以浏览主要目录、技术栈和源码文件；重新扫描后会补充更多可验证能力。');

  const used = new Set();
  const candidates = [
    ['先看项目说明，了解用途、启动方式和目录约定', [/(^|\/)readme(?:\.[^/]+)?$/i]],
    ['找到应用入口，确认程序如何启动和装配模块', [/(Application\.java$|(^|\/)(main|app)\.(py|js|ts)$|(^|\/)index\.(js|ts|html)$|package\.json$)/i]],
    ['阅读控制器或路由，建立功能与接口的对应关系', [/(controller|router|routes?)[^/]*\.(java|py|js|ts)$/i]],
    ['进入业务服务层，理解核心规则和调用顺序', [/(service|usecase|application)[^/]*\.(java|py|js|ts)$/i]],
    ['最后查看数据访问层，确认数据来源和持久化方式', [/(repository|dao|mapper|storage)[^/]*\.(java|py|js|ts)$/i]],
  ];
  const readingSteps = candidates.map(([label, patterns]) => ({ label, path: firstMatchingPath(files, patterns, used) }))
    .filter(item => item.path);
  if (!readingSteps.length && files.length) readingSteps.push({ label: '从项目根目录的第一个源码文件开始浏览', path: files[0].relative_path });
  return { summary, capabilities, businessFunctions, readingSteps };
}

function inferBusinessFunctions(projectText, resourceText, routes, files) {
  const has = pattern => pattern.test(projectText);
  if (has(/book|library|borrow|图书|图书馆|借阅|归还/)) {
    return [
      { role: '用户端', description: '用户可以查找图书、查看详情、提交借阅和归还操作，并查看自己的借阅记录与逾期信息。', intro: '它面向图书借阅场景，把查书、借阅、归还和借阅记录集中到一个系统中。' },
      { role: '管理端', description: '管理员统一维护图书、分类和用户，处理借阅订单、归还状态以及逾期记录。', intro: '' },
      { role: '运维端', description: '系统记录关键操作日志，统计馆藏、借阅和逾期数据，帮助管理人员进行日常复盘。', intro: '' },
    ];
  }
  if (has(/kkrepo|repository|artifact|blob-store|blobstores|制品|仓库|nexus|maven|npm/)) {
    return [
      { role: '使用端', description: '开发者可以浏览和搜索制品仓库，查看版本与元数据，并通过接口上传、下载或校验对象。', intro: '它是一个面向团队的制品仓库服务，用来统一保存、查询和分发构建产物。' },
      { role: '管理端', description: '管理员可以管理仓库格式、Blob 存储、访问策略和兼容性配置，控制不同仓库的使用边界。', intro: '' },
      { role: '运维端', description: '系统提供存储连通性检查、健康状态、对象统计和迁移信息，便于定位存储或部署问题。', intro: '' },
    ];
  }
  if (has(/order|product|cart|payment|商品|订单|购物车|支付/)) {
    return [
      { role: '用户端', description: '用户可以浏览商品、加入购物车、提交订单并查询订单状态。', intro: '它围绕商品交易流程组织页面、接口和数据模块。' },
      { role: '管理端', description: '管理员可以维护商品与分类，处理订单、库存和售后状态。', intro: '' },
      { role: '运维端', description: '系统记录操作日志并汇总交易、库存和异常数据，支持运营分析。', intro: '' },
    ];
  }
  const routeHint = resourceText || '核心业务';
  const hasUi = files.some(file => /\.(html|vue|jsx|tsx|css)$/i.test(file.relative_path || ''));
  const hasData = files.some(file => /(repository|dao|mapper|database|storage)/i.test(file.relative_path || ''));
  return [
    { role: hasUi ? '使用端' : '调用端', description: `通过${hasUi ? '页面和' : ''}接口访问 ${routeHint}，完成项目提供的主要查询与操作。`, intro: `它围绕 ${routeHint} 等核心功能组织入口、业务处理和数据访问模块。` },
    { role: '业务端', description: '业务服务负责校验请求、编排核心规则，并把一次调用拆分为可追踪的处理步骤。', intro: '' },
    { role: hasData ? '运维端' : '维护端', description: `${hasData ? '数据访问和存储模块负责持久化业务数据。' : '项目可从入口文件、模块依赖和接口定义逐步阅读。'}重新扫描后可继续补充可验证的功能证据。`, intro: '' },
  ];
}

function sortTreeNodes(nodes) {
  nodes.sort((left, right) => {
    if (left.type !== right.type) return left.type === 'folder' ? -1 : 1;
    return left.name.localeCompare(right.name, 'zh-CN', { numeric: true });
  });
  nodes.forEach(node => {
    if (node.type === 'folder') sortTreeNodes(node.children);
  });
  return nodes;
}

export function buildProjectFileTree(files = []) {
  const root = { children: [], folders: new Map() };
  for (const file of files) {
    const relativePath = String(file.relative_path || '').replaceAll('\\', '/').replace(/^\/+|\/+$/g, '');
    if (!relativePath) continue;
    const parts = relativePath.split('/');
    let current = root;
    parts.forEach((part, index) => {
      const isFile = index === parts.length - 1;
      if (isFile) {
        current.children.push({
          name: part,
          path: relativePath,
          type: 'file',
          language: file.language || 'text',
          sizeBytes: Number(file.size_bytes || 0),
        });
        return;
      }
      if (!current.folders.has(part)) {
        const folder = { name: part, type: 'folder', children: [], folders: new Map() };
        current.folders.set(part, folder);
        current.children.push(folder);
      }
      current = current.folders.get(part);
    });
  }
  const stripMaps = nodes => nodes.map(node => (
    node.type === 'folder'
      ? { name: node.name, type: 'folder', children: stripMaps(node.children) }
      : node
  ));
  return stripMaps(sortTreeNodes(root.children));
}

function descendantCount(node) {
  if (node.type === 'file') return 1;
  return node.children.reduce((count, child) => count + descendantCount(child), 0);
}

function renderTreeNodes(nodes, depth = 0) {
  return nodes.map(node => {
    if (node.type === 'folder') {
      return `<details class="file-tree-folder"${depth === 0 && nodes.length === 1 ? ' open' : ''}>
        <summary><span class="folder-glyph" aria-hidden="true"></span><strong>${ui.escape(node.name)}</strong><span class="tree-chevron" aria-hidden="true">›</span><small>${descendantCount(node)} 个文件</small></summary>
        <div class="file-tree-children">${renderTreeNodes(node.children, depth + 1)}</div>
      </details>`;
    }
    return `<div class="file-tree-file" title="${ui.escape(node.path)}"><span class="file-glyph" aria-hidden="true"></span><strong>${ui.escape(node.name)}</strong><small>${ui.escape(node.language)} · ${node.sizeBytes} B</small></div>`;
  }).join('');
}

function renderProjectSelector() {
  const selector = el('overview-project-selector');
  const options = ['<option value="">选择已添加的项目</option>'];
  for (const project of state.projects) {
    options.push(`<option value="${ui.escape(project.id)}">${ui.escape(project.name)}</option>`);
  }
  selector.innerHTML = options.join('');
  selector.value = state.activeId;
}

function projectIntroduction(project) {
  if (!project) return '<div class="empty-state"><strong>从一个项目开始</strong><span>添加本地目录、GitHub 或 Gitee 仓库，扫描后即可查看项目结构。</span></div>';
  const guide = buildProjectGuide(project, state.files, state.routes);
  return `<span class="section-kicker guide-heading">项目导读</span>
    <div class="guide-summary"><h2>这个项目能做什么</h2><p>${ui.escape(guide.summary)}</p></div>
    <div class="guide-business"><h3>业务能力</h3>${guide.businessFunctions.map(item => `<section><strong>${ui.escape(item.role)}</strong><p>${ui.escape(item.description)}</p></section>`).join('')}</div>
    <div class="guide-details">
      <section><h3>主要能力</h3><ul>${guide.capabilities.map(item => `<li>${ui.escape(item)}</li>`).join('')}</ul></section>
      <section><h3>源码阅读路线</h3><ol>${guide.readingSteps.map(item => `<li><span>${ui.escape(item.label)}</span><code>${ui.escape(item.path)}</code></li>`).join('')}</ol></section>
    </div>`;
}

function renderOverview() {
  const project = activeProject();
  const sourceLabel = { github: 'GitHub', gitee: 'Gitee' }[project?.source_type] || '本地目录';
  const sourceLocation = project?.source_uri || project?.root_path;
  el('scan-project').disabled = !project;
  el('remove-project').disabled = !project;
  el('overview-title').textContent = project?.name || '项目总览';
  el('overview-subtitle').textContent = project
    ? `${sourceLabel} · ${sourceLocation} · ${project.status === 'ready' ? '已扫描' : '等待扫描'}`
    : '连接本地目录或公开 Git 仓库后开始只读分析';
  renderProjectSelector();
  const stack = primaryTechStack(project?.tech_stack || []);
  const stats = project ? [
    ['状态', project.status === 'ready' ? '已就绪' : '等待扫描'],
    ['技术栈', stack.join('、') || '待识别'],
    ['文件', state.files.length],
    ['最近扫描', ui.formatTime(project.last_scanned_at)],
  ] : [['当前项目', '未连接'], ['源码权限', '严格只读'], ['项目数量', state.projects.length], ['远程仓库', 'GitHub / Gitee']];
  el('project-stats').innerHTML = stats.map(([label, value]) => `<div class="stat"><span>${ui.escape(label)}</span><strong>${ui.escape(String(value))}</strong></div>`).join('');
  el('project-introduction').innerHTML = projectIntroduction(project);
  document.querySelectorAll('.analysis-entry').forEach(button => { button.disabled = !project; });
  el('project-files').innerHTML = state.files.length
    ? renderTreeNodes(buildProjectFileTree(state.files))
    : '<div class="empty-state"><strong>还没有项目文件</strong><span>选择项目并执行扫描。</span></div>';
}

async function loadFiles() {
  if (!state.activeId) { state.files = []; state.routes = []; renderOverview(); return; }
  const [filesResult, routesResult] = await Promise.allSettled([
    api.projectFiles(state.activeId), api.projectRoutes(state.activeId),
  ]);
  state.files = filesResult.status === 'fulfilled' ? listFrom(filesResult.value) : [];
  state.routes = routesResult.status === 'fulfilled' ? listFrom(routesResult.value) : [];
  if (filesResult.status === 'rejected') ui.alert('project-alert', errorText(filesResult.reason));
  renderOverview();
}

async function loadProjects({ emit = true } = {}) {
  const payload = await api.projects();
  state.projects = listFrom(payload);
  if (state.activeId && !state.projects.some(item => item.id === state.activeId)) {
    state.activeId = '';
    localStorage.removeItem('active_project_id');
  }
  renderProjectSelector();
  await loadFiles();
  ui.emit('projects:changed', { projects: allProjects() });
  if (emit) ui.emit('project:changed', { projectId: state.activeId, project: activeProject() });
}

export async function addProject() {
  const result = await ui.formDialog({
    title: '连接项目', submitText: '连接', fields: [
      { name: 'source_type', label: '项目来源', type: 'select', value: 'local', options: [
        ['local', '本地目录'], ['github', 'GitHub'], ['gitee', 'Gitee'],
      ] },
      { name: 'project_name', label: '项目名称', autocomplete: 'new-password' },
      { name: 'root_path', label: '本地项目文件夹', type: 'directory', placeholder: '选择本机中的项目文件夹', requiredWhen: { source_type: 'local' } },
      { name: 'github_url', label: 'GitHub 仓库地址', requiredWhen: { source_type: 'github' } },
      { name: 'gitee_url', label: 'Gitee 仓库地址', requiredWhen: { source_type: 'gitee' } },
    ],
  });
  if (!result) return;
  ui.showView('overview');
  const remote = result.source_type !== 'local';
  ui.alert(
    'project-alert',
    remote ? '正在连接远程仓库并准备源码，请稍候…' : '正在连接本地项目…',
    'progress',
  );
  try {
    const payload = { name: result.project_name, source_type: result.source_type };
    if (result.source_type === 'local') payload.root_path = result.root_path;
    else payload.repository_url = result.github_url || result.gitee_url;
    const project = await api.createProject(payload);
    state.activeId = project.id;
    localStorage.setItem('active_project_id', state.activeId);
    await loadProjects();
    ui.alert('project-alert', '项目连接成功，可以开始扫描。', 'success');
  } catch (error) {
    ui.alert('project-alert', errorText(error));
  }
}

export async function selectProject(projectId, { emit = true } = {}) {
  const normalized = String(projectId || '');
  state.activeId = state.projects.some(project => String(project.id) === normalized) ? normalized : '';
  if (state.activeId) localStorage.setItem('active_project_id', state.activeId);
  else localStorage.removeItem('active_project_id');
  await loadFiles();
  if (emit) ui.emit('project:changed', { projectId: state.activeId, project: activeProject() });
}

async function scanProject() {
  if (!state.activeId) return;
  const button = el('scan-project');
  ui.busy(button, true);
  ui.alert('project-alert', '正在扫描项目，请稍候…', 'progress');
  try {
    const summary = await api.scanProject(state.activeId);
    await loadProjects({ emit: false });
    ui.emit('project:scanned', { projectId: state.activeId, summary });
    const warnings = summary.warnings || [];
    const messages = [];
    if (warnings.includes('remote_update_unavailable')) messages.push('远程更新失败，已使用本地缓存');
    if (warnings.includes('project_semantic_index_unavailable')) messages.push('语义索引暂时不可用');
    const warning = messages.length ? `，${messages.join('；')}` : '';
    const completedAt = new Date().toLocaleTimeString('zh-CN', { hour12: false });
    ui.alert('project-alert', `本次扫描完成（${completedAt}）：${summary.file_count} 个文件，${summary.route_count} 个接口${warning}`, 'success');
  } catch (error) {
    ui.alert('project-alert', errorText(error));
  } finally {
    ui.busy(button, false);
  }
}

async function removeProject() {
  const project = activeProject();
  if (!project) return;
  if (!await ui.confirmDialog('移除项目', `确定移除“${project.name}”吗？源码文件不会被修改。`, '移除')) return;
  try {
    await api.deleteProject(project.id);
    state.activeId = '';
    state.files = [];
    state.routes = [];
    localStorage.removeItem('active_project_id');
    await loadProjects();
    ui.showView('overview');
  } catch (error) {
    ui.alert('project-alert', errorText(error));
  }
}

export async function initProjects(sharedUi) {
  ui = sharedUi;
  el('add-project').addEventListener('click', addProject);
  el('scan-project').addEventListener('click', scanProject);
  el('remove-project').addEventListener('click', removeProject);
  el('overview-project-selector').addEventListener('change', event => selectProject(event.target.value));
  await loadProjects();
}
