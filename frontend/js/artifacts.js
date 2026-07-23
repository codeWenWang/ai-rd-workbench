import { api, errorText, listFrom } from './api.js?v=20260723.2';
import { activeProjectId, projectFileMetadata } from './projects.js?v=20260723.2';
import { sourceSnippet } from './source-snippet.js?v=20260722.3';

let ui;
const latest = new Map();
let projectRoutes = [];

function inferredEvidenceLayer(moduleName) {
  const value = String(moduleName || '').toLowerCase();
  if (/(ui|frontend|web|client)/.test(value)) return '客户端层';
  if (/(persistence|database|jdbc|mysql|postgres|repository|storage|blob|s3)/.test(value)) return '数据层';
  return '业务服务层';
}

export function parseEvidenceGroups(content = '') {
  const layers = new Map();
  const add = (layerName, moduleName, path) => {
    if (!path) return;
    if (!layers.has(layerName)) layers.set(layerName, new Map());
    const modules = layers.get(layerName);
    if (!modules.has(moduleName)) modules.set(moduleName, new Set());
    modules.get(moduleName).add(path);
  };
  for (const line of String(content).split('\n')) {
    const match = line.match(/^\s*%%\s*evidence:\s*(.+?)\s*$/);
    if (!match) continue;
    const parts = match[1].split(/\s+\/\s+/);
    if (parts.length >= 3) {
      add(parts[0], parts[1], parts.slice(2).join(' / '));
    } else {
      const path = match[1].trim();
      const moduleName = path.split('/')[0] || '项目源码';
      add(inferredEvidenceLayer(moduleName), moduleName, path);
    }
  }
  if (!layers.size) {
    const paths = [...new Set((String(content).match(/[A-Za-z0-9_./-]+\.(?:py|java|js|ts|tsx|jsx|vue|go|cs)(?::\d+)?/g) || []))];
    for (const path of paths) {
      const moduleName = path.split('/')[0] || '项目源码';
      add(inferredEvidenceLayer(moduleName), moduleName, path);
    }
  }
  return [...layers].map(([name, modules]) => ({
    name,
    modules: [...modules].map(([moduleName, paths]) => ({ name: moduleName, paths: [...paths] })),
  }));
}

function evidenceNode(content) {
  const groups = parseEvidenceGroups(content);
  if (!groups.length) return null;
  const evidence = document.createElement('section');
  evidence.className = 'artifact-evidence';
  evidence.innerHTML = '<h2>源码证据</h2><p>证据按架构层和模块归类，点击文件可查看扫描时保存的源码。</p>';
  const body = document.createElement('div');
  body.className = 'evidence-groups';
  for (const group of groups) {
    const layer = document.createElement('section');
    layer.className = 'evidence-layer';
    const heading = document.createElement('h3');
    heading.textContent = group.name;
    layer.append(heading);
    for (const item of group.modules) {
      const module = document.createElement('div');
      module.className = 'evidence-module';
      const moduleHeading = document.createElement('h4');
      moduleHeading.textContent = item.name;
      const links = document.createElement('div');
      links.className = 'evidence-links';
      for (const path of item.paths) {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'evidence-link';
        button.textContent = path;
        button.addEventListener('click', () => showEvidence(path));
        links.append(button);
      }
      module.append(moduleHeading, links);
      layer.append(module);
    }
    body.append(layer);
  }
  evidence.append(body);
  return evidence;
}

export function mermaidThemeConfig(theme) {
  if (theme !== 'dark') return { startOnLoad: false, theme: 'default' };
  return {
    startOnLoad: false,
    theme: 'base',
    themeVariables: {
      darkMode: true,
      background: '#2f2f2f',
      primaryColor: '#3a3a3a',
      primaryTextColor: '#f4f4f5',
      primaryBorderColor: '#a1a1aa',
      secondaryColor: '#183d34',
      secondaryTextColor: '#ecfdf5',
      secondaryBorderColor: '#54c58b',
      tertiaryColor: '#463817',
      tertiaryTextColor: '#fff7cc',
      tertiaryBorderColor: '#e5b94f',
      lineColor: '#d4d4d8',
      textColor: '#f4f4f5',
      mainBkg: '#3a3a3a',
      nodeBorder: '#a1a1aa',
      clusterBkg: '#262626',
      clusterBorder: '#71717a',
      edgeLabelBackground: '#2f2f2f',
      actorBkg: '#3a3a3a',
      actorBorder: '#a1a1aa',
      actorTextColor: '#f4f4f5',
      actorLineColor: '#a1a1aa',
      signalColor: '#e4e4e7',
      signalTextColor: '#f4f4f5',
      labelBoxBkgColor: '#2f2f2f',
      labelBoxBorderColor: '#71717a',
      labelTextColor: '#f4f4f5',
      loopTextColor: '#f4f4f5',
      noteBkgColor: '#4a431f',
      noteBorderColor: '#e5b94f',
      noteTextColor: '#fff7cc',
      activationBkgColor: '#183d34',
      activationBorderColor: '#54c58b',
    },
  };
}

