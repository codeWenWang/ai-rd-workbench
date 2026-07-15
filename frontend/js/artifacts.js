import { api, errorText, listFrom } from './api.js?v=20260714.1';
import { activeProjectId } from './projects.js?v=20260715.2';

let ui;
const latest = new Map();

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
    const diagram = document.createElement('pre');
    diagram.className = `mermaid artifact-diagram artifact-${view.dataset.artifactType}`;
    diagram.textContent = artifact.content;
    container.append(diagram);
    if (globalThis.mermaid) {
      globalThis.mermaid.initialize(mermaidThemeConfig(document.documentElement.dataset.theme));
      globalThis.mermaid.run({ nodes: [diagram] }).catch(() => { diagram.classList.add('artifact-code'); });
    } else diagram.classList.add('artifact-code');
  } else {
    const markdown = document.createElement('pre');
    markdown.className = 'artifact-markdown';
    markdown.textContent = artifact.content;
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
  const projectId = activeProjectId();
  if (!projectId) return renderAll();
  try {
    for (const item of listFrom(await api.artifacts(projectId))) {
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
