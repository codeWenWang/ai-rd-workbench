import { api, errorText, listFrom, streamChat } from './api.js?v=20260714.3';
import { groupConversations } from './conversation-groups.js?v=20260714.4';
import { activeProjectId, projectById } from './projects.js?v=20260715.2';
import { comparisonModelIds, selectedModelId } from './models.js?v=20260714.3';

const stageNames = {
  receive_query: '接收问题', understand_query: '理解问题', retrieving: '检索资料', retrieve_context: '检索资料',
  merge_and_rank: '整理资料', reranking: '整理资料', evaluate_context: '评估资料', generating: '生成回答',
  generate_answer: '生成回答', validate_citations: '校验引用', persist_result: '保存结果', propose_memories: '提取记忆建议', done: '已完成',
};

const state = {
  conversations: [],
  activeId: localStorage.getItem('conversation_id') || '',
  messages: [],
  sending: false,
};
const expandedProjectIds = new Set();
let ui;

const el = id => document.getElementById(id);
const value = (obj, ...keys) => keys.map(key => obj?.[key]).find(item => item !== undefined && item !== null);
const conversationId = item => value(item, 'id', 'conversation_id', 'session_id');
const normalizeProjectId = item => String(typeof item === 'object' ? value(item, 'project_id') || '' : item || '');
const conversationTitle = item => {
  const title = value(item, 'title', 'name');
  return !title || title === 'New conversation' ? '新对话' : title;
};

function activeConversation() {
  return state.conversations.find(item => conversationId(item) === state.activeId);
}

function syncActiveTitle() {
  el('active-conversation-title').textContent = conversationTitle(activeConversation());
}

function conversationRow(item) {
  const id = conversationId(item);
  const row = document.createElement('div');
  row.className = `conversation-row${id === state.activeId ? ' active' : ''}`;

  const select = document.createElement('button');
  select.className = 'conversation-item';
  select.title = conversationTitle(item);
  select.innerHTML = `<strong>${ui.escape(conversationTitle(item))}</strong><span>${ui.escape(ui.formatTime(value(item, 'updated_at', 'created_at')))}</span>`;
  select.addEventListener('click', () => selectConversation(id));

  const actions = document.createElement('div');
  actions.className = 'conversation-actions';
  const rename = document.createElement('button');
  rename.className = 'conversation-action';
  rename.type = 'button';
  rename.title = '重命名';
  rename.setAttribute('aria-label', `重命名${conversationTitle(item)}`);
  rename.textContent = '✎';
  rename.addEventListener('click', () => renameConversation(item));
  const remove = document.createElement('button');
  remove.className = 'conversation-action danger';
  remove.type = 'button';
  remove.title = '删除';
  remove.setAttribute('aria-label', `删除${conversationTitle(item)}`);
  remove.textContent = '×';
  remove.addEventListener('click', () => deleteConversation(item));
  actions.append(rename, remove);
  row.append(select, actions);
  return row;
}

function setProjectGroupExpanded(group, panel, toggle, expanded) {
  const projectId = group.dataset.projectId;
  group.classList.toggle('collapsed', !expanded);
  toggle.setAttribute('aria-expanded', String(expanded));
  panel.setAttribute('aria-hidden', String(!expanded));
  panel.inert = !expanded;
  if (expanded) expandedProjectIds.add(projectId); else expandedProjectIds.delete(projectId);
}

function projectHistoryGroup(groupData) {
  const group = document.createElement('section');
  group.className = 'project-history-group';
  group.dataset.projectId = groupData.projectId;

  const toggle = document.createElement('button');
  toggle.type = 'button';
  toggle.className = 'project-history-toggle';
  const label = document.createElement('strong');
  label.textContent = groupData.name;
  const count = document.createElement('span');
  count.className = 'project-history-count';
  count.textContent = String(groupData.conversations.length);
  const chevron = document.createElement('span');
  chevron.className = 'project-history-chevron';
  chevron.setAttribute('aria-hidden', 'true');
  chevron.textContent = '›';
  toggle.append(label, count, chevron);

  const panel = document.createElement('div');
  panel.className = 'project-conversation-panel';
  const inner = document.createElement('div');
  inner.className = 'project-conversation-inner';
  groupData.conversations.forEach(item => inner.append(conversationRow(item)));
  panel.append(inner);
  group.append(toggle, panel);

  const expanded = expandedProjectIds.has(groupData.projectId);
  setProjectGroupExpanded(group, panel, toggle, expanded);
  toggle.addEventListener('click', () => {
    setProjectGroupExpanded(group, panel, toggle, toggle.getAttribute('aria-expanded') !== 'true');
  });
  return group;
}

