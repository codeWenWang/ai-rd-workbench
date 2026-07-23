import test from 'node:test';
import assert from 'node:assert/strict';
import { renderMarkdown } from './js/markdown.js';

test('renders common markdown without exposing raw markers or unsafe html', () => {
  const html = renderMarkdown('## 标题\n\n**重点** 和 `code`\n\n- 一项\n- 二项\n\n<script>alert(1)</script>');
  assert.match(html, /<h2>标题<\/h2>/);
  assert.match(html, /<strong>重点<\/strong>/);
  assert.match(html, /<code>code<\/code>/);
  assert.match(html, /<ul>[\s\S]*<li>一项<\/li>/);
  assert.doesNotMatch(html, /<script>/);
  assert.doesNotMatch(html, /\*\*/);
});

test('renders tables, ordered lists, separators and model line breaks', () => {
  const html = renderMarkdown('---\n\n| 模块 | 职责 |\n| --- | --- |\n| api | 接口<br>校验 |\n\n1. 扫描\n2. 审查');
  assert.match(html, /<hr>/);
  assert.match(html, /<table>[\s\S]*<th>模块<\/th>/);
  assert.match(html, /<td>接口<br>校验<\/td>/);
  assert.match(html, /<ol>[\s\S]*<li>扫描<\/li>/);
  assert.doesNotMatch(html, /\| --- \|/);
  assert.doesNotMatch(html, /&lt;br&gt;/);
});

test('removes decorative emoji prefixes from prose while preserving code blocks', () => {
  const html = renderMarkdown('## ✅ 项目目标\n\n🧱 模块职责\n\n```text\n✅ status\n```');
  assert.match(html, /<h2>项目目标<\/h2>/);
  assert.match(html, /<p>模块职责<\/p>/);
  assert.match(html, /<code data-language="text">✅ status/);
  assert.doesNotMatch(html, /<h2>✅/);
});
