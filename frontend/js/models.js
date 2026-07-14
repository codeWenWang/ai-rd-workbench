import { api, errorText, listFrom } from './api.js?v=20260714.1';

let ui;
let providers = [];
const el = id => document.getElementById(id);

export function selectedModelId() {
  return el('chat-model').value || null;
}

export function comparisonModelIds() {
  if (!el('compare-models').checked) return [];
  return [el('chat-model').value, el('compare-model').value].filter(Boolean).filter((value, index, values) => values.indexOf(value) === index);
}

function render() {
  for (const id of ['chat-model', 'compare-model']) {
    const select = el(id);
    const current = select.value;
    select.innerHTML = id === 'chat-model' ? '<option value="">默认模型</option>' : '<option value="">选择对比模型</option>';
    for (const provider of providers) {
      const option = document.createElement('option');
      option.value = provider.id;
      option.textContent = `${provider.name} · ${provider.model_name}`;
      select.append(option);
    }
    if ([...select.options].some(option => option.value === current)) select.value = current;
  }
}

async function load() {
  providers = listFrom(await api.modelProviders());
  render();
}

async function addProvider() {
  const result = await ui.formDialog({
    title: '添加模型', submitText: '保存', fields: [
      { name: 'provider_type', label: '供应商类型', type: 'select', value: 'openai_compatible', options: [['dashscope', '阿里云 DashScope'], ['openai_compatible', 'OpenAI 兼容接口']], required: true },
      { name: 'name', label: '显示名称', placeholder: '例如 DeepSeek', required: true },
      { name: 'base_url', label: 'Base URL', placeholder: 'https://api.example.com/v1', required: true },
      { name: 'model_name', label: '模型名称', placeholder: '例如 deepseek-chat', required: true },
      { name: 'api_key', label: 'API Key', type: 'password', required: true },
    ],
  });
  if (!result) return;
  try { await api.createModelProvider(result); await load(); }
  catch (error) { ui.alert('chat-alerts', errorText(error)); }
}

export async function initModels(sharedUi) {
  ui = sharedUi;
  el('model-settings').addEventListener('click', addProvider);
  el('compare-models').addEventListener('change', event => {
    el('compare-model').classList.toggle('hidden', !event.target.checked);
    el('comparison-results').classList.toggle('hidden', !event.target.checked);
  });
  await load();
}
