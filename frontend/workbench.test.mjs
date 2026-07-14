import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';


test('sidebar owns navigation, conversations, theme, and API access', async () => {
  const html = await readFile(new URL('./index.html', import.meta.url), 'utf8');
  const start = html.indexOf('<aside class="sidebar"');
  const end = html.indexOf('</aside>', start);
  const sidebar = html.slice(start, end);

  assert.match(sidebar, /id="sidebar-collapse"/);
  assert.match(sidebar, /id="new-conversation"/);
  assert.match(sidebar, /id="conversation-list"/);
  assert.match(sidebar, /id="theme-toggle"/);
  assert.match(sidebar, /href="\/docs"/);
  assert.doesNotMatch(html, /class="conversation-panel"/);
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


test('API documentation enables root page scrolling', async () => {
  const html = await readFile(new URL('./docs.html', import.meta.url), 'utf8');
  const css = await readFile(new URL('./css/style.css', import.meta.url), 'utf8');

  assert.match(html, /<html[^>]*class="docs-root"/);
  assert.match(css, /html\.docs-root[^}]*overflow-y:\s*auto/s);
});
