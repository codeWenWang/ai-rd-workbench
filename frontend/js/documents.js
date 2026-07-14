import { api, errorText, listFrom } from './api.js?v=20260713.4';

let ui;
let documents = [];
let searchTimer;
const el = id => document.getElementById(id);
const value = (obj, ...keys) => keys.map(key => obj?.[key]).find(item => item !== undefined && item !== null);
const statusLabels = { pending: '等待中', indexing: '索引中', indexed: '已索引', failed: '失败', deleting: '删除中' };

function showError(error) { const target = el('document-alert'); target.textContent = errorText(error); target.classList.remove('hidden'); }
function clearError() { el('document-alert').classList.add('hidden'); }

function render() {
  const body = el('document-table'); body.innerHTML = '';
  el('document-empty').classList.toggle('hidden', documents.length > 0);
  for (const doc of documents) {
    const id = value(doc, 'id', 'document_id');
    const status = value(doc, 'status') || 'pending';
    const tr = document.createElement('tr');
    tr.innerHTML = `<td><span class="cell-title">${ui.escape(value(doc, 'title', 'source_name') || '未命名文档')}</span><span class="cell-subtitle">${ui.escape(value(doc, 'source_name', 'error_message') || id)}</span></td><td>${ui.escape(value(doc, 'category') || 'general')}</td><td>${value(doc, 'source_type') === 'pdf' ? 'PDF' : '文本'}</td><td><span class="status-pill ${ui.escape(status)}">${statusLabels[status] || status}</span></td><td>${ui.escape(ui.formatTime(value(doc, 'updated_at', 'created_at')))}</td><td><div class="row-actions"><button data-action="view">查看</button><button data-action="edit">编辑</button><button data-action="reindex" ${['indexing','deleting'].includes(status) ? 'disabled' : ''}>重建</button><button data-action="delete" class="danger" ${status === 'deleting' ? 'disabled' : ''}>删除</button></div></td>`;
    tr.addEventListener('click', event => {
      const action = event.target.closest('button')?.dataset.action;
      if (action === 'view') viewDocument(id);
      if (action === 'edit') editDocument(doc);
      if (action === 'reindex') reindexDocument(id, event.target);
      if (action === 'delete') deleteDocument(id, value(doc, 'title', 'source_name'));
    });
    body.append(tr);
  }
  const categories = [...new Set(documents.map(doc => value(doc, 'category')).filter(Boolean))].sort();
  const select = el('document-category'); const current = select.value;
  select.innerHTML = '<option value="">全部分类</option>' + categories.map(item => `<option value="${ui.escape(item)}">${ui.escape(item)}</option>`).join('');
  select.value = current;
}

async function loadDocuments() {
  el('document-table').innerHTML = el('loading-row-template').innerHTML;
  const params = { q: el('document-search').value.trim(), category: el('document-category').value, status: el('document-status').value };
  Object.keys(params).forEach(key => { if (!params[key]) delete params[key]; });
  try {
    const payload = await api.documents(params); documents = listFrom(payload, ['documents', 'items', 'data']); clearError(); render();
  } catch (error) { documents = []; render(); showError(error); }
}

function chunksFrom(payload) { return listFrom(value(payload, 'chunks', 'document')?.chunks || payload?.chunks || [], ['chunks', 'items']); }

