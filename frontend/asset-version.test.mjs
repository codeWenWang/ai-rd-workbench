import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';


test('frontend entry point cache-busts stylesheet and module assets', async () => {
  const html = await readFile(new URL('./index.html', import.meta.url), 'utf8');

  assert.match(html, /href="css\/style\.css\?v=[^"]+"/);
  assert.match(html, /src="js\/app\.js\?v=[^"]+"/);
});


test('relative JavaScript imports use the same cache-busting strategy', async () => {
  const files = ['app.js', 'chat.js', 'documents.js', 'memories.js', 'diagnostics.js'];

  for (const file of files) {
    const source = await readFile(new URL(`./js/${file}`, import.meta.url), 'utf8');
    const imports = [...source.matchAll(/from\s+['"](\.\/[^'"]+)['"]/g)].map(match => match[1]);
    assert.ok(imports.length > 0, `${file} should contain relative imports`);
    for (const specifier of imports) {
      assert.match(specifier, /\?v=[^?]+$/, `${file}: ${specifier}`);
    }
  }
});


test('all frontend modules use one current API module version', async () => {
  const files = ['artifacts.js', 'chat.js', 'diagnostics.js', 'documents.js', 'memories.js', 'models.js', 'projects.js'];
  const versions = [];

  for (const file of files) {
    const source = await readFile(new URL(`./js/${file}`, import.meta.url), 'utf8');
    const version = source.match(/from ['"]\.\/api\.js\?v=([^'"]+)['"]/)?.[1];
    assert.ok(version, `${file} should import a versioned api.js`);
    versions.push(version);
  }

  assert.equal(new Set(versions).size, 1, `api.js versions must match: ${versions.join(', ')}`);
});
