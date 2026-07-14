import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';


test('sidebar owns project workspace, conversations, theme, and bottom diagnostics', async () => {
  const html = await readFile(new URL('./index.html', import.meta.url), 'utf8');
  const start = html.indexOf('<aside class="sidebar"');
  const end = html.indexOf('</aside>', start);
  const sidebar = html.slice(start, end);

  assert.match(sidebar, /id="sidebar-collapse"/);
  assert.match(sidebar, /id="new-conversation"/);
  assert.match(sidebar, /id="project-selector"/);
  assert.match(sidebar, /id="add-project"/);
  assert.match(sidebar, /class="analysis-nav"/);
  assert.match(sidebar, /data-view="architecture"/);
  assert.match(sidebar, /data-view="flow"/);
  assert.match(sidebar, /data-view="sequence"/);
  assert.match(sidebar, /data-view="project-api"/);
  assert.match(sidebar, /id="conversation-list"/);
  assert.match(sidebar, /id="theme-toggle"/);
  assert.match(sidebar, /id="diagnostics-toggle"/);
  assert.doesNotMatch(sidebar, /href="\/docs"/);
  assert.doesNotMatch(html, /class="conversation-panel"/);
  assert.match(html, /id="remove-project"/);
});


test('stylesheet defines collapsed sidebar, dark theme, and safe composer', async () => {
  const css = await readFile(new URL('./css/style.css', import.meta.url), 'utf8');

  assert.match(css, /html\[data-theme="dark"\]/);
  assert.match(css, /\.app-shell\.sidebar-collapsed/);
  assert.match(css, /\.composer-shell/);
  assert.match(css, /padding-bottom:\s*max\(/);
  assert.match(css, /\.composer-shell\s*\{[^}]*grid-row:\s*4/s);
  assert.doesNotMatch(css, /\.alert-stack:empty\s*\{[^}]*display:\s*none/s);
});


test('memory candidates only expose pending suggestions', async () => {
  const module = await import(`./js/memories.js?test=${Date.now()}`);

  assert.equal(typeof module.pendingCandidates, 'function');
  assert.deepEqual(
    module.pendingCandidates([
      { id: 'pending', status: 'pending' },
      { id: 'rejected', status: 'rejected' },
      { id: 'confirmed', status: 'confirmed' },
    ]).map(item => item.id),
    ['pending'],
  );
});


test('selecting a recent conversation requests the chat view', async () => {
  const appSource = await readFile(new URL('./js/app.js', import.meta.url), 'utf8');
  const chatSource = await readFile(new URL('./js/chat.js', import.meta.url), 'utf8');

  assert.match(appSource, /showView:\s*switchView/);
  assert.match(chatSource, /async function selectConversation[\s\S]*?ui\.showView\('chat'\)/);
});


test('chat header exposes model selection and comparison mode', async () => {
  const html = await readFile(new URL('./index.html', import.meta.url), 'utf8');

  assert.match(html, /id="chat-model"/);
  assert.match(html, /id="compare-models"/);
  assert.match(html, /id="model-settings"/);
  assert.match(html, /id="comparison-results"/);
});