async function viewDocument(id) {
  ui.openDrawer({ eyebrow: '知识文档', title: '正在加载', html: '<div class="loading-line">正在读取文档…</div>' });
  try {
    const payload = await api.document(id); const doc = payload.document || payload; const chunks = chunksFrom(payload);
    const fields = `<div class="drawer-fields"><div><span>分类</span><strong>${ui.escape(value(doc,'category') || 'general')}</strong></div><div><span>状态</span><strong>${ui.escape(statusLabels[value(doc,'status')] || value(doc,'status') || '未知')}</strong></div><div><span>来源</span><strong>${ui.escape(value(doc,'source_name') || '文本录入')}</strong></div><div><span>片段数</span><strong>${chunks.length || value(doc,'chunk_count') || 0}</strong></div></div>`;
    const error = value(doc, 'error_message') ? `<div class="error-box">${ui.escape(doc.error_message)}</div>` : '';
    const preview = chunks.length ? chunks.map((chunk,index) => `<div class="chunk"><small>片段 ${value(chunk,'chunk_index') ?? index + 1}${value(chunk,'page_number') ? ` · 第 ${chunk.page_number} 页` : ''}</small>${ui.escape(value(chunk,'content','text') || '')}</div>`).join('') : '<div class="empty-state"><span>暂无可预览片段</span></div>';
    ui.openDrawer({ eyebrow: '知识文档', title: value(doc,'title','source_name') || '文档详情', html: `<div class="drawer-section"><h3>文档信息</h3>${fields}${error}</div><div class="drawer-section"><h3>片段预览</h3>${preview}</div>` });
  } catch (error) { ui.openDrawer({ eyebrow: '知识文档', title: '读取失败', html: `<div class="inline-alert error">${ui.escape(errorText(error))}</div>` }); }
}

async function addDocument() {
  const result = await ui.formDialog({
    title: '添加知识文档', submitText: '开始入库', enctype: true,
    fields: [
      { name:'source_type', label:'录入方式', type:'select', options:[['text','文本'],['pdf','PDF 文件']], value:'text' },
      { name:'title', label:'文档标题', required:true, maxlength:200 },
      { name:'category', label:'分类', value:'general', required:true, maxlength:80 },
      { name:'content', label:'文档内容', type:'textarea', requiredWhen:{ source_type:'text' }, placeholder:'输入团队规范、技术文档或 FAQ' },
      { name:'file', label:'选择 PDF', type:'file', accept:'.pdf,application/pdf', requiredWhen:{ source_type:'pdf' } },
    ],
  });
  if (!result) return;
  try {
    if (result.source_type === 'pdf') {
      const form = new FormData(); form.append('file', result.file); form.append('title', result.title); form.append('category', result.category); await api.createPdfDocument(form);
    } else await api.createTextDocument({ title: result.title, category: result.category, text: result.content, content: result.content });
    clearError(); await loadDocuments();
  } catch (error) { showError(error); }
}

async function editDocument(doc) {
  const id = value(doc,'id','document_id'); let detail = doc;
  try { const payload = await api.document(id); detail = payload.document || payload; } catch { /* metadata edit remains available */ }
  const canEditText = value(detail,'source_type') !== 'pdf';
  const fields = [
    { name:'title', label:'文档标题', value:value(detail,'title','source_name') || '', required:true },
    { name:'category', label:'分类', value:value(detail,'category') || 'general', required:true },
  ];
  if (canEditText) fields.push({ name:'content', label:'文档内容', type:'textarea', value:value(detail,'content','text') || '' });
  const result = await ui.formDialog({ title:'编辑文档', submitText:'保存并更新', fields });
  if (!result) return;
  try { await api.updateDocument(id, { ...result, text: result.content }); clearError(); await loadDocuments(); }
  catch (error) { showError(error); }
}

async function reindexDocument(id, button) {
  ui.busy(button,true);
  try { await api.reindexDocument(id); clearError(); await loadDocuments(); }
  catch (error) { showError(error); }
  finally { ui.busy(button,false); }
}

async function deleteDocument(id, title) {
  if (!await ui.confirmDialog('删除文档', `确定删除“${title || '该文档'}”及其全部索引片段吗？`, '删除')) return;
  try { await api.deleteDocument(id); clearError(); await loadDocuments(); }
  catch (error) { showError(error); }
}

export async function initDocuments(sharedUi) {
  ui = sharedUi;
  el('add-document').addEventListener('click', addDocument);
  el('refresh-documents').addEventListener('click', loadDocuments);
  el('document-search').addEventListener('input', () => { clearTimeout(searchTimer); searchTimer = setTimeout(loadDocuments, 300); });
  el('document-category').addEventListener('change', loadDocuments);
  el('document-status').addEventListener('change', loadDocuments);
  ui.on('documents:refresh', loadDocuments);
  await loadDocuments();
}
