const JSON_HEADERS = { Accept: 'application/json', 'Content-Type': 'application/json' };

export class ApiError extends Error {
  constructor({ message, code = 'HTTP_ERROR', requestId, status = 0, details }) {
    super(message);
    this.name = 'ApiError';
    this.code = code;
    this.requestId = requestId;
    this.status = status;
    this.details = details;
  }
}

export function parseApiError(payload, status = 0) {
  const root = payload && typeof payload === 'object' ? payload : {};
  const detail = root.detail && typeof root.detail === 'object' ? root.detail : {};
  const message = typeof payload === 'string'
    ? payload
    : root.message || detail.message || (typeof root.detail === 'string' ? root.detail : '') || `请求失败 (${status || '网络错误'})`;
  return {
    code: root.code || detail.code || 'HTTP_ERROR',
    message,
    requestId: root.request_id || detail.request_id,
    status,
    details: root.details || detail.details,
  };
}

async function responsePayload(response) {
  const text = await response.text();
  if (!text) return null;
  try { return JSON.parse(text); } catch { return text; }
}

export async function request(path, options = {}) {
  const { json, timeout = 20000, ...fetchOptions } = options;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  try {
    const response = await fetch(path, {
      ...fetchOptions,
      headers: json === undefined ? fetchOptions.headers : { ...JSON_HEADERS, ...fetchOptions.headers },
      body: json === undefined ? fetchOptions.body : JSON.stringify(json),
      signal: fetchOptions.signal || controller.signal,
    });
    const payload = await responsePayload(response);
    if (!response.ok) throw new ApiError(parseApiError(payload, response.status));
    return payload;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (error.name === 'AbortError') throw new ApiError({ code: 'TIMEOUT', message: '请求超时，请检查本地服务状态', status: 0 });
    throw new ApiError({ code: 'NETWORK_ERROR', message: '无法连接本地服务', status: 0, details: error.message });
  } finally { clearTimeout(timer); }
}

export async function requestWithFallback(paths, options = {}) {
  let lastError;
  for (const path of paths) {
    try { return await request(path, options); }
    catch (error) {
      lastError = error;
      if (![404, 405].includes(error.status)) throw error;
    }
  }
  throw lastError;
}

export function listFrom(payload, keys = ['items', 'results', 'data']) {
  if (Array.isArray(payload)) return payload;
  for (const key of keys) if (Array.isArray(payload?.[key])) return payload[key];
  return [];
}

export function parseSSEChunk(text) {
  const normalized = text.replace(/\r\n/g, '\n');
  const blocks = normalized.split('\n\n');
  const remainder = blocks.pop() || '';
  const events = [];
  for (const block of blocks) {
    if (!block.trim() || block.startsWith(':')) continue;
    let event = 'message';
    const dataLines = [];
    for (const line of block.split('\n')) {
      if (line.startsWith('event:')) event = line.slice(6).trim();
      else if (line.startsWith('data:')) dataLines.push(line.slice(5).trimStart());
    }
    const raw = dataLines.join('\n');
    if (!raw) continue;
    let data = raw;
    try { data = JSON.parse(raw); } catch { /* text token */ }
    events.push({ event, data });
  }
  return { events, remainder };
}

