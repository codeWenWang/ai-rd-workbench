import { initChat } from './chat.js?v=20260721.7';
import { initDocuments } from './documents.js?v=20260721.7';
import { initMemories } from './memories.js?v=20260721.7';
import { initDiagnostics } from './diagnostics.js?v=20260721.7';
import { initProjects } from './projects.js?v=20260721.7';
import { initArtifacts } from './artifacts.js?v=20260721.7';
import { initModels } from './models.js?v=20260721.7';
import { escapeHtml, renderMarkdown } from './markdown.js?v=20260721.1';

const eventBus = new EventTarget();
const el = id => document.getElementById(id);
const THEME_KEY = 'workbench_theme';
const SIDEBAR_KEY = 'workbench_sidebar_collapsed';

function escape(value = '') {
  return escapeHtml(value);
}

function formatTime(value) {
  if (!value) return '时间未知';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit',
  }).format(date);
}

function busy(button, active) {
  if (!button) return;
  if (active) {
    button.dataset.label = button.innerHTML;
    button.disabled = true;
    button.setAttribute('aria-busy', 'true');
    if (!button.classList.contains('icon-btn') && !button.classList.contains('send-btn')) button.textContent = '处理中…';
    return;
  }
  button.disabled = false;
  button.removeAttribute('aria-busy');
  if (button.dataset.label) {
    button.innerHTML = button.dataset.label;
    delete button.dataset.label;
  }
}

function alert(containerId, message, type = 'error') {
  const container = el(containerId);
  if (!container) return;
  const box = document.createElement('div');
  box.className = `inline-alert ${type}`;
  box.setAttribute('role', type === 'error' ? 'alert' : 'status');
  box.textContent = message;
  container.replaceChildren(box);
}

function openDrawer({ eyebrow = '', title = '详情', html = '' }) {
  el('drawer-eyebrow').textContent = eyebrow;
  el('drawer-title').textContent = title;
  el('drawer-content').innerHTML = html;
  el('detail-drawer').classList.add('open');
  el('detail-drawer').setAttribute('aria-hidden', 'false');
  el('drawer-backdrop').classList.remove('hidden');
  el('close-drawer').focus();
}

function closeDrawer() {
  el('detail-drawer').classList.remove('open');
  el('detail-drawer').setAttribute('aria-hidden', 'true');
  el('drawer-backdrop').classList.add('hidden');
}

function buildField(field) {
  const label = document.createElement('label');
  label.dataset.field = field.name;
  const text = document.createElement('span');
  text.textContent = field.label;
  label.append(text);
  let input;
  if (field.type === 'textarea') {
    input = document.createElement('textarea');
    input.value = field.value || '';
    input.placeholder = field.placeholder || '';
  } else if (field.type === 'select') {
    input = document.createElement('select');
    for (const [value, labelText] of field.options || []) {
      const option = document.createElement('option');
      option.value = value;
      option.textContent = labelText;
      input.append(option);
    }
    input.value = field.value || '';
  } else if (field.type === 'directory') {
    const picker = document.createElement('div');
    picker.className = 'directory-picker';
    input = document.createElement('input');
    input.type = 'text';
    input.readOnly = true;
    input.placeholder = field.placeholder || '点击右侧按钮选择本机文件夹';
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'button secondary';
    button.textContent = '选择文件夹';
    button.addEventListener('click', async () => {
      button.disabled = true;
      try {
        const response = await fetch('/api/projects/select-directory', { method: 'POST' });
        const payload = await response.json();
        if (!response.ok) throw new Error(payload?.detail?.message || payload?.detail || '无法打开文件夹选择器');
        input.value = payload.path || '';
      } catch (error) {
        el('dialog-error').textContent = error.message;
        el('dialog-error').classList.remove('hidden');
      } finally { button.disabled = false; }
    });
    picker.append(input, button);
    label.append(picker);
  } else {
    input = document.createElement('input');
    input.type = field.type || 'text';
    if (field.type !== 'file') input.value = field.value || '';
    if (field.accept) input.accept = field.accept;
  }
  input.name = field.name;
  input.autocomplete = field.autocomplete || 'off';
  if (field.required) input.required = true;
  if (field.maxlength) input.maxLength = field.maxlength;
  if (field.type !== 'directory') label.append(input);
  if (field.requiredWhen) {
    label.dataset.requiredField = Object.keys(field.requiredWhen)[0];
    label.dataset.requiredValue = Object.values(field.requiredWhen)[0];
  }
  return label;
}