function renderConversations() {
  const container = el('conversation-list');
  container.innerHTML = '';
  if (!state.conversations.length) {
    container.innerHTML = '<div class="history-empty">还没有对话</div>';
    syncActiveTitle();
    return;
  }

  const activeProject = normalizeProjectId(activeConversation());
  if (activeProject) expandedProjectIds.add(activeProject);
  const grouped = groupConversations(state.conversations, projectId => projectById(projectId)?.name);
  grouped.projects.forEach(group => container.append(projectHistoryGroup(group)));
  if (grouped.general.length) {
    const label = document.createElement('div');
    label.className = 'conversation-group-label';
    label.textContent = '通用对话';
    container.append(label);
    grouped.general.forEach(item => container.append(conversationRow(item)));
  }
  syncActiveTitle();
}

function normalizeCitation(citation, index) {
  return {
    id: index + 1,
    title: value(citation, 'title', 'source_name', 'document_title') || `来源 ${index + 1}`,
    category: value(citation, 'category', 'kind') || '未分类',
    page: value(citation, 'page_number', 'page'),
    excerpt: value(citation, 'excerpt', 'content', 'text', 'snippet') || '暂无原文片段',
    chunkId: value(citation, 'chunk_id', 'id'),
    relativePath: value(citation, 'relative_path'),
    startLine: value(citation, 'start_line'),
    endLine: value(citation, 'end_line'),
  };
}

function normalizeMessage(message) {
  const metadata = value(message, 'metadata') || {};
  return {
    id: value(message, 'id', 'message_id') || crypto.randomUUID(),
    role: value(message, 'role') || 'assistant',
    content: value(message, 'content', 'answer', 'message') || '',
    status: value(message, 'status') || 'completed',
    citations: listFrom(value(message, 'citations', 'sources') || []).map(normalizeCitation),
    warnings: listFrom(value(message, 'warnings') || []).map(w => typeof w === 'string' ? w : value(w, 'message', 'code') || JSON.stringify(w)),
    error: value(message, 'error_message', 'error', 'message_error'),
    prompt: value(message, 'prompt', 'original_query'),
    metadata,
    comparison: metadata.type === 'model_comparison' ? listFrom(metadata.items || []) : [],
  };
}

function renderMessages() {
  const container = el('message-list');
  if (!state.messages.length) {
    container.innerHTML = '<div class="empty-state chat-empty"><strong>今天想解决什么问题？</strong></div>';
    return;
  }
  container.innerHTML = '';
  for (const message of state.messages) container.append(messageNode(message));
  requestAnimationFrame(() => { container.scrollTop = container.scrollHeight; });
}

function comparisonTurnNode(message) {
  const turn = document.createElement('section');
  turn.className = 'comparison-turn';
  const heading = document.createElement('header');
  heading.className = 'comparison-heading';
  const title = document.createElement('strong');
  title.textContent = '模型对比';
  const subtitle = document.createElement('span');
  subtitle.textContent = '相同问题与上下文，并行生成';
  heading.append(title, subtitle);
  turn.append(heading);

  if (message.status === 'pending' && !message.comparison.length) {
    const loading = document.createElement('div');
    loading.className = 'comparison-loading';
    loading.textContent = '正在并行调用两个模型…';
    turn.append(loading);
    return turn;
  }

  const grid = document.createElement('div');
  grid.className = 'comparison-grid';
  for (const item of message.comparison) {
    const card = document.createElement('article');
    card.className = `comparison-card${item.error ? ' failed' : ''}`;
    const cardHeader = document.createElement('header');
    const name = document.createElement('strong');
    name.textContent = [item.provider_name, item.model_name].filter(Boolean).join(' · ') || '未命名模型';
    const latency = document.createElement('span');
    latency.textContent = `${Number(item.latency_ms || 0)} ms`;
    cardHeader.append(name, latency);
    const answer = document.createElement('div');
    answer.className = 'comparison-answer';
    answer.textContent = item.answer || item.error || '没有返回内容';
    card.append(cardHeader, answer);
    grid.append(card);
  }
  turn.append(grid);
  return turn;
}

