import { api, errorText } from './api.js?v=20260721.7';

let ui;
const el=id=>document.getElementById(id);
const value=(obj,...keys)=>keys.map(key=>obj?.[key]).find(item=>item!==undefined&&item!==null);

function statusValue(data){return value(data,'status','state','ok','ready','live');}
function isGood(data){const status=statusValue(data);return status===true||['ok','healthy','ready','live','configured','connected','consistent','completed'].includes(String(status).toLowerCase());}
function label(data){const status=statusValue(data);if(status===true)return '正常';if(status===false)return '异常';return status||'未知';}
function setHealth(id,data){const target=el(id);target.textContent=label(data);target.className=isGood(data)?'good':'bad';}

function normalizeComponents(payload){
  const raw=value(payload,'components','services')||{};
  if(Array.isArray(raw))return raw;
  return Object.entries(raw).map(([name,data])=>({name,...(typeof data==='object'?data:{status:data})}));
}

function renderDiagnostics(payload={}){
  const components=normalizeComponents(payload);
  const componentGrid=el('component-grid');
  componentGrid.innerHTML=components.length?components.map(component=>`<article class="component"><header><strong>${ui.escape(value(component,'display_name','name')||'组件')}</strong><span class="status-pill ${isGood(component)?'indexed':'failed'}">${ui.escape(label(component))}</span></header><p>${ui.escape(value(component,'message','detail','model','provider')||'未提供附加信息')}</p></article>`).join(''):'<div class="empty-state"><span>诊断接口未返回组件明细</span></div>';

  const vector=value(payload,'vector','vector_index','pinecone','index')||{};
  const namespaces=value(vector,'namespaces','namespace_counts')||value(payload,'namespaces')||{};
  const namespaceEntries=Array.isArray(namespaces)?namespaces.map(item=>[value(item,'name','namespace'),value(item,'count','vector_count')]):Object.entries(namespaces).map(([name,data])=>[name,typeof data==='object'?value(data,'count','vector_count'):data]);
  const stats=[['索引名称',value(vector,'name','index_name')||'未配置'],['向量维度',value(vector,'dimension','dimensions')||'未知'],...namespaceEntries.map(([name,count])=>[`${name||'默认'} namespace`,count??0])];
  el('vector-stats').innerHTML=stats.map(([name,count])=>`<div class="stat"><span>${ui.escape(name)}</span><strong>${ui.escape(String(count))}</strong></div>`).join('');

  const consistency=value(payload,'consistency','consistency_summary')||{};
  const migration=value(payload,'migration','migration_status')||{};
  const rows=[
    ['SQLite 记录',value(consistency,'sqlite_count','database_count','local_count')??'未知'],
    ['Pinecone 向量',value(consistency,'pinecone_count','vector_count','remote_count')??'未知'],
    ['缺失向量',value(consistency,'missing_vectors','missing_count')??0],
    ['孤立向量',value(consistency,'orphan_vectors','orphan_count')??0],
    ['迁移状态',label(migration)],
    ['最近迁移',ui.formatTime(value(migration,'completed_at','updated_at','last_run_at'))],
  ];
  el('migration-status').innerHTML=rows.map(([name,data])=>`<div class="detail-row"><span>${ui.escape(name)}</span><strong>${ui.escape(String(data))}</strong></div>`).join('');
  const consistencyGood=value(consistency,'consistent','ok');setHealth('consistency-state',{status:consistencyGood===undefined?(Number(value(consistency,'missing_vectors','missing_count')||0)===0&&Number(value(consistency,'orphan_vectors','orphan_count')||0)===0):consistencyGood});
}

async function refreshDiagnostics(){
  const button=el('refresh-diagnostics');ui.busy(button,true);el('diagnostics-alert').classList.add('hidden');
  const [live,ready,details]=await Promise.allSettled([api.live(),api.ready(),api.diagnostics()]);
  setHealth('live-state',live.status==='fulfilled'?live.value:{status:false});setHealth('ready-state',ready.status==='fulfilled'?ready.value:{status:false});
  const dot=el('global-status-dot');const global=el('global-status');
  if(live.status==='fulfilled'){dot.className='status-dot good';global.textContent=ready.status==='fulfilled'?'本地服务已就绪':'服务已启动，部分组件异常';}else{dot.className='status-dot bad';global.textContent='本地服务不可用';}
  if(details.status==='fulfilled')renderDiagnostics(details.value);
  else{renderDiagnostics();const target=el('diagnostics-alert');target.textContent=errorText(details.reason);target.classList.remove('hidden');}
  el('diagnostics-updated').textContent=`最近检查：${new Intl.DateTimeFormat('zh-CN',{hour:'2-digit',minute:'2-digit',second:'2-digit'}).format(new Date())}`;ui.busy(button,false);
}

export async function initDiagnostics(sharedUi){ui=sharedUi;el('refresh-diagnostics').addEventListener('click',refreshDiagnostics);await refreshDiagnostics();}
