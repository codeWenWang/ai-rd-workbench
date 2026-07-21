const assert = require('node:assert/strict');
const path = require('node:path');
const { chromium } = require('playwright');


(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('http://127.0.0.1:8000/?e2e=20260714', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('#conversation-list');
  assert.equal(await page.locator('a[href="/docs"]').count(), 0);

  const rootPath = path.resolve(__dirname, '..', 'backend', 'tests', 'fixtures', 'sample_project');
  const projects = await page.evaluate(() => fetch('/api/projects').then(response => response.json()));
  let project = projects.items.find(item => item.root_path.toLowerCase() === rootPath.toLowerCase());
  if (!project) {
    project = await page.evaluate(async payload => {
      const response = await fetch('/api/projects', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
      });
      return response.json();
    }, { name: '端到端示例项目', root_path: rootPath });
  }

  await page.evaluate(id => localStorage.setItem('active_project_id', id), project.id);
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.click('[data-view="overview"]');
  await page.click('#scan-project');
  await page.waitForFunction(() => !document.querySelector('#scan-project').disabled);
  await page.waitForFunction(() => document.querySelector('#project-files').textContent.includes('main.py'));

  for (const view of ['architecture', 'flow', 'sequence', 'project-api']) {
    await page.click(`[data-view="${view}"]`);
    await page.click(`#view-${view} .generate-artifact`);
    await page.waitForFunction(id => {
      const text = document.querySelector(`#view-${id} .artifact-content`).textContent;
      return text && !text.includes('尚未生成');
    }, view);
  }

  await page.click('[data-view="architecture"]');
  await page.waitForSelector('#view-architecture.active .artifact-content');
  await page.screenshot({ path: path.resolve(__dirname, 'e2e-architecture.png'), fullPage: true });

  await page.locator('#settings-menu summary').click();
  await page.click('#model-settings');
  assert.equal(await page.locator('#detail-drawer.open').count(), 1);
  await page.click('#close-drawer');
  await page.click('#diagnostics-toggle');
  assert.equal(await page.locator('#view-diagnostics.active').count(), 1);
  await page.screenshot({ path: path.resolve(__dirname, 'e2e-desktop.png'), fullPage: true });

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('http://127.0.0.1:8000/?e2e=mobile', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('#chat-input');
  const composer = await page.locator('.composer-shell').boundingBox();
  assert.ok(composer && composer.y + composer.height <= 844, 'composer must remain inside mobile viewport');
  await page.screenshot({ path: path.resolve(__dirname, 'e2e-mobile.png'), fullPage: true });

  assert.deepEqual(errors, []);
  await browser.close();
  console.log('browser smoke test passed');
})().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