export async function streamChat(body, onEvent) {
  const controller = new AbortController();
  let response;
  try {
    response = await fetch('/api/chat/stream', {
      method: 'POST', headers: JSON_HEADERS, body: JSON.stringify(body), signal: controller.signal,
    });
  } catch (error) {
    throw new ApiError({ code: 'NETWORK_ERROR', message: '无法连接流式问答服务', details: error.message });
  }
  if (!response.ok) {
    const payload = await responsePayload(response);
    throw new ApiError(parseApiError(payload, response.status));
  }
  if (!response.body || !response.headers.get('content-type')?.includes('text/event-stream')) {
    throw new ApiError({ code: 'STREAM_UNAVAILABLE', message: '当前服务未启用流式响应', status: 501 });
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  try {
    while (true) {
      const { done, value } = await reader.read();
      buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
      const parsed = parseSSEChunk(buffer);
      buffer = parsed.remainder;
      for (const item of parsed.events) await onEvent(item.event, item.data);
      if (done) break;
    }
    if (buffer.trim()) {
      const parsed = parseSSEChunk(`${buffer}\n\n`);
      for (const item of parsed.events) await onEvent(item.event, item.data);
    }
  } finally { reader.releaseLock(); }
  return { abort: () => controller.abort() };
}

export const api = {
  conversations: projectId => request(`/api/conversations?${new URLSearchParams(projectId ? { project_id: projectId } : {})}`),
  createConversation: projectId => request('/api/chat/session', { method: 'POST', json: projectId ? { project_id: projectId } : {} }),
  messages: id => request(`/api/conversations/${encodeURIComponent(id)}/messages`),
  renameConversation: (id, title) => request(`/api/conversations/${encodeURIComponent(id)}`, { method: 'PATCH', json: { title } }),
  deleteConversation: id => request(`/api/conversations/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  chat: body => request('/api/chat', { method: 'POST', json: body, timeout: 120000 }),
  documents: params => request(`/api/documents?${new URLSearchParams(params)}`),
  document: id => request(`/api/documents/${encodeURIComponent(id)}`),
  createTextDocument: body => requestWithFallback(['/api/documents/text', '/api/knowledge/text'], { method: 'POST', json: body, timeout: 120000 }),
  createPdfDocument: form => requestWithFallback(['/api/documents/pdf', '/api/knowledge/pdf'], { method: 'POST', body: form, timeout: 120000 }),
  updateDocument: (id, body) => request(`/api/documents/${encodeURIComponent(id)}`, { method: 'PATCH', json: body, timeout: 120000 }),
  reindexDocument: id => request(`/api/documents/${encodeURIComponent(id)}/reindex`, { method: 'POST', timeout: 120000 }),
  deleteDocument: id => request(`/api/documents/${encodeURIComponent(id)}`, { method: 'DELETE', timeout: 120000 }),
  memories: () => request('/api/memories'),
  candidates: () => request('/api/memory-candidates?status=pending'),
  createMemory: body => request('/api/memories', { method: 'POST', json: body, timeout: 120000 }),
  createMemoryPdf: form => request('/api/memory/pdf', { method: 'POST', body: form, timeout: 120000 }),
  updateMemory: (id, body) => request(`/api/memories/${encodeURIComponent(id)}`, { method: 'PATCH', json: body }),
  deleteMemory: id => request(`/api/memories/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  confirmCandidate: (id, body) => request(`/api/memory-candidates/${encodeURIComponent(id)}/confirm`, { method: 'POST', json: body }),
  rejectCandidate: id => request(`/api/memory-candidates/${encodeURIComponent(id)}/reject`, { method: 'POST' }),
  live: () => request('/api/health/live', { timeout: 7000 }),
  ready: () => request('/api/health/ready', { timeout: 10000 }),
  diagnostics: () => request('/api/diagnostics', { timeout: 15000 }),
  projects: () => request('/api/projects'),
  project: id => request(`/api/projects/${encodeURIComponent(id)}`),
  createProject: body => request('/api/projects', { method: 'POST', json: body }),
  deleteProject: id => request(`/api/projects/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  scanProject: id => request(`/api/projects/${encodeURIComponent(id)}/scan`, { method: 'POST', timeout: 180000 }),
  projectFiles: id => request(`/api/projects/${encodeURIComponent(id)}/files`),
  artifacts: id => request(`/api/projects/${encodeURIComponent(id)}/artifacts`),
  generateArtifact: (id, type) => request(`/api/projects/${encodeURIComponent(id)}/artifacts/${encodeURIComponent(type)}`, { method: 'POST', timeout: 120000 }),
  modelProviders: () => request('/api/model-providers'),
  createModelProvider: body => request('/api/model-providers', { method: 'POST', json: body }),
  updateModelProvider: (id, body) => request(`/api/model-providers/${encodeURIComponent(id)}`, { method: 'PATCH', json: body }),
  deleteModelProvider: id => request(`/api/model-providers/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  compareModels: body => request('/api/models/compare', { method: 'POST', json: body, timeout: 180000 }),
};

export function errorText(error) {
  const requestId = error?.requestId ? `（请求 ${error.requestId}）` : '';
  return `${error?.message || '操作失败'}${requestId}`;
}
