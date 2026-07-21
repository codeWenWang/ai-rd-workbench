import { api, errorText, listFrom } from './api.js?v=20260721.7';

let ui;
let providers = [];
const el = id => document.getElementById(id);
const providerTypes = [['dashscope', '阿里云 DashScope'], ['openai_compatible', 'OpenAI 兼容接口']];

export function selectedModelId() {
  return el('chat-model').value || null;
}

export function comparisonModelIds() {
  if (!el('compare-models').checked) return [];
  return [el('chat-model').value, el('compare-model').value]
    .filter(Boolean)
    .filter((value, index, values) => values.indexOf(value) === index);
}

function renderSelectors() {
  for (const id of ['chat-model', 'compare-model']) {
    const select = el(id);
    const current = select.value;
    select.innerHTML = id === 'chat-model'
      ? '<option value="">默认模型</option>'
      : '<option value="">选择对比模型</option>';
    for (const provider of providers) {
      const option = document.createElement('option');
      option.value = provider.id;
      option.textContent = `${provider.name} · ${provider.model_name}`;
      select.append(option);
    }
    select.value = [...select.options].some(option => option.value === current) ? current : '';
  }
}

async function load() {
  providers = listFrom(await api.modelProviders());
  renderSelectors();
}

function providerFields(provider = null) {
  return [
    { name: 'provider_type', label: '供应商类型', type: 'select', value: provider?.provider_type || 'openai_compatible', options: providerTypes, required: true },
    { name: 'name', label: '显示名称', value: provider?.name || '', placeholder: '例如 DeepSeek', required: true },
    { name: 'base_url', label: 'Base URL', value: provider?.base_url || '', placeholder: 'https://api.example.com/v1', required: true },
    { name: 'model_name', label: '模型名称', value: provider?.model_name || '', placeholder: '例如 deepseek-chat', required: true },
    { name: 'api_key', label: provider ? 'API Key（留空保持原密钥）' : 'API Key', type: 'password', required: !provider },
  ];
}

async function saveProvider(provider = null) {
  const result = await ui.formDialog({
    title: provider ? '编辑模型' : '添加模型',
    submitText: '保存',
    fields: providerFields(provider),
  });
  if (!result) return;
  try {
    if (provider) await api.updateModelProvider(provider.id, result);
    else await api.createModelProvider(result);
    await load();
    await openModelManager(false);
  } catch (error) {
    ui.alert('chat-alerts', errorText(error));
  }
}

async function deleteProvider(provider) {
  const confirmed = await ui.confirmDialog(
    '删除模型',
    `确定删除“${provider.name} · ${provider.model_name}”吗？`,
    '删除',
  );
  if (!confirmed) return;
  try {
    await api.deleteModelProvider(provider.id);
    await load();
    await openModelManager(false);
  } catch (error) {
    ui.alert('chat-alerts', errorText(error));
  }
}

function managerHtml() {
  const rows = providers.length
    ? providers.map(provider => `
      <article class="model-provider-row" data-provider-id="${ui.escape(provider.id)}">
        <div class="model-provider-main">
          <strong>${ui.escape(provider.name)}</strong>
          <span>${ui.escape(provider.model_name)}</span>
          <small>${provider.provider_type === 'dashscope' ? '阿里云 DashScope' : 'OpenAI 兼容接口'} · ${ui.escape(provider.base_url)}</small>
        </div>
        <div class="model-provider-actions">
          <button class="button" data-model-action="edit">编辑</button>
          <button class="button danger" data-model-action="delete">删除</button>
        </div>
      </article>`).join('')
    : '<div class="empty-state"><strong>还没有模型配置</strong><span>添加一个模型后即可在对话中切换或对比。</span></div>';
  return `
    <div class="model-manager-toolbar">
      <p>API Key 加密保存在本机，不会在页面中回显。</p>
      <button class="button primary" data-model-action="add">＋ 添加模型</button>
    </div>
    <div class="model-provider-list">${rows}</div>`;
}

function bindManagerActions() {
  const content = el('drawer-content');
  content.querySelector('[data-model-action="add"]')?.addEventListener('click', () => saveProvider());
  content.querySelectorAll('.model-provider-row').forEach(row => {
    const provider = providers.find(item => item.id === row.dataset.providerId);
    row.querySelector('[data-model-action="edit"]')?.addEventListener('click', () => saveProvider(provider));
    row.querySelector('[data-model-action="delete"]')?.addEventListener('click', () => deleteProvider(provider));
  });
}

async function openModelManager(refresh = true) {
  try {
    if (refresh) await load();
    ui.openDrawer({
      eyebrow: '模型配置',
      title: '模型设置',
      html: managerHtml(),
    });
    bindManagerActions();
  } catch (error) {
    ui.alert('chat-alerts', errorText(error));
  }
}

export async function initModels(sharedUi) {
  ui = sharedUi;
  el('model-settings').addEventListener('click', openModelManager);
  el('compare-models').addEventListener('change', event => {
    el('compare-model').classList.toggle('hidden', !event.target.checked);
  });
  await load();
}
