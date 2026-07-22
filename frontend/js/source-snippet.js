function locationLine(location) {
  const match = String(location || '').match(/:(\d+)$/);
  return match ? Math.max(1, Number(match[1])) : 0;
}

function matchingBlockEnd(lines, start) {
  let depth = 0;
  let opened = false;
  for (let index = start; index < lines.length; index += 1) {
    for (const character of lines[index]) {
      if (character === '{') { depth += 1; opened = true; }
      if (character === '}') depth -= 1;
    }
    if (opened && depth <= 0) return index;
  }
  return Math.min(lines.length - 1, start + 40);
}

function annotationBlockStart(lines, codeLine, boundary) {
  let start = codeLine;
  let index = codeLine - 1;
  while (index > boundary && !lines[index].trim()) index -= 1;
  while (index > boundary) {
    const value = lines[index].trim();
    if (value.startsWith('@')) {
      start = index;
      index -= 1;
      continue;
    }
    if (value.endsWith('*/')) {
      start = index;
      while (start > boundary && !lines[start].includes('/**')) start -= 1;
      index = start - 1;
      continue;
    }
    break;
  }
  return start;
}

function endpointIndexes(lines, lineNumber) {
  const target = Math.max(0, lineNumber - 1);
  let classLine = -1;
  for (let index = target; index >= 0; index -= 1) {
    if (/\b(class|record|interface)\s+[A-Za-z_$][\w$]*/.test(lines[index])) {
      classLine = index;
      break;
    }
  }
  if (classLine < 0) return null;

  const isMethodLine = line => /\b(public|protected|private)\b/.test(line)
    && /[A-Za-z_$][\w$]*\s*\(/.test(line)
    && !/\b(class|record|interface)\b/.test(line);
  let methodLine = -1;
  const searchEnd = Math.min(lines.length, target + 24);
  for (let index = target; index < searchEnd; index += 1) {
    if (isMethodLine(lines[index])) {
      methodLine = index;
      break;
    }
  }
  if (methodLine < 0) {
    for (let index = target - 1; index > classLine; index -= 1) {
      if (isMethodLine(lines[index])) { methodLine = index; break; }
    }
  }
  if (methodLine < 0) return null;

  const methodStart = annotationBlockStart(lines, methodLine, classLine);
  const methodEnd = matchingBlockEnd(lines, methodLine);
  const classStart = annotationBlockStart(lines, classLine, -1);
  const selected = new Set();
  for (let index = classStart; index <= classLine; index += 1) selected.add(index);

  for (let index = classLine + 1; index < methodStart; index += 1) {
    const value = lines[index].trim();
    const injected = /^@(Autowired|Inject|Resource)\b/.test(value);
    const field = /^(private|protected)\s+(?:static\s+)?(?:final\s+)?[^();]+;\s*$/.test(value);
    if (!injected && !field) continue;
    selected.add(index);
    if (injected) {
      for (let cursor = index + 1; cursor < methodStart; cursor += 1) {
        selected.add(cursor);
        if (lines[cursor].includes(';')) { index = cursor; break; }
      }
    }
  }
  for (let index = methodStart; index <= methodEnd; index += 1) selected.add(index);

  const classEnd = matchingBlockEnd(lines, classLine);
  if (classEnd > methodEnd) selected.add(classEnd);
  return [...selected].sort((left, right) => left - right);
}

function formatLines(lines, indexes, lineNumber) {
  const output = [];
  let previous = -1;
  for (const index of indexes) {
    if (previous >= 0 && index - previous > 1) output.push('       ...');
    const current = index + 1;
    output.push(`${current === lineNumber ? '>' : ' '} ${String(current).padStart(4)}  ${lines[index]}`);
    previous = index;
  }
  return output.join('\n');
}

export function sourceSnippet(content, location, { endpoint = false } = {}) {
  const lines = String(content || '').split('\n');
  const lineNumber = locationLine(location);
  if (endpoint) {
    const indexes = endpointIndexes(lines, lineNumber);
    if (indexes?.length) return formatLines(lines, indexes, lineNumber);
  }
  const start = Math.max(0, lineNumber ? lineNumber - 7 : 0);
  const end = Math.min(lines.length, lineNumber ? lineNumber + 6 : 80);
  return formatLines(lines, Array.from({ length: end - start }, (_, index) => start + index), lineNumber);
}