function messageNode(message) {
  const article = document.createElement('article');
  article.className = `message ${message.role}${message.status === 'failed' ? ' failed' : ''}`;
  article.dataset.messageId = message.id;

  const content = document.createElement('div');
  content.className = 'message-content';
  if (message.role === 'assistant') {
    const avatar = document.createElement('div');
    avatar.className = 'assistant-avatar';
    avatar.textContent = 'AI';
    avatar.setAttribute('aria-hidden', 'true');
    article.append(avatar);
  }

  if (message.metadata.type === 'model_comparison') {
    content.append(comparisonTurnNode(message));
    article.classList.add('comparison-message');
  } else {
    const body = document.createElement('div');
    body.className = 'message-body';
    body.textContent = message.content || (message.status === 'pending' ? '正在思考…' : '');
    content.append(body);
  }

  const meta = document.createElement('div');
  meta.className = 'message-meta';
  for (const citation of message.citations || []) {
    const button = document.createElement('button');
    button.className = 'citation-button';
    button.textContent = `[${citation.id}] ${citation.title}${citation.page ? ` · 第 ${citation.page} 页` : ''}`;
    button.addEventListener('click', () => showCitation(citation));
    meta.append(button);
  }
  for (const warning of message.warnings || []) {
    const box = document.createElement('div');
    box.className = 'warning-box';
    box.textContent = `提示：${warning}`;
    meta.append(box);
  }
  if (message.error || message.status === 'failed') {
    const box = document.createElement('div');
    box.className = 'error-box';
    const text = document.createElement('span');
    text.textContent = message.error || '回答失败，问题已保留。';
    const retry = document.createElement('button');
    retry.className = 'retry-button';
    retry.textContent = '重试';
    retry.addEventListener('click', () => retryMessage(message));
    box.append(text, document.createTextNode(' '), retry);
    meta.append(box);
  }
  content.append(meta);
  article.append(content);
  return article;
}

function showCitation(citation) {
  const location = citation.relativePath
    ? `${citation.relativePath}${citation.startLine ? `:${citation.startLine}${citation.endLine && citation.endLine !== citation.startLine ? `-${citation.endLine}` : ''}` : ''}`
    : '无';
  ui.openDrawer({
    eyebrow: `引用 ${citation.id}`,
    title: citation.title,
    html: `<div class="drawer-section"><h3>来源信息</h3><div class="drawer-fields"><div><span>分类</span><strong>${ui.escape(citation.category)}</strong></div><div><span>源码位置</span><strong>${ui.escape(location)}</strong></div><div><span>页码</span><strong>${citation.page ? `第 ${citation.page} 页` : '无'}</strong></div><div><span>片段 ID</span><strong>${ui.escape(citation.chunkId || '无')}</strong></div></div></div><div class="drawer-section"><h3>原文片段</h3><div class="source-text">${ui.escape(citation.excerpt)}</div></div>`,
  });
}

function setStage(stage, active = true) {
  const target = el('chat-stage');
  target.textContent = stageNames[stage] || stage || '处理中';
  target.classList.toggle('active', active);
}

function showConversationError(error) {
  const target = el('conversation-error');
  target.textContent = errorText(error);
  target.classList.remove('hidden');
}

async function loadConversations({ select = true, preferredProjectId = activeProjectId() } = {}) {
  try {
    const payload = await api.conversations();
    state.conversations = listFrom(payload, ['conversations', 'items', 'data']);
    el('conversation-error').classList.add('hidden');
    if (state.activeId && !state.conversations.some(item => conversationId(item) === state.activeId)) {
      state.activeId = '';
      localStorage.removeItem('conversation_id');
    }
    if (select && !state.activeId) {
      const preferred = normalizeProjectId(preferredProjectId);
      const target = state.conversations.find(item => normalizeProjectId(item) === preferred);
      state.activeId = target ? conversationId(target) : '';
      if (state.activeId) localStorage.setItem('conversation_id', state.activeId);
      else localStorage.removeItem('conversation_id');
    }
    renderConversations();
    if (select) await loadMessages();
  } catch (error) {
    state.conversations = [];
    renderConversations();
    showConversationError(error);
  }
}

async function loadMessages() {
  if (!state.activeId) {
    state.messages = [];
    renderMessages();
    syncActiveTitle();
    return;
  }
  syncActiveTitle();
  try {
    const payload = await api.messages(state.activeId);
    state.messages = listFrom(payload, ['messages', 'items', 'data']).map(normalizeMessage);
    renderMessages();
  } catch (error) {
    state.messages = [];
    renderMessages();
    ui.alert('chat-alerts', errorText(error), 'error');
  }
}

async function selectConversation(id) {
  if (state.sending) return;
  ui.showView('chat');
  if (id === state.activeId) return;
  state.activeId = id;
  localStorage.setItem('conversation_id', id);
  renderConversations();
  await loadMessages();
}

