import { api, errorText, listFrom } from './api.js?v=20260723.4';
import { activeProjectId, allProjects, projectById } from './projects.js?v=20260723.2';

const el = id => document.getElementById(id);
const state = { tasks: [], activeId: '', filterProjectId: '' };
let ui;
let promptTaskId = '';

const statusLabels = {
  planned: '待开始',
  in_progress: '进行中',
  needs_review: '待复审',
  completed: '已完成',
};

function activeTask() {
  return state.tasks.find(task => task.id === state.activeId) || null;
}

function taskProject(task) {
  return projectById(task?.project_id) || { name: '已移除项目' };
}

function setTaskAlert(message = '', type = 'error') {
  const target = el('task-alert');
  target.textContent = message;
  target.className = `inline-alert ${type}${message ? '' : ' hidden'}`;
}

function syncTaskCount() {
  const count = state.tasks.filter(task => task.status !== 'completed').length;
  const badge = el('task-count');
  badge.textContent = String(count);
  badge.classList.toggle('hidden', count === 0);
}

function visibleTasks() {
  return state.filterProjectId
    ? state.tasks.filter(task => task.project_id === state.filterProjectId)
    : state.tasks;
}

function progress(task) {
  const steps = task.plan?.steps || [];
  const completed = new Set(task.completed_step_ids || []);
  const done = steps.filter(step => completed.has(step.id)).length;
  return { done, total: steps.length, percent: steps.length ? Math.round(done / steps.length * 100) : 0 };
}

function renderProjectFilter() {
  const select = el('task-project-filter');
  const value = state.filterProjectId;
  select.innerHTML = '<option value="">全部项目</option>';
  for (const project of allProjects()) {
    const option = document.createElement('option');
    option.value = project.id;
    option.textContent = project.name;
    select.append(option);
  }
  select.value = allProjects().some(project => project.id === value) ? value : '';
  state.filterProjectId = select.value;
}

function renderTaskList() {
  const container = el('task-list');
  const tasks = visibleTasks();
  if (!tasks.length) {
    container.innerHTML = '<div class="empty-state compact"><strong>还没有研发任务</strong><span>创建任务后，持续记录实施进度。</span></div>';
    return;
  }
  container.innerHTML = '';
  for (const task of tasks) {
    const item = document.createElement('button');
    item.type = 'button';
    item.className = `task-list-item${task.id === state.activeId ? ' active' : ''}`;
    const taskProgress = progress(task);
    item.innerHTML = `
      <span class="task-list-top"><strong>${ui.escape(task.title)}</strong><span class="task-status ${ui.escape(task.status)}">${statusLabels[task.status] || task.status}</span></span>
      <small>${ui.escape(taskProject(task).name)}</small>
      <span class="task-list-progress"><i style="width:${taskProgress.percent}%"></i></span>
      <small>${taskProgress.done}/${taskProgress.total} 个步骤</small>`;
    item.addEventListener('click', () => {
      state.activeId = task.id;
      renderTaskList();
      renderTaskDetail();
    });
    container.append(item);
  }
}

function renderSteps(task) {
  const completed = new Set(task.completed_step_ids || []);
  return (task.plan?.steps || []).map((step, index) => `
    <label class="task-step${completed.has(step.id) ? ' completed' : ''}">
      <input type="checkbox" data-step-id="${ui.escape(step.id)}" ${completed.has(step.id) ? 'checked' : ''}>
      <span><strong>${index + 1}. ${ui.escape(step.title)}</strong><small>${ui.escape(step.description || '')}</small>${step.affected_files?.length ? `<code>${step.affected_files.map(ui.escape).join(' · ')}</code>` : ''}</span>
    </label>`).join('');
}

function renderAffectedFiles(task) {
  const files = task.plan?.affected_files || [];
  if (!files.length) return '<p class="task-muted">计划未锁定具体文件，请在实施前结合源码进一步确认。</p>';
  return `<div class="task-file-list">${files.map(file => `
    <div><code>${ui.escape(file.path)}</code><span>${ui.escape(file.reason || '')}</span></div>`).join('')}</div>`;
}

