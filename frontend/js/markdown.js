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
  const normalized = value.replace(/^(\s*(?:#{1,3}\s*)?)[\u{1F300}-\u{1FAFF}\u2600-\u27BF]\uFE0F?\s*/gmu, '$1');
  const lines = normalized.split('\n');
  const output = [];
  let list = '';
  let paragraph = [];
  const closeList = () => { if (list) { output.push(`</${list}>`); list = ''; } };
  const closeParagraph = () => {
    if (!paragraph.length) return;
    output.push(`<p>${paragraph.map(inline).join('<br>')}</p>`);
    paragraph = [];
  };
  const closeBlocks = () => { closeParagraph(); closeList(); };
  const openList = type => {
    closeParagraph();
    if (list === type) return;
    closeList();
    output.push(`<${type}>`);
    list = type;
  };
  for (let index = 0; index < lines.length; index += 1) {
    const raw = lines[index];
    const line = raw.trimEnd();
    if (!line.trim()) { closeBlocks(); continue; }
    const heading = line.match(/^(#{1,3})\s+(.+)$/);
    const bullet = line.match(/^[-*]\s+(.+)$/);
    const ordered = line.match(/^\d+[.)]\s+(.+)$/);
    const quote = line.match(/^>\s?(.*)$/);
    const next = lines[index + 1] || '';
    if (heading) { closeBlocks(); output.push(`<h${heading[1].length}>${inline(heading[2])}</h${heading[1].length}>`); continue; }
    if (/^\s{0,3}([-*_])(?:\s*\1){2,}\s*$/.test(line)) { closeBlocks(); output.push('<hr>'); continue; }
    if (isTableRow(line) && isTableDivider(next)) {
      closeBlocks();
      const headers = tableCells(line);
      output.push(`<div class="md-table-wrap"><table><thead><tr>${headers.map(cell => `<th>${inline(cell)}</th>`).join('')}</tr></thead><tbody>`);
      index += 2;
      while (index < lines.length && isTableRow(lines[index]) && lines[index].trim()) {
        const cells = tableCells(lines[index]);
        output.push(`<tr>${headers.map((_, cellIndex) => `<td>${inline(cells[cellIndex] || '')}</td>`).join('')}</tr>`);
        index += 1;
      }
      output.push('</tbody></table></div>');
      index -= 1;
      continue;
    }
    if (bullet) { openList('ul'); output.push(`<li>${inline(bullet[1])}</li>`); continue; }
    if (ordered) { openList('ol'); output.push(`<li>${inline(ordered[1])}</li>`); continue; }
    if (quote) { closeBlocks(); output.push(`<blockquote>${inline(quote[1])}</blockquote>`); continue; }
    closeList();
    paragraph.push(line.trim());
  }
  closeBlocks();
  return output.join('');
}

function isTableRow(value) {
  const line = String(value || '').trim();
  return line.includes('|') && !/^\|?\s*[-:]+\s*\|/.test(line);
}

function isTableDivider(value) {
  const cells = tableCells(value);
  return cells.length > 0 && cells.every(cell => /^:?-{3,}:?$/.test(cell.replace(/\s/g, '')));
}

function tableCells(value) {
  return String(value || '').trim().replace(/^\||\|$/g, '').split('|').map(cell => cell.trim());
}

function inline(value) {
  return escapeHtml(value)
    .replace(/&lt;br\s*\/?&gt;/gi, '<br>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/__(.+?)__/g, '<strong>$1</strong>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\[([^\]]+)\]\((source:\/\/[^\s)]+)\)/g, '<a href="$2" class="source-link">$1</a>')
    .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noreferrer">$1</a>');
}
