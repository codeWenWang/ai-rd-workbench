import { api, errorText, listFrom } from './api.js?v=20260714.1';

let ui;
const el = id => document.getElementById(id);
const state = { projects: [], activeId: localStorage.getItem('active_project_id') || '', files: [] };

export function activeProjectId() {
  return state.activeId;
}

export function activeProject() {
  return state.projects.find(item => item.id === state.activeId) || null;
}

function renderSelector() {
  const select = el('project-selector');
  select.innerHTML = '<option value="">通用工作区</option>';
  for (const project of state.projects) {
    const option = document.createElement('option');
    option.value = project.id;
    option.textContent = project.name;
    select.append(option);
  }
  if (state.activeId && !state.projects.some(item => item.id === state.activeId)) state.activeId = '';
  select.value = state.activeId;
}

function renderOverview() {
  const project = activeProject();
  el('scan-project').disabled = !project;
  el('remove-project').disabled = !project;
  el('overview-subtitle').textContent = project
    ? `${project.root_path} · ${project.status === 'ready' ? '已扫描' : '等待扫描'}`
    : '连接本地项目后开始只读分析';
  const stats = project ? [
    ['状态', project.status === 'ready' ? '已就绪' : '等待扫描'],
    ['技术栈', (project.tech_stack || []).join('、') || '待识别'],
    ['文件', state.files.length],
    ['最近扫描', ui.formatTime(project.last_scanned_at)],
  ] : [['当前项目', '未连接'], ['源码权限', '严格只读'], ['项目数量', state.projects.length], ['GitHub', '后续扩展']];
  el('project-stats').innerHTML = stats.map(([label, value]) => `<div class="stat"><span>${ui.escape(label)}</span><strong>${ui.escape(String(value))}</strong></div>`).join('');
  el('project-files').innerHTML = state.files.length
    ? state.files.map(file => `<article class="list-item compact"><div><strong>${ui.escape(file.relative_path)}</strong><p>${ui.escape(file.language)} · ${file.size_bytes} B</p></div><span class="status-pill indexed">已解析</span></article>`).join('')
    : '<div class="empty-state"><strong>还没有项目文件</strong><span>选择项目并执行扫描。</span></div>';
}

async function loadFiles() {
  if (!state.activeId) { state.files = []; renderOverview(); return; }
  try {
    state.files = listFrom(await api.projectFiles(state.activeId));
  } catch (error) {
    state.files = [];
    ui.alert('project-alert', errorText(error));
  }
  renderOverview();
}

async function loadProjects({ emit = true } = {}) {
  const payload = await api.projects();
  state.projects = listFrom(payload);
  renderSelector();
  await loadFiles();
  if (emit) ui.emit('project:changed', { projectId: state.activeId, project: activeProject() });
}

async function addProject() {
  const result = await ui.formDialog({
    title: '连接本地项目', submitText: '连接', fields: [
      { name: 'name', label: '项目名称', placeholder: '默认使用文件夹名称' },
      { name: 'root_path', label: '项目绝对路径', placeholder: '例如 E:\\projects\\demo', required: true },
    ],
  });
  if (!result) return;
  try {
    const project = await api.createProject(result);
    state.activeId = project.id;
    localStorage.setItem('active_project_id', state.activeId);
    await loadProjects();
    ui.showView('overview');
  } catch (error) {
    ui.alert('project-alert', errorText(error));
  }
}

async function scanProject() {
  if (!state.activeId) return;
  const button = el('scan-project');
  ui.busy(button, true);
  try {
    const summary = await api.scanProject(state.activeId);
    await loadProjects({ emit: false });
    ui.emit('project:scanned', { projectId: state.activeId, summary });
    const warning = summary.warnings?.length ? '，语义索引暂时不可用，仍可使用本地检索' : '';
    ui.alert('project-alert', `扫描完成：${summary.file_count} 个文件，${summary.route_count} 个接口${warning}`, 'success');
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
  el('project-selector').addEventListener('change', async event => {
    state.activeId = event.target.value;
    if (state.activeId) localStorage.setItem('active_project_id', state.activeId);
    else localStorage.removeItem('active_project_id');
    await loadFiles();
    ui.emit('project:changed', { projectId: state.activeId, project: activeProject() });
  });
  await loadProjects();
}