function contentNode(view, artifact) {
  const container = view.querySelector('.artifact-content');
  container.className = 'artifact-content';
  container.innerHTML = '';
  if (!artifact) {
    container.className = 'artifact-content empty-state';
    container.innerHTML = '<strong>尚未生成</strong><span>先扫描项目，再生成当前内容。</span>';
    return;
  }
  const artifactNumbers = {
    architecture: 'ARCH-01', flow: 'FLOW-01', sequence: 'SEQ-01', api_docs: 'API-01',
  };
  const drawingDate = artifact.updated_at || artifact.created_at;
  const formattedDate = drawingDate
    ? new Date(drawingDate).toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' })
    : '未知';
  const meta = document.createElement('div');
  meta.className = 'artifact-meta';
  meta.textContent = [
    artifact.status === 'stale' ? '源码已变化，需要重新生成' : '当前版本',
    '图号 ' + (artifactNumbers[view.dataset.artifactType] || 'DOC-01'),
    '版本 ' + (artifact.source_revision?.slice(0, 10) || '未知'),
    '绘制日期 ' + formattedDate,
  ].join(' · ');
  container.append(meta);
  if (artifact.format === 'mermaid') {
    if (view.dataset.artifactType === 'sequence' && projectRoutes.length) {
      const scenarios = document.createElement('nav');
      scenarios.className = 'sequence-scenarios';
      scenarios.setAttribute('aria-label', '时序图场景');
      const overall = document.createElement('button');
      overall.type = 'button';
      overall.className = 'active';
      overall.textContent = '整体时序';
      scenarios.append(overall);
      for (const route of projectRoutes.slice(0, 12)) {
        const button = document.createElement('button');
        button.type = 'button';
        button.textContent = `${route.method} ${route.path}`;
        button.addEventListener('click', () => {
          scenarios.querySelectorAll('button').forEach(item => item.classList.toggle('active', item === button));
          renderDiagram(diagram, featureSequence(route));
        });
        scenarios.append(button);
      }
      overall.addEventListener('click', () => {
        scenarios.querySelectorAll('button').forEach(item => item.classList.toggle('active', item === overall));
        renderDiagram(diagram, artifact.content);
      });
      container.append(scenarios);
    }
    const diagram = document.createElement('pre');
    diagram.className = `mermaid artifact-diagram artifact-${view.dataset.artifactType}`;
    diagram.textContent = artifact.content;
    container.append(diagram);
    renderDiagram(diagram, artifact.content);
    const evidence = evidenceNode(artifact.content);
    if (evidence) container.append(evidence);
  } else {
    const markdown = document.createElement('article');
    markdown.className = 'artifact-markdown';
    markdown.innerHTML = ui.renderMarkdown(artifact.content);
    markdown.querySelectorAll('a.source-link').forEach(link => {
      link.addEventListener('click', event => {
        event.preventDefault();
        const location = decodeURIComponent(link.getAttribute('href').replace(/^source:\/\//, ''));
        showEvidence(location, { endpoint: true });
      });
    });
    container.append(markdown);
  }
}

function renderAll() {
  document.querySelectorAll('.artifact-view').forEach(view => {
    contentNode(view, latest.get(view.dataset.artifactType));
  });
}

async function loadArtifacts() {
  latest.clear();
  projectRoutes = [];
  const projectId = activeProjectId();
  if (!projectId) return renderAll();
  try {
    const [artifactPayload, routePayload] = await Promise.all([
      api.artifacts(projectId), api.projectRoutes(projectId),
    ]);
    projectRoutes = listFrom(routePayload);
    for (const item of listFrom(artifactPayload)) {
      if (!latest.has(item.artifact_type)) latest.set(item.artifact_type, item);
    }
  } catch { /* empty project */ }
  renderAll();
}

async function generate(view) {
  const projectId = activeProjectId();
  const alert = view.querySelector('.artifact-alert');
  alert.classList.add('hidden');
  if (!projectId) {
    alert.textContent = '请先连接并扫描项目'; alert.classList.remove('hidden'); return;
  }
  const button = view.querySelector('.generate-artifact');
  ui.busy(button, true);
  try {
    const artifact = await api.generateArtifact(projectId, view.dataset.artifactType);
    latest.set(view.dataset.artifactType, artifact);
    contentNode(view, artifact);
  } catch (error) {
    alert.textContent = errorText(error); alert.classList.remove('hidden');
  } finally { ui.busy(button, false); }
}

export async function initArtifacts(sharedUi) {
  ui = sharedUi;
  document.querySelectorAll('.artifact-view').forEach(view => {
    view.querySelector('.generate-artifact').addEventListener('click', () => generate(view));
  });
  ui.on('project:changed', loadArtifacts);
  ui.on('project:scanned', loadArtifacts);
  ui.on('theme:changed', renderAll);
  await loadArtifacts();
}

function renderDiagram(diagram, content) {
  diagram.removeAttribute('data-processed');
  diagram.classList.remove('artifact-code');
  diagram.textContent = content;
  if (!globalThis.mermaid) { diagram.classList.add('artifact-code'); return; }
  globalThis.mermaid.initialize(mermaidThemeConfig(document.documentElement.dataset.theme));
  globalThis.mermaid.run({ nodes: [diagram] }).catch(() => { diagram.classList.add('artifact-code'); });
}

export function featureSequence(route) {
  const method = String(route.method || 'GET').replace(/[^A-Z]/g, '') || 'GET';
  const path = String(route.path || '/').replaceAll('\n', ' ').trim();
  const handler = String(route.handler || '业务处理器').replaceAll('\n', ' ').trim().split('.')[0] || '业务处理器';
  const moduleName = String(route.module || '应用').replaceAll('\n', ' ').trim();
  const params = [...path.matchAll(/\{([^}]+)\}/g)].map(match => match[1]).join(',') || '无';
  const source = String(route.source_path || '').replaceAll('\n', ' ').trim();
  const line = Number(route.line_number || 1);
  return [
    'sequenceDiagram',
    '    actor U as 外部用户',
    `    participant G as 前端 / 网关【${moduleName}】`,
    `    participant B as 业务服务【${handler}】`,
    `    U->>G: ${method} ${path}(${params}) : 发起请求`,
    '    activate G',
    `    G->>B: ${handler}(${params}) : 处理请求`,
    '    activate B',
    '    alt 正常流程',
    '        B-->>G: 业务结果(状态) : 处理成功',
    '        G-->>U: HTTP 响应(状态) : 返回成功',
    '    else 关键异常',
    '        B-->>G: 错误(状态) : 校验或业务失败',
    '        G-->>U: HTTP 响应(状态) : 返回错误',
    '    end',
    '    deactivate B',
    '    deactivate G',
    `    %% evidence: 业务服务层 / ${handler} / ${source}:${line}`,
  ].join('\n');
}

async function showEvidence(location, { endpoint = false } = {}) {
  const file = projectFileMetadata(location);
  if (!file) {
    ui.openDrawer({ eyebrow: '源码证据', title: location, html: '<div class="source-text">当前扫描结果中未找到该文件，请重新扫描项目。</div>' });
    return;
  }
  try {
    const detail = await api.projectFile(activeProjectId(), file.id);
    const snippet = sourceSnippet(detail.content || file.excerpt || '', location, { endpoint });
    ui.openDrawer({
      eyebrow: endpoint ? '接口关键源码' : '源码证据',
      title: location,
      html: `<div class="source-text source-code">${ui.escape(snippet)}</div>`,
      wide: true,
    });
  } catch {
    ui.openDrawer({ eyebrow: '源码证据', title: location, html: `<div class="source-text source-code">${ui.escape(file.excerpt || '')}</div>`, wide: true });
  }
}
