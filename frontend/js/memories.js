import { api, errorText, listFrom } from './api.js?v=20260723.2';

let ui;
let memories = [];
let candidates = [];
const el = id => document.getElementById(id);
const value = (obj, ...keys) => keys.map(key => obj?.[key]).find(item => item !== undefined && item !== null);
const kindLabels = { preference:'偏好', fact:'事实', decision:'决策', context:'背景' };

export function pendingCandidates(items) {
  return items.filter(item => (value(item, 'status') || 'pending') === 'pending');
}

function idOf(item) { return value(item,'id','memory_id','candidate_id'); }
function titleOf(item) { return value(item,'title','proposed_title') || '未命名记忆'; }
function contentOf(item) { return value(item,'content','proposed_content') || ''; }
function showError(error) { const target=el('memory-alert'); target.textContent=errorText(error); target.classList.remove('hidden'); }
function clearError() { el('memory-alert').classList.add('hidden'); }

function renderConfirmed() {
  const container=el('confirmed-memories'); container.innerHTML=''; el('confirmed-count').textContent=memories.length;
  if (!memories.length) { container.innerHTML='<div class="empty-state"><strong>还没有已确认记忆</strong><span>手动添加，或从待确认建议中选择。</span></div>'; return; }
  for (const memory of memories) {
    const item=document.createElement('article'); item.className='list-item';
    item.innerHTML=`<div><h3>${ui.escape(titleOf(memory))}</h3><p>${ui.escape(contentOf(memory))}</p><div class="item-meta"><span class="kind-tag">${kindLabels[value(memory,'kind')] || ui.escape(value(memory,'kind') || '背景')}</span><span>${ui.escape(ui.formatTime(value(memory,'updated_at','created_at')))}</span></div></div><div class="item-actions"><button class="button" data-action="edit">编辑</button><button class="button danger" data-action="delete">删除</button></div>`;
    item.addEventListener('click', event => { const action=event.target.closest('button')?.dataset.action; if(action==='edit') editMemory(memory); if(action==='delete') deleteMemory(memory); });
    container.append(item);
  }
}

function renderCandidates() {
  const container=el('candidate-memories'); container.innerHTML=''; el('candidate-count').textContent=candidates.length;
  el('pending-count').textContent=candidates.length; el('pending-count').classList.toggle('hidden',!candidates.length);
  if (!candidates.length) { container.innerHTML='<div class="empty-state"><strong>没有待确认建议</strong><span>对话完成后，新建议会显示在这里。</span></div>'; return; }
  for (const candidate of candidates) {
    const item=document.createElement('article'); item.className='list-item';
    item.innerHTML=`<div><h3>${ui.escape(titleOf(candidate))}</h3><p>${ui.escape(contentOf(candidate))}</p><div class="item-meta"><span class="kind-tag">${kindLabels[value(candidate,'kind')] || '背景'}</span><span>${ui.escape(ui.formatTime(value(candidate,'created_at')))}</span></div></div><div class="item-actions"><button class="button primary" data-action="confirm">编辑并确认</button><button class="button danger" data-action="reject">拒绝</button></div>`;
    item.addEventListener('click', event => { const action=event.target.closest('button')?.dataset.action; if(action==='confirm') confirmCandidate(candidate); if(action==='reject') rejectCandidate(candidate); });
    container.append(item);
  }
}

async function loadMemories() {
  try {
    const [memoryResult,candidateResult]=await Promise.allSettled([api.memories(),api.candidates()]);
    if(memoryResult.status==='fulfilled') memories=listFrom(memoryResult.value,['memories','items','data']); else throw memoryResult.reason;
    candidates=candidateResult.status==='fulfilled' ? pendingCandidates(listFrom(candidateResult.value,['candidates','items','data'])) : [];
    if(candidateResult.status==='rejected' && ![404,405].includes(candidateResult.reason?.status)) throw candidateResult.reason;
    clearError(); renderConfirmed(); renderCandidates();
  } catch(error) { showError(error); renderConfirmed(); renderCandidates(); }
}

const memoryFields = item => [
  {name:'title',label:'记忆标题',value:item ? titleOf(item) : '',required:true,maxlength:200},
  {name:'kind',label:'类型',type:'select',value:value(item,'kind') || 'context',options:Object.entries(kindLabels)},
  {name:'content',label:'记忆内容',type:'textarea',value:item ? contentOf(item) : '',required:true},
];

async function addMemory() {
  const result=await ui.formDialog({title:'添加个人记忆',submitText:'确认添加',enctype:true,fields:[
    {name:'source_type',label:'录入方式',type:'select',value:'text',options:[['text','文本'],['pdf','PDF 文件']]},
    {name:'title',label:'记忆标题',required:true,maxlength:200},
    {name:'kind',label:'类型',type:'select',value:'context',options:Object.entries(kindLabels)},
    {name:'content',label:'记忆内容',type:'textarea',requiredWhen:{source_type:'text'}},
    {name:'file',label:'选择 PDF',type:'file',accept:'.pdf,application/pdf',requiredWhen:{source_type:'pdf'}},
  ]});
  if(!result)return;
  try {
    if(result.source_type==='pdf') { const form=new FormData(); form.append('file',result.file); form.append('title',result.title); form.append('kind',result.kind); await api.createMemoryPdf(form); }
    else await api.createMemory({title:result.title,kind:result.kind,content:result.content,text:result.content});
    clearError(); await loadMemories();
  } catch(error){showError(error);}
}

async function editMemory(memory) {
  const result=await ui.formDialog({title:'编辑记忆',submitText:'保存',fields:memoryFields(memory)}); if(!result)return;
  try{await api.updateMemory(idOf(memory),result);clearError();await loadMemories();}catch(error){showError(error);}
}

async function deleteMemory(memory) {
  if(!await ui.confirmDialog('删除记忆',`确定删除“${titleOf(memory)}”吗？删除后将不再参与回答。`,'删除'))return;
  try{await api.deleteMemory(idOf(memory));clearError();await loadMemories();}catch(error){showError(error);}
}

async function confirmCandidate(candidate) {
  const result=await ui.formDialog({title:'确认记忆建议',submitText:'确认并保存',fields:memoryFields(candidate)});if(!result)return;
  try{await api.confirmCandidate(idOf(candidate),{...result,proposed_title:result.title,proposed_content:result.content});clearError();await loadMemories();}catch(error){showError(error);}
}

async function rejectCandidate(candidate) {
  if(!await ui.confirmDialog('拒绝记忆建议',`确定拒绝“${titleOf(candidate)}”吗？`,'拒绝'))return;
  try{
    await api.rejectCandidate(idOf(candidate));
    candidates=candidates.filter(item=>idOf(item)!==idOf(candidate));
    clearError();renderCandidates();
    await loadMemories();
  }catch(error){showError(error);}
}

function switchTab(tab) {
  document.querySelectorAll('[data-memory-tab]').forEach(button=>{const active=button.dataset.memoryTab===tab;button.classList.toggle('active',active);button.setAttribute('aria-selected',active);});
  el('confirmed-memories').classList.toggle('hidden',tab!=='confirmed');el('candidate-memories').classList.toggle('hidden',tab!=='candidates');
}

export async function initMemories(sharedUi) {
  ui=sharedUi;el('add-memory').addEventListener('click',addMemory);
  document.querySelectorAll('[data-memory-tab]').forEach(button=>button.addEventListener('click',()=>switchTab(button.dataset.memoryTab)));
  ui.on('memories:refresh',loadMemories);await loadMemories();
}