function updateConditionalFields(body) {
  body.querySelectorAll('[data-required-field]').forEach(label => {
    const controller = body.querySelector(`[name="${CSS.escape(label.dataset.requiredField)}"]`);
    const visible = controller?.value === label.dataset.requiredValue;
    label.classList.toggle('hidden', !visible);
    const input = label.querySelector('input,textarea,select');
    input.required = visible;
    if (!visible && input.type === 'file') input.value = '';
  });
}

function dialogResult(fields) {
  const result = {};
  for (const field of fields) {
    const input = el('dialog-body').querySelector(`[name="${CSS.escape(field.name)}"]`);
    if (!input || input.closest('.hidden')) continue;
    result[field.name] = input.type === 'file' ? input.files[0] : input.value.trim();
  }
  return result;
}

function formDialog({ title, submitText = '确认', fields = [] }) {
  const dialog = el('app-dialog');
  const body = el('dialog-body');
  const form = el('dialog-form');
  form.autocomplete = 'off';
  el('dialog-title').textContent = title;
  el('dialog-submit').textContent = submitText;
  el('dialog-submit').className = 'button primary';
  el('dialog-error').classList.add('hidden');
  body.innerHTML = '';
  fields.forEach(field => body.append(buildField(field)));
  body.querySelectorAll('select').forEach(select => select.addEventListener('change', () => updateConditionalFields(body)));
  updateConditionalFields(body);
  dialog.showModal();
  requestAnimationFrame(() => body.querySelector('input:not([type=file]),textarea,select')?.focus());
  return new Promise(resolve => {
    const cancelButtons = [...form.querySelectorAll('[value="cancel"]')];
    const cleanup = () => {
      form.removeEventListener('submit', submit);
      dialog.removeEventListener('cancel', cancel);
      cancelButtons.forEach(button => button.removeEventListener('click', cancelClick));
    };
    const cancelClick = event => {
      event.preventDefault(); cleanup(); dialog.close('cancel'); resolve(null);
    };
    const submit = event => {
      event.preventDefault();
      if (event.submitter?.value === 'cancel') {
        cleanup(); dialog.close('cancel'); resolve(null); return;
      }
      if (!form.reportValidity()) return;
      const result = dialogResult(fields);
      cleanup(); dialog.close('default'); resolve(result);
    };
    const cancel = event => {
      event.preventDefault(); cleanup(); dialog.close('cancel'); resolve(null);
    };
    form.addEventListener('submit', submit);
    dialog.addEventListener('cancel', cancel);
    cancelButtons.forEach(button => button.addEventListener('click', cancelClick));
  });
}

function confirmDialog(title, message, submitText = '确认') {
  const dialog = el('app-dialog');
  const body = el('dialog-body');
  const form = el('dialog-form');
  el('dialog-title').textContent = title;
  body.innerHTML = `<p>${escape(message)}</p>`;
  el('dialog-submit').textContent = submitText;
  el('dialog-submit').className = 'button danger';
  el('dialog-error').classList.add('hidden');
  dialog.showModal();
  el('dialog-submit').focus();
  return new Promise(resolve => {
    const cancelButtons = [...form.querySelectorAll('[value="cancel"]')];
    const cleanup = () => {
      form.removeEventListener('submit', submit);
      dialog.removeEventListener('cancel', cancel);
      cancelButtons.forEach(button => button.removeEventListener('click', cancelClick));
    };
    const cancelClick = event => {
      event.preventDefault(); cleanup(); dialog.close('cancel'); resolve(false);
    };
    const submit = event => {
      event.preventDefault();
      const confirmed = event.submitter?.value !== 'cancel';
      cleanup(); dialog.close(confirmed ? 'default' : 'cancel'); resolve(confirmed);
    };
    const cancel = event => {
      event.preventDefault(); cleanup(); dialog.close('cancel'); resolve(false);
    };
    form.addEventListener('submit', submit);
    dialog.addEventListener('cancel', cancel);
    cancelButtons.forEach(button => button.addEventListener('click', cancelClick));
  });
}