function renderReview(task) {
  const review = task.review || {};
  if (!review.summary) {
    return '<p class="task-muted">修改项目并重新扫描后，点击“审查当前修改”。系统将按照验收标准检查当前源码。</p>';
  }
  const changes = review.changed_files || {};
  const changeRows = ['added', 'modified', 'deleted'].map(kind => {
    const labels = { added: '新增', modified: '修改', deleted: '删除' };
    const paths = changes[kind] || [];
    return `<div><strong>${labels[kind]}</strong><span>${paths.length ? paths.map(ui.escape).join('、') : '无'}</span></div>`;
  }).join('');
  const criteria = (review.criteria || []).map(item => `
    <li class="criterion-${ui.escape(item.status)}"><span class="criterion-status">${item.status === 'passed' ? '通过' : item.status === 'failed' ? '未通过' : '待确认'}</span><div><strong>${ui.escape(item.criterion)}</strong><small>${ui.escape(item.evidence || '')}</small></div></li>`).join('');
  const findings = (review.findings || []).map(item => `
    <li><span class="finding-severity ${ui.escape(item.severity)}">${item.severity === 'high' ? '高' : item.severity === 'low' ? '低' : '中'}</span><div><strong>${ui.escape(item.title)}</strong><p>${ui.escape(item.detail || '')}</p>${item.path ? `<code>${ui.escape(item.path)}${item.line ? `:${item.line}` : ''}</code>` : ''}</div></li>`).join('');
  return `
    <div class="review-block review-conclusion"><p>${ui.escape(review.summary)}</p></div>
    <div class="review-block"><h4>变更摘要</h4><div class="task-change-summary">${changeRows}</div></div>
    <div class="review-block"><h4>验收结果</h4><ul class="task-criteria review-criteria">${criteria || '<li><span class="task-muted">没有返回验收结果</span></li>'}</ul></div>
    <div class="review-block"><h4>审查发现</h4><ul class="task-findings">${findings || '<li class="task-muted">没有发现需要单独记录的问题。</li>'}</ul></div>
    ${(review.next_actions || []).length ? `<div class="review-block"><h4>下一步</h4><ol class="task-next-actions">${review.next_actions.map(item => `<li>${ui.escape(item)}</li>`).join('')}</ol></div>` : ''}`;
}

function normalizeInlineCode(value) {
  return String(value || '').replace(
    /(?<![`\w])((?:[\w.-]+\/)+[\w.$-]+(?:\.[A-Za-z0-9]+)?)(?![`\w])/g,
    '`$1`',
  );
}

