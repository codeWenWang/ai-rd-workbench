export function escapeHtml(value = '') {
  return String(value).replace(/[&<>"']/g, character => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[character]));
}

export function renderMarkdown(value = '') {
  const source = String(value).replace(/\r\n/g, '\n');
  const blocks = source.split(/```/g);
  return blocks.map((block, index) => {
    if (index % 2 === 1) {
      const lines = block.split('\n');
      const language = /^[\w+#.-]+$/.test(lines[0]?.trim() || '') ? lines.shift().trim() : '';
      return `<pre class="md-code"><code data-language="${escapeHtml(language)}">${escapeHtml(lines.join('\n'))}</code></pre>`;
    }
    return renderText(block);
  }).join('');
}

function renderText(value) {
  const lines = value.split('\n');
  const output = [];
  let list = false;
  const closeList = () => { if (list) { output.push('</ul>'); list = false; } };
  for (const raw of lines) {
    const line = raw.trimEnd();
    if (!line.trim()) { closeList(); continue; }
    const heading = line.match(/^(#{1,3})\s+(.+)$/);
    const bullet = line.match(/^[-*]\s+(.+)$/);
    if (heading) { closeList(); output.push(`<h${heading[1].length}>${inline(heading[2])}</h${heading[1].length}>`); continue; }
    if (bullet) { if (!list) { output.push('<ul>'); list = true; } output.push(`<li>${inline(bullet[1])}</li>`); continue; }
    closeList(); output.push(`<p>${inline(line)}</p>`);
  }
  closeList();
  return output.join('');
}

function inline(value) {
  return escapeHtml(value)
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/__(.+?)__/g, '<strong>$1</strong>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noreferrer">$1</a>');
}