const ui = {
  escape, renderMarkdown, formatTime, busy, alert, openDrawer, closeDrawer, formDialog, confirmDialog,
  showView: switchView,
  emit: (name, detail) => eventBus.dispatchEvent(new CustomEvent(name, { detail })),
  on: (name, handler) => eventBus.addEventListener(name, event => handler(event.detail)),
};

function closeMobileSidebar() {
  el('sidebar').classList.remove('open');
  el('sidebar-backdrop').classList.add('hidden');
  el('menu-toggle').setAttribute('aria-expanded', 'false');
}

function switchView(name) {
  document.querySelectorAll('.view').forEach(view => view.classList.toggle('active', view.id === `view-${name}`));
  document.querySelectorAll('button.nav-item[data-view]').forEach(button => {
    const active = button.dataset.view === name;
    button.classList.toggle('active', active);
    if (active) button.setAttribute('aria-current', 'page'); else button.removeAttribute('aria-current');
  });
  location.hash = name === 'chat' ? '' : name;
  closeMobileSidebar();
}

function setTheme(theme) {
  document.documentElement.dataset.theme = theme;
  localStorage.setItem(THEME_KEY, theme);
  const next = theme === 'dark' ? '浅色模式' : '深色模式';
  el('theme-label').textContent = next;
  el('theme-toggle').title = `切换到${next}`;
  ui.emit('theme:changed', theme);
}

function setSidebarCollapsed(collapsed) {
  el('app-shell').classList.toggle('sidebar-collapsed', collapsed);
  el('sidebar-collapse').textContent = collapsed ? '›' : '‹';
  el('sidebar-collapse').setAttribute('aria-expanded', String(!collapsed));
  el('sidebar-collapse').setAttribute('aria-label', collapsed ? '展开侧边栏' : '收起侧边栏');
  el('sidebar-collapse').title = collapsed ? '展开侧边栏' : '收起侧边栏';
  localStorage.setItem(SIDEBAR_KEY, String(collapsed));
}

async function initialize() {
  setTheme(document.documentElement.dataset.theme || 'light');
  setSidebarCollapsed(localStorage.getItem(SIDEBAR_KEY) === 'true');
  document.querySelectorAll('button[data-view]').forEach(button => button.addEventListener('click', () => switchView(button.dataset.view)));
  el('theme-toggle').addEventListener('click', () => setTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark'));
  el('diagnostics-toggle').addEventListener('click', () => switchView('diagnostics'));
  el('sidebar-collapse').addEventListener('click', () => {
    if (matchMedia('(max-width: 760px)').matches) closeMobileSidebar();
    else setSidebarCollapsed(!el('app-shell').classList.contains('sidebar-collapsed'));
  });
  el('menu-toggle').addEventListener('click', () => {
    const open = el('sidebar').classList.toggle('open');
    el('sidebar-backdrop').classList.toggle('hidden', !open);
    el('menu-toggle').setAttribute('aria-expanded', String(open));
  });
  el('sidebar-backdrop').addEventListener('click', closeMobileSidebar);
  el('close-drawer').addEventListener('click', closeDrawer);
  el('drawer-backdrop').addEventListener('click', closeDrawer);
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape') {
      if (el('detail-drawer').classList.contains('open')) closeDrawer();
      closeMobileSidebar();
    }
  });
  const requested = location.hash.slice(1);
  const allowedViews = ['chat', 'overview', 'architecture', 'flow', 'sequence', 'project-api', 'knowledge', 'memories', 'diagnostics'];
  if (allowedViews.includes(requested)) switchView(requested);
  const projectResult = await Promise.allSettled([initProjects(ui)]);
  if (projectResult[0].status === 'rejected') console.error('projects', projectResult[0].reason);
  const results = await Promise.allSettled([
    initChat(ui), initArtifacts(ui), initModels(ui),
    initDocuments(ui), initMemories(ui), initDiagnostics(ui),
  ]);
  results.forEach((result, index) => {
    if (result.status === 'rejected') console.error(['chat', 'artifacts', 'models', 'documents', 'memories', 'diagnostics'][index], result.reason);
  });
}

initialize();
