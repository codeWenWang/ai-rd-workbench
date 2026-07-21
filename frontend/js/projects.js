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

export function primaryTechStack(values = []) {
  const result = [];
  for (const raw of values) {
    const normalized = String(raw || '').trim().toLowerCase();
    const label = STACK_LABELS.get(normalized);
    if (label && !result.includes(label)) result.push(label);
  }
  return result;
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
  const summary = `${project?.name || '当前项目'} 是一个以 ${stackText} 构建的源码项目。平台已扫描 ${files.length} 个文件${routes.length ? `并识别 ${routes.length} 个接口` : ''}。${resourceText ? `从接口和目录结构看，项目主要围绕 ${resourceText} 等功能展开。` : '可以通过目录结构、入口文件和模块依赖快速了解它的职责。'}`;

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
  return { summary, capabilities, readingSteps };
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
  return `<div class="guide-summary"><span class="section-kicker">项目导读</span><h2>这个项目能做什么</h2><p>${ui.escape(guide.summary)}</p></div>
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
      { name: 'name', label: '项目名称' },
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
    const payload = { name: result.name, source_type: result.source_type };
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
