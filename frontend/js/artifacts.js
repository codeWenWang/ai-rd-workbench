import { api, errorText, listFrom } from './api.js?v=20260721.7';
import { activeProjectId, projectFileMetadata } from './projects.js?v=20260721.7';

let ui;
const latest = new Map();
let projectRoutes = [];

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
  const meta = document.createElement('div');
  meta.className = 'artifact-meta';
  meta.textContent = `${artifact.status === 'stale' ? '源码已变化，需要重新生成' : '当前版本'} · ${artifact.source_revision?.slice(0, 10) || ''}`;
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
    const evidencePaths = [...new Set((artifact.content.match(/[A-Za-z0-9_./-]+\.(?:py|java|js|ts|tsx|jsx|vue|go|cs)(?::\d+)?/g) || []))];
    if (evidencePaths.length) {
      const evidence = document.createElement('section');
      evidence.className = 'artifact-evidence';
      evidence.innerHTML = '<h2>源码证据</h2><p>点击证据可查看扫描时保存的源码片段。</p>';
      const links = document.createElement('div');
      for (const path of evidencePaths.slice(0, 12)) {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'evidence-link';
        button.textContent = path;
        button.addEventListener('click', () => showEvidence(path));
        links.append(button);
      }
      evidence.append(links);
      container.append(evidence);
    }
  } else {
    const markdown = document.createElement('article');
    markdown.className = 'artifact-markdown';
    markdown.innerHTML = ui.renderMarkdown(artifact.content);
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

function featureSequence(route) {
  const method = String(route.method || 'GET').replace(/[^A-Z]/g, '') || 'GET';
  const path = String(route.path || '/').replaceAll(':', '：').replaceAll('\n', ' ');
  const handler = String(route.handler || '处理器').replaceAll(':', '：').replaceAll('\n', ' ');
  const source = String(route.source_path || '').replaceAll(':', '：').replaceAll('\n', ' ');
  return [
    'sequenceDiagram',
    '    participant U as 客户端',
    '    participant A as 应用 API',
    `    participant H as ${handler}`,
    `    U->>A: ${method} ${path}`,
    '    A->>H: 调用处理器',
    '    H-->>A: 返回业务结果',
    '    A-->>U: HTTP 响应',
    `    Note over A,H: 源码证据 ${source}:${Number(route.line_number || 1)}`,
  ].join('\n');
}

async function showEvidence(location) {
  const file = projectFileMetadata(location);
  if (!file) {
    ui.openDrawer({ eyebrow: '源码证据', title: location, html: '<div class="source-text">当前扫描结果中未找到该文件，请重新扫描项目。</div>' });
    return;
  }
  try {
    const detail = await api.projectFile(activeProjectId(), file.id);
    const snippet = sourceSnippet(detail.content || file.excerpt || '', location);
    ui.openDrawer({
      eyebrow: '源码证据',
      title: location,
      html: `<div class="source-text source-code">${ui.escape(snippet)}</div>`,
    });
  } catch {
    ui.openDrawer({ eyebrow: '源码证据', title: location, html: `<div class="source-text source-code">${ui.escape(file.excerpt || '')}</div>` });
  }
}

function sourceSnippet(content, location) {
  const lines = String(content || '').split('\n');
  const match = String(location || '').match(/:(\d+)$/);
  if (!match) return lines.slice(0, 80).map((line, index) => `${String(index + 1).padStart(4)}  ${line}`).join('\n');
  const lineNumber = Math.max(1, Number(match[1]));
  const start = Math.max(0, lineNumber - 7);
  const end = Math.min(lines.length, lineNumber + 6);
  return lines.slice(start, end).map((line, index) => {
    const current = start + index + 1;
    return `${current === lineNumber ? '>' : ' '} ${String(current).padStart(4)}  ${line}`;
  }).join('\n');
}