function normalizeAgentPrompt(value) {
  const source = String(value || '').replace(/\r\n/g, '\n').trim();
  if (!source) return '';
  if (source.includes('## 任务目标') && source.includes('## 实施步骤')) {
    return normalizeInlineCode(source);
  }
  const markers = [...source.matchAll(/(?<![\w])(\d+)[.)]\s+/g)].map(match => ({
    number: match[1],
    numberStart: match.index,
    contentStart: match.index + match[0].length,
  }));
  if (markers.length < 1) return normalizeInlineCode(source);
  const intro = source.slice(0, markers[0].numberStart)
    .replace(/^##[^\n]*$/gm, '')
    .replace(/[：:]\s*$/, '')
    .trim();
  const lines = [intro || '请按以下要求修改代码。', '', '## 修改要求'];
  markers.forEach((marker, index) => {
    const end = markers[index + 1]?.numberStart ?? source.length;
    const content = source.slice(marker.contentStart, end)
      .replace(/^##[^\n]*$/gm, '')
      .split(/\n##\s+/)[0]
      .replace(/[；。]\s*$/, '')
      .trim();
    if (content) lines.push(`${marker.number}. ${content}`);
  });
  lines.push(
    '',
    '## 交付要求',
    '- 保持现有架构和编码风格。',
    '- 只修改完成任务所需的文件。',
    '- 完成后说明改动文件、验证结果和剩余风险。',
  );
  return normalizeInlineCode(lines.join('\n'));
}

function renderTaskDetail() {
  const container = el('task-detail');
  const task = activeTask();
  if (!task) {
    container.innerHTML = '<div class="empty-state"><strong>选择一项研发任务</strong><span>查看步骤、提示词和审查结果。</span></div>';
    return;
  }
  const taskProgress = progress(task);
  container.innerHTML = `
    <header class="task-detail-header">
      <div><span>${ui.escape(taskProject(task).name)}</span><h2>${ui.escape(task.title)}</h2><p>${ui.escape(task.goal)}</p></div>
      <span class="task-status ${ui.escape(task.status)}">${statusLabels[task.status] || task.status}</span>
    </header>
    <div class="task-actions">
      <button id="review-task" class="button primary" type="button">审查当前修改</button>
      <button id="view-agent-prompt" class="button" type="button">查看 Agent 提示词</button>
      <button id="delete-task" class="button danger" type="button">删除任务</button>
    </div>
    <section class="task-progress-section">
      <div><strong>实施进度</strong><span>${taskProgress.done}/${taskProgress.total}</span></div>
      <div class="task-progress-track"><i style="width:${taskProgress.percent}%"></i></div>
    </section>
    <section class="task-card"><h3>方案概述</h3><p>${ui.escape(task.plan?.summary || '暂无方案概述')}</p></section>
    <section class="task-card"><h3>实施步骤</h3><div class="task-steps">${renderSteps(task)}</div></section>
    <section class="task-card"><h3>影响文件</h3>${renderAffectedFiles(task)}</section>
    <section class="task-card"><h3>风险</h3><ul>${(task.plan?.risks || []).map(item => `<li>${ui.escape(item)}</li>`).join('') || '<li class="task-muted">暂无明确风险</li>'}</ul></section>
    <section class="task-card"><h3>验收标准</h3><ul class="task-criteria">${(task.acceptance_criteria || []).map(item => `<li>${ui.escape(item)}</li>`).join('')}</ul></section>
    <section id="agent-prompt-section" class="task-card"><div class="task-section-heading"><h3>Agent 提示词</h3><span>可查看、编辑并复制</span></div><div class="prompt-preview">${ui.escape(normalizeAgentPrompt(task.agent_prompt).split('\n').slice(0, 6).join('\n'))}${normalizeAgentPrompt(task.agent_prompt).split('\n').length > 6 ? '\n…' : ''}</div><button id="view-agent-prompt-inline" class="button" type="button">查看 Agent 提示词</button></section>
    <section class="task-card"><div class="task-section-heading"><h3>最近审查</h3><span>自动快速同步源码；不会执行项目测试</span></div>${renderReview(task)}</section>`;

  container.querySelectorAll('[data-step-id]').forEach(input => input.addEventListener('change', updateSteps));
  el('review-task').addEventListener('click', () => reviewTask(task));
  el('view-agent-prompt').addEventListener('click', () => openAgentPrompt(task));
  el('view-agent-prompt-inline').addEventListener('click', () => openAgentPrompt(task));
  el('delete-task').addEventListener('click', () => deleteTask(task));
}

async function updateSteps() {
  const task = activeTask();
  if (!task) return;
  const completed = [...el('task-detail').querySelectorAll('[data-step-id]:checked')]
    .map(input => input.dataset.stepId);
  try {
    const updated = await api.updateImprovementTask(task.id, { completed_step_ids: completed });
    replaceTask(updated);
  } catch (error) {
    setTaskAlert(errorText(error));
    renderTaskDetail();
  }
}

function replaceTask(task) {
  const index = state.tasks.findIndex(item => item.id === task.id);
  if (index >= 0) state.tasks[index] = task; else state.tasks.unshift(task);
  state.activeId = task.id;
  renderTaskList();
  renderTaskDetail();
  syncTaskCount();
}

export async function createTask() {
  const projects = allProjects();
  if (!projects.length) {
    ui.showView('overview');
    ui.alert('project-alert', '请先连接并扫描一个项目。', 'error');
    return null;
  }
  const selectedProjectId = activeProjectId() || projects[0].id;
  const result = await ui.formDialog({
    title: '制定改进计划', submitText: '生成计划', fields: [
      { name: 'project_id', label: '项目', type: 'select', value: selectedProjectId, options: projects.map(project => [project.id, project.name]) },
      { name: 'title', label: '任务名称（可选）', maxlength: 100, placeholder: '由模型根据目标生成' },
      { name: 'goal', label: '需要实现或优化什么', type: 'textarea', required: true, maxlength: 4000, placeholder: '例如：增加批量完成研发任务的接口，并补充必要测试' },
    ],
  });
  if (!result) return null;
  ui.showView('tasks');
  setTaskAlert('正在分析项目并制定改进计划，请稍候…', 'progress');
  try {
    const task = await api.createImprovementTask({
      project_id: result.project_id,
      title: result.title,
      goal: result.goal,
      model_id: el('chat-model')?.value || null,
    });
    state.filterProjectId = result.project_id;
    renderProjectFilter();
    replaceTask(task);
    setTaskAlert('改进计划已生成，可以按步骤实施。', 'success');
    return task;
  } catch (error) {
    setTaskAlert(errorText(error));
    return null;
  }
}

async function reviewTask(task) {
  const button = el('review-task');
  ui.busy(button, true);
  setTaskAlert('正在快速同步源码并进行静态审查…', 'progress');
  try {
    const updated = await api.reviewImprovementTask(task.id, {
      model_id: el('chat-model')?.value || null,
    });
    replaceTask(updated);
    setTaskAlert(updated.status === 'completed' ? '验收标准已通过，任务已完成。' : '审查完成，请处理待确认项。', updated.status === 'completed' ? 'success' : 'progress');
  } catch (error) {
    setTaskAlert(errorText(error));
  } finally {
    ui.busy(el('review-task'), false);
  }
}

function openAgentPrompt(task) {
  const dialog = el('agent-prompt-dialog');
  promptTaskId = task.id;
  const prompt = normalizeAgentPrompt(task.agent_prompt);
  el('agent-prompt-editor').value = prompt;
  el('agent-prompt-preview').innerHTML = ui.renderMarkdown(prompt);
  togglePromptEditing(false);
  el('agent-prompt-alert').classList.add('hidden');
  dialog.showModal();
}

function togglePromptEditing(editing) {
  el('agent-prompt-preview').classList.toggle('hidden', editing);
  el('agent-prompt-editor').classList.toggle('hidden', !editing);
  el('edit-agent-prompt').classList.toggle('hidden', editing);
  el('save-agent-prompt').classList.toggle('hidden', !editing);
  if (editing) requestAnimationFrame(() => el('agent-prompt-editor').focus());
}

async function copyEditedAgentPrompt() {
  try {
    await navigator.clipboard.writeText(el('agent-prompt-editor').value);
    el('agent-prompt-alert').textContent = '提示词已复制。';
    el('agent-prompt-alert').className = 'inline-alert success';
  } catch {
    el('agent-prompt-alert').textContent = '浏览器未允许复制，请手动选择文本。';
    el('agent-prompt-alert').className = 'inline-alert error';
  }
}

async function saveEditedAgentPrompt(event) {
  if (event.submitter?.value === 'cancel') return;
  event.preventDefault();
  const task = activeTask();
  if (!task || task.id !== promptTaskId) return;
  const button = el('save-agent-prompt');
  ui.busy(button, true);
  try {
    const updated = await api.updateImprovementTask(task.id, {
      agent_prompt: el('agent-prompt-editor').value,
    });
    replaceTask(updated);
    el('agent-prompt-dialog').close('default');
    setTaskAlert('Agent 提示词已保存。', 'success');
  } catch (error) {
    el('agent-prompt-alert').textContent = errorText(error);
    el('agent-prompt-alert').className = 'inline-alert error';
  } finally {
    ui.busy(button, false);
  }
}

async function deleteTask(task) {
  if (!await ui.confirmDialog('删除研发任务', `确定删除“${task.title}”吗？`, '删除')) return;
  try {
    await api.deleteImprovementTask(task.id);
    state.tasks = state.tasks.filter(item => item.id !== task.id);
    state.activeId = visibleTasks()[0]?.id || '';
    renderTaskList();
    renderTaskDetail();
    syncTaskCount();
    setTaskAlert('研发任务已删除。', 'success');
  } catch (error) {
    setTaskAlert(errorText(error));
  }
}

async function loadTasks({ preserveSelection = true } = {}) {
  try {
    const payload = await api.improvementTasks();
    state.tasks = listFrom(payload);
    if (!preserveSelection || !state.tasks.some(task => task.id === state.activeId)) {
      state.activeId = visibleTasks()[0]?.id || '';
    }
    renderProjectFilter();
    renderTaskList();
    renderTaskDetail();
    syncTaskCount();
  } catch (error) {
    setTaskAlert(errorText(error));
  }
}

async function openCurrentProjectTask({ focusPrompt = false, review = false } = {}) {
  const projectId = activeProjectId();
  const task = state.tasks.find(item => !projectId || item.project_id === projectId);
  if (!task) {
    await createTask();
    return;
  }
  state.activeId = task.id;
  state.filterProjectId = projectId || '';
  renderProjectFilter();
  renderTaskList();
  renderTaskDetail();
  ui.showView('tasks');
  if (review) await reviewTask(task);
  if (focusPrompt) requestAnimationFrame(() => el('agent-prompt-section')?.scrollIntoView({ behavior: 'smooth', block: 'start' }));
}

function closeAddMenu() {
  el('composer-add-menu').classList.add('hidden');
  el('composer-add-button').setAttribute('aria-expanded', 'false');
}

function initComposerMenu() {
  el('composer-add-button').addEventListener('click', event => {
    event.stopPropagation();
    const menu = el('composer-add-menu');
    const opening = menu.classList.contains('hidden');
    menu.classList.toggle('hidden', !opening);
    el('composer-add-button').setAttribute('aria-expanded', String(opening));
  });
  el('quick-create-task').addEventListener('click', async () => { closeAddMenu(); await createTask(); });
  el('quick-review-task').addEventListener('click', async () => { closeAddMenu(); await openCurrentProjectTask({ review: true }); });
  el('quick-agent-prompt').addEventListener('click', async () => { closeAddMenu(); await openCurrentProjectTask({ focusPrompt: true }); });
  document.addEventListener('click', event => {
    if (!event.target.closest('.composer-add')) closeAddMenu();
  });
}

export async function initImprovementTasks(sharedUi) {
  ui = sharedUi;
  el('create-task').addEventListener('click', createTask);
  el('task-project-filter').addEventListener('change', event => {
    state.filterProjectId = event.target.value;
    if (!visibleTasks().some(task => task.id === state.activeId)) state.activeId = visibleTasks()[0]?.id || '';
    renderTaskList();
    renderTaskDetail();
  });
  ui.on('projects:changed', () => { renderProjectFilter(); renderTaskList(); renderTaskDetail(); });
  ui.on('project:scanned', () => loadTasks());
  initComposerMenu();
  el('copy-agent-prompt-dialog').addEventListener('click', copyEditedAgentPrompt);
  el('edit-agent-prompt').addEventListener('click', () => togglePromptEditing(true));
  el('agent-prompt-form').addEventListener('submit', saveEditedAgentPrompt);
  await loadTasks();
}