function conversationContextProjectId() {
  return normalizeProjectId(activeConversation()) || normalizeProjectId(activeProjectId()) || null;
}

async function createConversation() {
  ui.showView('chat');
  const button = el('new-conversation');
  ui.busy(button, true);
  try {
    const payload = await api.createConversation(activeProjectId());
    state.activeId = value(payload, 'conversation_id', 'session_id', 'id');
    if (!state.activeId) throw new Error('创建会话响应中缺少 ID');
    localStorage.setItem('conversation_id', state.activeId);
    state.messages = [];
    renderMessages();
    await loadConversations({ select: false });
    renderConversations();
    el('chat-input').focus();
  } catch (error) {
    ui.alert('chat-alerts', errorText(error), 'error');
  } finally {
    ui.busy(button, false);
  }
}

async function ensureConversation() {
  if (!state.activeId) await createConversation();
  return state.activeId;
}

function appendAssistant() {
  const message = normalizeMessage({ role: 'assistant', status: 'pending', content: '', citations: [], warnings: [] });
  state.messages.push(message);
  renderMessages();
  return message;
}

function updateMessage(message) {
  const node = document.querySelector(`[data-message-id="${CSS.escape(message.id)}"]`);
  if (!node) return renderMessages();
  node.replaceWith(messageNode(message));
  el('message-list').scrollTop = el('message-list').scrollHeight;
}

function applyStreamEvent(message, eventName, payload) {
  const type = payload?.type || eventName;
  if (type === 'stage') setStage(value(payload, 'stage', 'name', 'node'));
  else if (type === 'token') {
    message.content += typeof payload === 'string' ? payload : value(payload, 'token', 'content', 'text') || '';
    updateMessage(message);
  } else if (type === 'citations' || type === 'citation') {
    const citationPayload = value(payload, 'citations', 'data') || payload;
    const citations = type === 'citation' && !Array.isArray(citationPayload) ? [citationPayload] : listFrom(citationPayload);
    message.citations = citations.map(normalizeCitation);
    updateMessage(message);
  } else if (type === 'warning') {
    message.warnings.push(typeof payload === 'string' ? payload : value(payload, 'message', 'warning', 'code') || '检索已降级');
    updateMessage(message);
  } else if (type === 'error') {
    message.error = typeof payload === 'string' ? payload : value(payload, 'message', 'error') || '回答失败';
    message.status = 'failed';
    updateMessage(message);
  } else if (type === 'done') {
    message.content ||= value(payload, 'answer', 'content') || '';
    message.citations = message.citations.length ? message.citations : listFrom(value(payload, 'citations') || []).map(normalizeCitation);
    message.warnings.push(...listFrom(value(payload, 'warnings') || []).map(w => typeof w === 'string' ? w : w.message));
    message.status = message.error ? 'failed' : 'completed';
    updateMessage(message);
    setStage('done', false);
  }
}

async function postFallback(text, message) {
  const payload = await api.chat({ message: text, session_id: state.activeId });
  message.content = value(payload, 'answer', 'content', 'message') || '';
  message.citations = listFrom(value(payload, 'citations', 'sources') || []).map(normalizeCitation);
  message.warnings = listFrom(value(payload, 'warnings') || []).map(w => typeof w === 'string' ? w : w.message);
  message.status = 'completed';
  updateMessage(message);
}

async function send(text) {
  if (!text.trim() || state.sending) return;
  state.sending = true;
  ui.busy(el('send-message'), true);
  el('chat-input').disabled = true;
  try {
    const compareIds = comparisonModelIds();
    if (document.getElementById('compare-models').checked) {
      if (compareIds.length !== 2) throw new Error('模型对比需要选择两个不同的模型');
      await sendComparison(text, compareIds);
      return;
    }
    await ensureConversation();
    state.messages.push(normalizeMessage({ role: 'user', content: text, status: 'completed', prompt: text }));
    const assistant = appendAssistant();
    setStage('receive_query');
    try {
      await streamChat({
        message: text,
        session_id: state.activeId,
        project_id: conversationContextProjectId(),
        model_id: selectedModelId(),
      }, (event, data) => applyStreamEvent(assistant, event, data));
      if (assistant.status === 'pending') {
        assistant.status = 'completed';
        updateMessage(assistant);
      }
    } catch (error) {
      if ([404, 405, 501].includes(error.status) || error.code === 'STREAM_UNAVAILABLE') await postFallback(text, assistant);
      else throw error;
    }
    setStage('done', false);
    await loadConversations({ select: false });
    renderConversations();
    ui.emit('memories:refresh');
  } catch (error) {
    const assistant = state.messages.at(-1);
    if (assistant?.role === 'assistant') {
      assistant.status = 'failed';
      assistant.error = errorText(error);
      assistant.prompt = text;
      updateMessage(assistant);
    }
    setStage('回答失败', false);
  } finally {
    state.sending = false;
    ui.busy(el('send-message'), false);
    el('chat-input').disabled = false;
    el('chat-input').focus();
  }
}

