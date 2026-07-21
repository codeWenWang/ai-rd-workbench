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