async function sendComparison(text, modelIds) {
  await ensureConversation();
  state.messages.push(normalizeMessage({
    role: 'user', content: text, status: 'completed', prompt: text,
  }));
  const comparison = normalizeMessage({
    role: 'assistant',
    content: '模型对比结果',
    status: 'pending',
    prompt: text,
    metadata: { type: 'model_comparison', items: [] },
  });
  state.messages.push(comparison);
  renderMessages();
  setStage('generating');
  const payload = await api.compareModels({
    message: text,
    model_ids: modelIds,
    project_id: conversationContextProjectId(),
    session_id: state.activeId,
  });
  state.activeId = value(payload, 'session_id') || state.activeId;
  localStorage.setItem('conversation_id', state.activeId);
  comparison.id = value(payload, 'message_id') || comparison.id;
  comparison.status = 'completed';
  comparison.metadata = { type: 'model_comparison', items: listFrom(payload) };
  comparison.comparison = comparison.metadata.items;
  comparison.citations = listFrom(value(payload, 'citations') || []).map(normalizeCitation);
  comparison.warnings = listFrom(value(payload, 'warnings') || []).map(item => typeof item === 'string' ? item : item.message);
  updateMessage(comparison);
  setStage('done', false);
  await loadConversations({ select: false });
  renderConversations();
}

function retryMessage(message) {
  const index = state.messages.indexOf(message);
  const previous = [...state.messages].slice(0, index).reverse().find(item => item.role === 'user');
  const prompt = message.prompt || previous?.content;
  if (prompt) send(prompt);
}

async function renameConversation(item) {
  const id = conversationId(item);
  const result = await ui.formDialog({
    title: '重命名对话',
    submitText: '保存',
    fields: [{ name: 'title', label: '对话名称', value: conversationTitle(item), required: true, maxlength: 100 }],
  });
  if (!result) return;
  try {
    await api.renameConversation(id, result.title);
    await loadConversations({ select: false });
    renderConversations();
  } catch (error) {
    ui.alert('chat-alerts', errorText(error), 'error');
  }
}

async function deleteConversation(item) {
  const id = conversationId(item);
  if (!await ui.confirmDialog('删除对话', `确定删除“${conversationTitle(item)}”吗？其中的消息将永久删除。`, '删除')) return;
  try {
    await api.deleteConversation(id);
    const wasActive = id === state.activeId;
    state.conversations = state.conversations.filter(entry => conversationId(entry) !== id);
    if (wasActive) {
      const fallbackProjectId = normalizeProjectId(item);
      const fallback = state.conversations.find(entry => normalizeProjectId(entry) === fallbackProjectId);
      state.activeId = fallback ? conversationId(fallback) : '';
      if (state.activeId) localStorage.setItem('conversation_id', state.activeId); else localStorage.removeItem('conversation_id');
      await loadMessages();
    }
    renderConversations();
  } catch (error) {
    ui.alert('chat-alerts', errorText(error), 'error');
  }
}

function resizeInput() {
  const input = el('chat-input');
  input.style.height = 'auto';
  input.style.height = `${Math.min(input.scrollHeight, 160)}px`;
}

export async function initChat(sharedUi) {
  ui = sharedUi;
  el('chat-form').addEventListener('submit', event => {
    event.preventDefault();
    const input = el('chat-input');
    const text = input.value.trim();
    if (text) {
      input.value = '';
      resizeInput();
      send(text);
    }
  });
  el('chat-input').addEventListener('input', resizeInput);
  el('chat-input').addEventListener('keydown', event => {
    if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      el('chat-form').requestSubmit();
    }
  });
  el('new-conversation').addEventListener('click', createConversation);
  ui.on('project:changed', async ({ projectId } = {}) => {
    if (state.sending) return;
    state.activeId = '';
    state.messages = [];
    localStorage.removeItem('conversation_id');
    renderMessages();
    await loadConversations({ preferredProjectId: projectId || '' });
  });
  await loadConversations();
}
